"""
Fetches full job descriptions, salary, and company from LinkedIn.
Uses the jobs-guest API endpoint which returns the full posting without auth or JS.
"""
import re
import time
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

GUEST_API = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"


def _extract_job_id(url: str) -> str | None:
    m = re.search(r"-(\d{10,})/?$", url)
    return m.group(1) if m else None


def _clean(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#?\w+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_linkedin_job(url: str) -> dict:
    """Returns {description, company, salary, posted_at} using LinkedIn's guest API."""
    result = {"description": "", "company": "", "salary": "", "posted_at": ""}

    job_id = _extract_job_id(url)
    api_url = GUEST_API.format(job_id=job_id) if job_id else url

    try:
        resp = requests.get(api_url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            # fall back to the view URL
            resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return result
        html = resp.text

        # Company
        for pat in [
            r'class="[^"]*topcard__org-name-link[^"]*"[^>]*>(.*?)</a>',
            r'class="[^"]*sub-nav-cta__optional-url[^"]*"[^>]*>(.*?)</a>',
            r'"companyName"\s*:\s*"([^"]+)"',
        ]:
            m = re.search(pat, html, re.DOTALL)
            if m:
                result["company"] = _clean(m.group(1))
                break

        # Full description — guest API returns the complete text inside this section
        desc_m = re.search(
            r'<div[^>]*class="[^"]*description__text[^"]*"[^>]*>(.*?)</section>',
            html, re.DOTALL
        )
        if not desc_m:
            desc_m = re.search(
                r'<section[^>]*class="[^"]*show-more-less-html[^"]*"[^>]*>(.*?)</section>',
                html, re.DOTALL
            )
        if not desc_m:
            # JSON-LD fallback
            desc_m = re.search(r'"description"\s*:\s*\{"value"\s*:\s*"(.*?)"(?:,|\})', html, re.DOTALL)
        if desc_m:
            result["description"] = _clean(desc_m.group(1))[:5000]

        # Salary — LinkedIn puts it after a "compensation" heading near the bottom
        salary_m = re.search(
            r'[Cc]ompensation[^<]*(?:<[^>]+>)*\s*(\$[\d,.]+ ?USD? ?[-–] ?\$[\d,.]+)',
            html, re.DOTALL
        )
        if not salary_m:
            salary_m = re.search(r'(\$[\d,.]+ ?USD ?- ?\$[\d,.]+ ?USD)', html)
        if not salary_m:
            salary_m = re.search(r'(\$[\d,.]+(?:K)?\s*[-–]\s*\$[\d,.]+(?:K)?)', html)
        if salary_m:
            result["salary"] = _clean(salary_m.group(1))[:120]

        # Posted date — guest API shows "X days/hours/weeks ago" text
        ago_m = re.search(r'(\d+)\s+(hour|day|week|month)s?\s+ago', html, re.IGNORECASE)
        if ago_m:
            from datetime import datetime, timedelta, timezone
            n, unit = int(ago_m.group(1)), ago_m.group(2).lower()
            delta = {"hour": timedelta(hours=n), "day": timedelta(days=n),
                     "week": timedelta(weeks=n), "month": timedelta(days=n * 30)}[unit]
            result["posted_at"] = (datetime.now(timezone.utc) - delta).date().isoformat()

    except Exception as e:
        print(f"  Fetch error ({url[:60]}): {e}")
    return result


def enrich_jobs(jobs: list[dict]) -> list[dict]:
    """Fetch full descriptions for LinkedIn jobs. Non-LinkedIn jobs are skipped
    (their descriptions come directly from the scraper API/RSS).
    Jobs that already have a description are skipped to avoid double-fetching."""
    li_jobs = [j for j in jobs if "linkedin.com" in (j.get("url") or "")]
    other   = [j for j in jobs if "linkedin.com" not in (j.get("url") or "")]

    to_fetch  = [j for j in li_jobs if not j.get("description")]
    already   = [j for j in li_jobs if j.get("description")]

    if to_fetch:
        print(f"\n🌐 Enriching {len(to_fetch)} LinkedIn jobs "
              f"({len(already)} already have descriptions, skipping {len(other)} non-LinkedIn)...")
    for i, job in enumerate(to_fetch):
        url = job.get("url", "")
        print(f"  [{i+1}/{len(to_fetch)}] {job['title'][:55]}", end="", flush=True)
        data = fetch_linkedin_job(url)
        if data["description"]:
            job["description"] = data["description"]
            print(f" ✓ ({len(data['description'])} chars)", end="")
        else:
            print(" ✗ no desc", end="")
        if data["company"] and not job.get("company"):
            job["company"] = data["company"]
        if data["posted_at"]:
            job["posted_at"] = data["posted_at"]
        if data["salary"]:
            job["salary_range"] = data["salary"]
            print(f" | {data['salary'][:40]}", end="")
        print()
        time.sleep(0.8)

    return to_fetch + already + other
