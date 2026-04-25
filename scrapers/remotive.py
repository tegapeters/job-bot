"""
Remotive.com — free public API for remote jobs, no auth required
"""
import hashlib
import requests
from datetime import datetime
from config import TARGET_ROLES, EXCLUDE_KEYWORDS, MIN_SALARY

API = "https://remotive.com/api/remote-jobs"

REMOTIVE_CATEGORIES = [
    "data",
    "data-eng",
    "product",
    "project-mgmt",
    "software-dev",
]


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _is_excluded(title: str, desc: str) -> bool:
    text = (title + " " + desc).lower()
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


def _matches_target(title: str) -> bool:
    t = title.lower()
    keywords = [
        "data scientist", "business analyst", "business systems",
        "data engineer", "ml engineer", "machine learning",
        "ai engineer", "technical project", "project manager",
        "analytics engineer",
    ]
    return any(k in t for k in keywords)


def scrape_remotive() -> list[dict]:
    jobs = []
    seen = set()

    for cat in REMOTIVE_CATEGORIES:
        try:
            resp = requests.get(API, params={"category": cat, "limit": 50}, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json().get("jobs", [])
            for j in data:
                title = j.get("title", "")
                desc = j.get("description", "")
                url = j.get("url", "")

                if not _matches_target(title):
                    continue
                if _is_excluded(title, desc):
                    continue

                # Salary check if listed
                salary = j.get("salary", "")
                if salary:
                    nums = [int(n.replace(",", "")) for n in
                            __import__("re").findall(r"\d[\d,]+", salary)]
                    if nums and max(nums) < MIN_SALARY:
                        continue

                job_id = _make_id(url)
                if job_id in seen:
                    continue
                seen.add(job_id)

                jobs.append({
                    "id": job_id,
                    "source": "remotive",
                    "title": title,
                    "company": j.get("company_name", ""),
                    "location": "Remote",
                    "url": url,
                    "description": desc,
                    "posted_at": j.get("publication_date", datetime.utcnow().isoformat()),
                    "status": "new",
                    "score": None,
                    "cover_letter": None,
                })
        except Exception as e:
            print(f"  Remotive error ({cat}): {e}")

    return jobs
