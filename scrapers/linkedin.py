"""
LinkedIn Jobs scraper — uses public search RSS + HTML fallback
"""
import hashlib
import re
import time
import requests
from datetime import datetime
from config import TARGET_ROLES, EXCLUDE_KEYWORDS, LOCATIONS_ONSITE

# LinkedIn public job search URL (no auth required for listing pages)
LI_SEARCH = (
    "https://www.linkedin.com/jobs/search/?keywords={query}"
    "&location={location}&f_TPR=r259200"  # last 3 days
    "&f_WT={work_type}"  # 1=onsite, 2=remote, 3=hybrid
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

WORK_TYPES = {"remote": "2", "hybrid": "3", "onsite": "1"}


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _is_excluded(title: str, desc: str) -> bool:
    text = (title + " " + desc).lower()
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


def _parse_jobs_from_html(html: str, source_url: str) -> list[dict]:
    """Extract job cards from LinkedIn search HTML."""
    import json as _json
    jobs = []

    # Try JSON-LD first (most reliable)
    json_ld_hits = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
    for raw in json_ld_hits:
        try:
            data = _json.loads(raw)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") not in ("JobPosting", "jobPosting"):
                    continue
                url = item.get("url", "")
                title = item.get("title", "").strip()
                company = ""
                org = item.get("hiringOrganization", {})
                if isinstance(org, dict):
                    company = org.get("name", "")
                if not title or not url or _is_excluded(title, ""):
                    continue
                jobs.append({
                    "id": _make_id(url),
                    "source": "linkedin",
                    "title": title,
                    "company": company,
                    "location": "",
                    "url": url.split("?")[0],
                    "description": item.get("description", "")[:500],
                    "posted_at": datetime.utcnow().isoformat(),
                    "status": "new",
                    "score": None,
                    "cover_letter": None,
                })
        except Exception:
            pass

    if jobs:
        return jobs

    # Fallback: regex on job cards
    # Try to extract title + company together from job card HTML
    card_pattern = re.compile(
        r'href="(https://www\.linkedin\.com/jobs/view/[^"]+)"[^>]*>.*?'
        r'class="[^"]*base-search-card__title[^"]*"[^>]*>(.*?)</[^>]+>.*?'
        r'class="[^"]*base-search-card__subtitle[^"]*"[^>]*>(.*?)</[^>]+>',
        re.DOTALL,
    )
    seen_urls = set()
    for m in card_pattern.finditer(html):
        url = m.group(1).split("?")[0]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        company = re.sub(r"<[^>]+>", "", m.group(3)).strip()
        if not title or _is_excluded(title, ""):
            continue
        jobs.append({
            "id": _make_id(url),
            "source": "linkedin",
            "title": title,
            "company": company,
            "location": "",
            "url": url,
            "description": "",
            "posted_at": datetime.utcnow().isoformat(),
            "status": "new",
            "score": None,
            "cover_letter": None,
        })

    return jobs


def scrape_linkedin(max_per_query: int = 15) -> list[dict]:
    jobs = []
    seen = set()

    for role in TARGET_ROLES[:8]:  # top 8 roles
        query = requests.utils.quote(role)
        for wt_name, wt_code in WORK_TYPES.items():
            if wt_name == "onsite":
                # Search across all US onsite cities
                onsite_locs = [l.replace(" ", "+").replace(",", "%2C") for l in LOCATIONS_ONSITE]
            else:
                onsite_locs = ["United+States"]

            for loc in onsite_locs:
                url = LI_SEARCH.format(query=query, location=loc, work_type=wt_code)
                try:
                    resp = requests.get(url, headers=HEADERS, timeout=10)
                    if resp.status_code == 200:
                        parsed = _parse_jobs_from_html(resp.text, url)
                        for j in parsed:
                            if j["id"] not in seen:
                                seen.add(j["id"])
                                j["location"] = loc.replace("+", " ").replace("%2C", ",")
                                jobs.append(j)
                                if len(jobs) >= max_per_query * len(TARGET_ROLES):
                                    return jobs
                    time.sleep(1.2)  # be polite
                except Exception as e:
                    print(f"  LinkedIn scrape error ({role}, {wt_name}, {loc}): {e}")

    return jobs
