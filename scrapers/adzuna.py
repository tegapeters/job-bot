"""
Adzuna Jobs API — free tier (250 req/day), no scraping needed.
Sign up at https://developer.adzuna.com to get APP_ID + APP_KEY.
Set ADZUNA_APP_ID and ADZUNA_APP_KEY in .env / Streamlit Cloud secrets.
"""
import hashlib
import requests
from datetime import datetime
from config import EXCLUDE_KEYWORDS, ADZUNA_APP_ID, ADZUNA_APP_KEY

API = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"

HEADERS = {"Accept": "application/json"}

# Map location strings → Adzuna country codes
_COUNTRY_MAP = {
    "uk": "gb", "united kingdom": "gb", "london": "gb",
    "manchester": "gb", "birmingham": "gb", "edinburgh": "gb",
    "canada": "ca", "toronto": "ca", "vancouver": "ca",
    "montreal": "ca", "calgary": "ca", "ottawa": "ca",
    "australia": "au", "sydney": "au", "melbourne": "au",
    "germany": "de", "berlin": "de", "munich": "de", "frankfurt": "de",
    "france": "fr", "paris": "fr",
    "netherlands": "nl", "amsterdam": "nl",
    "singapore": "sg",
}


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _is_excluded(title: str) -> bool:
    return any(kw in title.lower() for kw in EXCLUDE_KEYWORDS)


def _salary_range(item: dict) -> str | None:
    lo = item.get("salary_min")
    hi = item.get("salary_max")
    if lo and hi:
        return f"${int(lo):,} - ${int(hi):,} /yr"
    if lo:
        return f"${int(lo):,}+ /yr"
    return None


def _countries_from_locations(locations: list[str]) -> list[str]:
    """Return deduplicated Adzuna country codes inferred from the location list."""
    codes: list[str] = []
    seen: set[str] = set()
    for loc in (locations or []):
        key = loc.lower().strip().rstrip(",. ")
        # Check explicit map
        code = _COUNTRY_MAP.get(key)
        if not code:
            # Check if any map key is a substring
            for k, v in _COUNTRY_MAP.items():
                if k in key:
                    code = v
                    break
        code = code or "us"  # default to US
        if code not in seen:
            seen.add(code)
            codes.append(code)
    return codes or ["us"]


def _where_from_location(loc: str) -> str | None:
    """Return a city/region string suitable for Adzuna's `where` param."""
    lower = loc.lower().strip()
    if lower in ("remote", "united states", "us"):
        return None
    # Strip country suffix for city searches (e.g. "Houston, TX" → "Houston")
    city = loc.split(",")[0].strip()
    return city if city else None


def scrape_adzuna(target_roles: list[str] = None, min_salary: int = 0,
                  locations: list[str] | None = None) -> list[dict]:
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        print("   Adzuna: skipped (ADZUNA_APP_ID / ADZUNA_APP_KEY not set)")
        return []

    jobs: list[dict] = []
    seen: set[str] = set()
    roles = target_roles or ["data scientist", "data engineer"]
    locs = locations or ["Remote"]

    countries = _countries_from_locations(locs)
    # For each country, determine the city searches to run
    where_values: list[str | None] = []
    for loc in locs:
        w = _where_from_location(loc)
        if w not in where_values:
            where_values.append(w)  # None = no city filter (country-wide)
    if not where_values:
        where_values = [None]

    # Deduplicate role queries (first 2 words, max 4 queries)
    queries: list[str] = []
    seen_q: set[str] = set()
    for role in roles:
        words = [w for w in role.lower().split() if len(w) > 2]
        q = " ".join(words[:2])
        if q and q not in seen_q:
            seen_q.add(q)
            queries.append(q)
        if len(queries) >= 4:
            break

    for country in countries:
        for query in queries:
            for where in where_values[:3]:  # cap city iterations
                params: dict = {
                    "app_id": ADZUNA_APP_ID,
                    "app_key": ADZUNA_APP_KEY,
                    "results_per_page": 20,
                    "what": query,
                    "content-type": "application/json",
                    "sort_by": "date",
                }
                if where:
                    params["where"] = where
                if min_salary:
                    params["salary_min"] = min_salary

                try:
                    url = API.format(country=country, page=1)
                    resp = requests.get(url, params=params, headers=HEADERS, timeout=12)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    for item in data.get("results", []):
                        redirect_url = item.get("redirect_url", "")
                        job_id = _make_id(redirect_url or str(item.get("id", "")))
                        if job_id in seen:
                            continue
                        seen.add(job_id)

                        title = item.get("title", "").strip()
                        if not title or _is_excluded(title):
                            continue

                        company = (item.get("company") or {}).get("display_name", "") or ""
                        location = (item.get("location") or {}).get("display_name", "") or ""
                        description = item.get("description", "")[:2000]
                        posted_raw = item.get("created", "")

                        job_entry: dict = {
                            "id": job_id,
                            "source": "adzuna",
                            "title": title,
                            "company": company,
                            "location": location,
                            "url": redirect_url,
                            "description": description,
                            "posted_at": posted_raw or datetime.utcnow().isoformat(),
                            "status": "new",
                            "score": None,
                            "cover_letter": None,
                        }
                        sr = _salary_range(item)
                        if sr:
                            job_entry["salary_range"] = sr
                        jobs.append(job_entry)
                except Exception as e:
                    print(f"   Adzuna error ({country}, {query}): {e}")

    return jobs
