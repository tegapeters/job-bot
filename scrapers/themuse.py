"""
The Muse public API — no key required, no scraping.
https://www.themuse.com/api/public/v1/jobs
Tech/data/business jobs with company detail. No salary data returned.
"""
import hashlib
import requests
from datetime import datetime
from config import EXCLUDE_KEYWORDS

API = "https://www.themuse.com/api/public/v1/jobs"

HEADERS = {"Accept": "application/json"}

# Categories closest to data/tech/analytics roles
_CATEGORIES = [
    "Data Science",
    "Engineering",
    "IT",
    "Project Management",
    "Business Development",
]

# Seniority levels — exclude intern/entry only
_LEVELS = [
    "Senior Level",
    "Mid Level",
    "Director",
    "VP",
    "C-Suite",
    "Manager",
]


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _is_excluded(title: str) -> bool:
    return any(kw in title.lower() for kw in EXCLUDE_KEYWORDS)


def _matches_roles(title: str, roles: list[str]) -> bool:
    if not roles:
        return True
    t = title.lower()
    for role in roles:
        if any(w in t for w in role.lower().split() if len(w) > 3):
            return True
    return False


def scrape_themuse(target_roles: list[str] = None,
                   locations: list[str] | None = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    roles = target_roles or []

    for category in _CATEGORIES:
        for page in range(1, 4):  # up to 3 pages per category
            try:
                resp = requests.get(
                    API,
                    params={"category": category, "page": page},
                    headers=HEADERS,
                    timeout=12,
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                items = data.get("results") or []
                if not items:
                    break

                for item in items:
                    title = (item.get("name") or "").strip()
                    if not title or _is_excluded(title):
                        continue
                    if roles and not _matches_roles(title, roles):
                        continue

                    url = (item.get("refs") or {}).get("landing_page", "")
                    job_id = _make_id(url or title)
                    if job_id in seen:
                        continue
                    seen.add(job_id)

                    company = (item.get("company") or {}).get("name", "")
                    raw_locs = item.get("locations") or []
                    location = ", ".join(l.get("name", "") for l in raw_locs if l.get("name")) or "Remote"
                    levels = [l.get("name", "") for l in (item.get("levels") or []) if l.get("name")]
                    published = item.get("publication_date", datetime.utcnow().isoformat())

                    # Skip intern/entry levels
                    level_str = " ".join(levels).lower()
                    if any(x in level_str for x in ("intern", "entry")):
                        continue

                    jobs.append({
                        "id": job_id,
                        "source": "themuse",
                        "title": title,
                        "company": company,
                        "location": location,
                        "url": url,
                        "description": f"Level: {', '.join(levels) or 'Not specified'}\nCategory: {category}",
                        "posted_at": published,
                        "status": "new",
                        "score": None,
                        "cover_letter": None,
                    })
            except Exception as e:
                print(f"   The Muse error ({category}, p{page}): {e}")
                break

    return jobs
