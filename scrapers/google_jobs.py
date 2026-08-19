"""
Google Jobs via SerpAPI — free tier: 100 searches/month.
Sign up at https://serpapi.com and set SERPAPI_KEY in .env / Streamlit Cloud secrets.

Returns structured job data aggregated by Google from hundreds of job boards
and company career pages — best single source for breadth.
"""
import hashlib
import re
import requests
from datetime import datetime
from config import EXCLUDE_KEYWORDS, SERPAPI_KEY

API = "https://serpapi.com/search.json"


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _is_excluded(title: str) -> bool:
    return any(kw in title.lower() for kw in EXCLUDE_KEYWORDS)


def _parse_salary(job: dict) -> str | None:
    ext = job.get("detected_extensions") or {}
    sal = ext.get("salary")
    if sal:
        return sal
    # Sometimes buried in job_highlights
    for section in (job.get("job_highlights") or []):
        for item in (section.get("items") or []):
            if re.search(r"\$[\d,]+", item):
                return item[:80]
    return None


def _best_apply_url(job: dict, fallback_query: str) -> str:
    options = job.get("apply_options") or []
    for opt in options:
        link = opt.get("link", "")
        if link and "google.com/search" not in link:
            return link
    # Fallback: Google Jobs share link
    job_id = job.get("job_id", "")
    if job_id:
        return f"https://www.google.com/search?q={fallback_query.replace(' ', '+')}&ibp=htl;jobs#htivrt=jobs&htidocid={job_id}"
    return ""


def scrape_google_jobs(target_roles: list[str] = None, min_salary: int = 0,
                       locations: list[str] | None = None) -> list[dict]:
    if not SERPAPI_KEY:
        print("   Google Jobs: skipped (SERPAPI_KEY not set — get a free key at serpapi.com)")
        return []

    jobs: list[dict] = []
    seen: set[str] = set()
    roles = target_roles or ["data engineer"]
    locs = locations or ["United States"]

    # Build deduplicated queries (max 4 to stay in free-tier budget)
    queries: list[str] = []
    seen_q: set[str] = set()
    for role in roles:
        q = role.strip()
        if q and q not in seen_q:
            seen_q.add(q)
            queries.append(q)
        if len(queries) >= 4:
            break

    # Google Jobs uses a single location param — pick the most general one
    location_str = "United States"
    for loc in locs:
        if loc.lower() not in ("remote", "united states", "us", "anywhere"):
            location_str = loc
            break

    for query in queries:
        params = {
            "engine": "google_jobs",
            "q": query,
            "location": location_str,
            "api_key": SERPAPI_KEY,
            "hl": "en",
            "gl": "us",
            "chips": "date_posted:week",  # last 7 days
        }
        try:
            resp = requests.get(API, params=params, timeout=20)
            if resp.status_code == 401:
                print("   Google Jobs: invalid SERPAPI_KEY")
                break
            if resp.status_code != 200:
                print(f"   Google Jobs: HTTP {resp.status_code} for query={query!r}")
                continue

            data = resp.json()
            if "error" in data:
                print(f"   Google Jobs API error: {data['error']}")
                continue

            for item in data.get("jobs_results", []):
                title = (item.get("title") or "").strip()
                if not title or _is_excluded(title):
                    continue

                company = (item.get("company_name") or "").strip()
                location = (item.get("location") or "").strip()
                description = (item.get("description") or "")[:5000]
                apply_url = _best_apply_url(item, query)

                job_id = _make_id(apply_url or f"{title}|{company}")
                if job_id in seen:
                    continue
                seen.add(job_id)

                ext = item.get("detected_extensions") or {}
                posted_raw = ext.get("posted_at", "")

                entry: dict = {
                    "id": job_id,
                    "source": "google_jobs",
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": apply_url,
                    "description": description,
                    "posted_at": posted_raw or datetime.utcnow().isoformat(),
                    "status": "new",
                    "score": None,
                    "cover_letter": None,
                }
                sal = _parse_salary(item)
                if sal:
                    entry["salary_range"] = sal

                # Infer work_type from location field
                loc_lower = location.lower()
                if "remote" in loc_lower or "anywhere" in loc_lower:
                    entry["work_type"] = "remote"
                elif "hybrid" in loc_lower:
                    entry["work_type"] = "hybrid"
                elif location:
                    entry["work_type"] = "onsite"

                jobs.append(entry)

        except Exception as e:
            print(f"   Google Jobs error (query={query!r}): {e}")

    return jobs
