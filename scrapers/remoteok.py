"""
RemoteOK — free public API, no auth required.
https://remoteok.com/api
Returns up to 100 remote jobs with salary data when available.
Fetches by domain tags derived from the user's target roles,
then applies title filtering so only matching jobs pass through.
"""
import hashlib
import time
import requests
from datetime import datetime
from config import EXCLUDE_KEYWORDS

API = "https://remoteok.com/api"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; JobPal/1.0)"}

# Map common role-domain keywords to RemoteOK tag slugs
_DOMAIN_TAGS = {
    "data": "data",
    "engineer": "engineer",
    "python": "python",
    "machine learning": "machine-learning",
    "ml": "machine-learning",
    "ai": "ai",
    "analytics": "analytics",
    "backend": "backend",
    "devops": "devops",
    "cloud": "cloud",
    "sql": "sql",
    "nurse": "medical",
    "nursing": "medical",
    "rn": "medical",
    "medical": "medical",
    "clinical": "medical",
    "healthcare": "medical",
    "finance": "finance",
    "accounting": "finance",
    "marketing": "marketing",
    "design": "design",
    "product": "product",
    "project": "project-management",
    "manager": "executive",
    "legal": "legal",
    "sales": "sales",
}


def _pick_tags(target_roles: list[str] | None) -> list[str]:
    """Derive the 2–3 best RemoteOK tags from the user's target roles."""
    if not target_roles:
        return ["engineer", "data"]

    seen: set[str] = set()
    tags: list[str] = []
    for role in target_roles:
        role_lower = role.lower()
        for keyword, tag in _DOMAIN_TAGS.items():
            if keyword in role_lower and tag not in seen:
                seen.add(tag)
                tags.append(tag)
        if len(tags) >= 3:
            break

    return tags if tags else ["engineer"]


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _is_excluded(title: str, desc: str) -> bool:
    text = (title + " " + desc).lower()
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


def scrape_remoteok(target_roles: list[str] = None, min_salary: int = 0) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()
    tags = _pick_tags(target_roles)

    for tag in tags:
        try:
            resp = requests.get(f"{API}?tags={tag}", headers=HEADERS, timeout=12)
            if resp.status_code != 200:
                print(f"  RemoteOK: HTTP {resp.status_code} for tag={tag}")
                continue

            data = resp.json()
            for j in data:
                if not isinstance(j, dict) or not j.get("position"):
                    continue

                title = j.get("position", "")
                url   = j.get("url", "") or j.get("apply_url", "")
                desc  = j.get("description", "") or ""
                company = j.get("company", "")

                if not url:
                    continue

                job_id = _make_id(url)
                if job_id in seen:
                    continue
                seen.add(job_id)

                if _is_excluded(title, desc):
                    continue

                # Salary gate
                sal_min = j.get("salary_min") or 0
                sal_max = j.get("salary_max") or 0
                effective_min = min_salary if min_salary else 0
                if effective_min and sal_max and int(sal_max) < effective_min:
                    continue

                salary_str = None
                if sal_min and sal_max and int(sal_min) > 0:
                    salary_str = f"${int(sal_min):,}–${int(sal_max):,}"

                jobs.append({
                    "id": job_id,
                    "source": "remoteok",
                    "title": title,
                    "company": company,
                    "location": "Remote",
                    "url": url,
                    "description": desc[:5000],
                    "posted_at": j.get("date", datetime.utcnow().isoformat()),
                    "status": "new",
                    "score": None,
                    "cover_letter": None,
                    "salary_range": salary_str,
                })

            time.sleep(0.5)  # be polite between tag requests

        except Exception as e:
            print(f"  RemoteOK error (tag={tag}): {e}")

    return jobs
