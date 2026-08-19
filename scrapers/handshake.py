"""
Handshake job scraper — opt-in, requires your personal session token.

Setup (one-time):
  1. Log into app.joinhandshake.com in Chrome
  2. Open DevTools → Application → Cookies → app.joinhandshake.com
  3. Copy the value of `remember_user_token`
  4. Add to .env:  HANDSHAKE_TOKEN=<paste here>

Skips gracefully if HANDSHAKE_TOKEN is not set.
This uses your own account at normal usage rates — not bulk/scale scraping.
"""
import hashlib
import re
import requests
from datetime import datetime
from config import EXCLUDE_KEYWORDS, HANDSHAKE_TOKEN

API = "https://app.joinhandshake.com/api/v1/jobs"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
}


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _is_excluded(title: str) -> bool:
    return any(kw in title.lower() for kw in EXCLUDE_KEYWORDS)


def _job_url(job_id) -> str:
    return f"https://app.joinhandshake.com/jobs/{job_id}"


def _parse_salary(job: dict) -> str | None:
    pay_min = job.get("pay_range_minimum")
    pay_max = job.get("pay_range_maximum")
    unit = (job.get("pay_period") or "").lower()
    if pay_min and pay_max:
        if "year" in unit or "annual" in unit or not unit:
            return f"${int(pay_min):,} - ${int(pay_max):,} /yr"
        return f"${int(pay_min):,} - ${int(pay_max):,} /{unit}"
    if pay_min:
        return f"${int(pay_min):,}+ /yr"
    return None


def scrape_handshake(target_roles: list[str] = None, min_salary: int = 0,
                     locations: list[str] | None = None) -> list[dict]:
    if not HANDSHAKE_TOKEN:
        print("   Handshake: skipped (HANDSHAKE_TOKEN not set — see scrapers/handshake.py for setup)")
        return []

    cookies = {"remember_user_token": HANDSHAKE_TOKEN}
    jobs: list[dict] = []
    seen: set[str] = set()
    roles = target_roles or ["data engineer"]

    queries: list[str] = []
    seen_q: set[str] = set()
    for role in roles:
        q = role.strip()
        if q and q not in seen_q:
            seen_q.add(q)
            queries.append(q)
        if len(queries) >= 4:
            break

    for query in queries:
        for page in range(1, 3):  # 2 pages = up to 50 results per query
            params = {
                "page": page,
                "per_page": 25,
                "query": query,
                "sort_direction": "desc",
                "sort_column": "created_at",
                "context_type": "research",
                "job_types[]": "1",  # full-time
            }
            try:
                resp = requests.get(
                    API,
                    params=params,
                    headers=HEADERS,
                    cookies=cookies,
                    timeout=15,
                )
                if resp.status_code == 401:
                    print("   Handshake: session token expired — refresh HANDSHAKE_TOKEN in .env")
                    return jobs
                if resp.status_code == 403:
                    print("   Handshake: access denied — check your token")
                    return jobs
                if resp.status_code != 200:
                    print(f"   Handshake: HTTP {resp.status_code} (page {page}, query={query!r})")
                    break

                data = resp.json()
                items = data.get("jobs") or data.get("results") or []
                if not items:
                    break  # no more pages

                for item in items:
                    jid = item.get("id")
                    title = (item.get("title") or "").strip()
                    if not title or not jid or _is_excluded(title):
                        continue

                    url = _job_url(jid)
                    job_id = _make_id(url)
                    if job_id in seen:
                        continue
                    seen.add(job_id)

                    employer = item.get("employer") or {}
                    company = (employer.get("name") or "").strip()
                    location = (item.get("location") or "").strip()
                    description = (item.get("description") or "")[:5000]
                    posted_raw = item.get("created_at") or item.get("posted_at") or ""

                    # Salary filter
                    sal_str = _parse_salary(item)
                    if min_salary and sal_str:
                        nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]+", sal_str)]
                        if nums and max(nums) < min_salary:
                            continue

                    entry: dict = {
                        "id": job_id,
                        "source": "handshake",
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": url,
                        "description": description,
                        "posted_at": posted_raw or datetime.utcnow().isoformat(),
                        "status": "new",
                        "score": None,
                        "cover_letter": None,
                    }
                    if sal_str:
                        entry["salary_range"] = sal_str

                    loc_lower = location.lower()
                    if "remote" in loc_lower or "anywhere" in loc_lower:
                        entry["work_type"] = "remote"
                    elif "hybrid" in loc_lower:
                        entry["work_type"] = "hybrid"
                    elif location:
                        entry["work_type"] = "onsite"

                    jobs.append(entry)

            except Exception as e:
                print(f"   Handshake error (query={query!r}, page={page}): {e}")
                break

    return jobs
