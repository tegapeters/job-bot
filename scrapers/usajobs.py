"""
USAJobs API — free, covers all US federal government positions.
Register at https://developer.usajobs.gov/APIRequest/Index to get a key.
Set USAJOBS_API_KEY and USAJOBS_EMAIL in .env / Streamlit Cloud secrets.
"""
import hashlib
import requests
from datetime import datetime
from config import EXCLUDE_KEYWORDS, USAJOBS_API_KEY, USAJOBS_EMAIL

API = "https://data.usajobs.gov/api/search"

_RATE_CODE_MAP = {
    "PA": "/yr",   # Per Annum
    "PH": "/hr",   # Per Hour
    "BW": "/yr",   # Bi-Weekly (approx)
    "WC": "/wk",   # Weekly
}


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _is_excluded(title: str) -> bool:
    return any(kw in title.lower() for kw in EXCLUDE_KEYWORDS)


def _salary_str(rem: list[dict]) -> str | None:
    if not rem:
        return None
    r = rem[0]
    lo = r.get("MinimumRange", "")
    hi = r.get("MaximumRange", "")
    rate = _RATE_CODE_MAP.get(r.get("RateIntervalCode", "PA"), "/yr")
    try:
        lo_i = int(float(lo))
        hi_i = int(float(hi))
        if lo_i and hi_i and lo_i != hi_i:
            return f"${lo_i:,} - ${hi_i:,} {rate}"
        if lo_i:
            return f"${lo_i:,}+ {rate}"
    except (ValueError, TypeError):
        pass
    return None


def _location_names(locations: list[str]) -> list[str | None]:
    """Return USAJobs LocationName values from the user's preferred locations."""
    names: list[str | None] = []
    for loc in (locations or []):
        lower = loc.lower().strip()
        if lower in ("remote", "united states"):
            names.append(None)  # no LocationName = nationwide search
        else:
            # Use the city + state abbreviation (e.g. "Houston, TX")
            names.append(loc)
    return names or [None]


def scrape_usajobs(target_roles: list[str] = None, min_salary: int = 0,
                   locations: list[str] | None = None) -> list[dict]:
    if not USAJOBS_API_KEY or not USAJOBS_EMAIL:
        print("   USAJobs: skipped (USAJOBS_API_KEY / USAJOBS_EMAIL not set)")
        return []

    headers = {
        "Host": "data.usajobs.gov",
        "User-Agent": USAJOBS_EMAIL,
        "Authorization-Key": USAJOBS_API_KEY,
    }

    jobs: list[dict] = []
    seen: set[str] = set()
    roles = target_roles or ["data scientist", "data engineer"]

    # Deduplicate queries, max 4
    queries: list[str] = []
    seen_q: set[str] = set()
    for role in roles:
        if role.lower() not in seen_q:
            seen_q.add(role.lower())
            queries.append(role)
        if len(queries) >= 4:
            break

    loc_names = _location_names(locations)

    for query in queries:
        for loc_name in loc_names[:3]:
            params: dict = {
                "Keyword": query,
                "ResultsPerPage": 25,
                "SortField": "OpenDate",
                "SortDirection": "Desc",
                "DatePosted": 14,  # last 14 days
            }
            if loc_name:
                params["LocationName"] = loc_name
            if min_salary:
                params["RemunerationMinimumAmount"] = min_salary

            try:
                resp = requests.get(API, params=params, headers=headers, timeout=15)
                if resp.status_code != 200:
                    print(f"   USAJobs {resp.status_code}: {resp.text[:200]}")
                    continue
                data = resp.json()
                items = (data.get("SearchResult") or {}).get("SearchResultItems") or []
                for item in items:
                    desc_obj = item.get("MatchedObjectDescriptor") or {}
                    title = desc_obj.get("PositionTitle", "").strip()
                    if not title or _is_excluded(title):
                        continue

                    apply_uris = desc_obj.get("ApplyURI") or []
                    url = apply_uris[0] if apply_uris else desc_obj.get("PositionURI", "")
                    job_id = _make_id(url or title)
                    if job_id in seen:
                        continue
                    seen.add(job_id)

                    org = desc_obj.get("OrganizationName", "")
                    locs = desc_obj.get("PositionLocation") or []
                    location = locs[0].get("LocationName", "") if locs else ""
                    qual = desc_obj.get("QualificationSummary", "")[:2000]
                    posted = desc_obj.get("PublicationStartDate", datetime.utcnow().isoformat())

                    job_entry: dict = {
                        "id": job_id,
                        "source": "usajobs",
                        "title": title,
                        "company": org,
                        "location": location,
                        "url": url,
                        "description": qual,
                        "posted_at": posted,
                        "status": "new",
                        "score": None,
                        "cover_letter": None,
                    }
                    sr = _salary_str(desc_obj.get("PositionRemuneration") or [])
                    if sr:
                        job_entry["salary_range"] = sr
                    jobs.append(job_entry)
            except Exception as e:
                print(f"   USAJobs error ({query}, {loc_name}): {e}")

    return jobs
