"""
Jobicy — free public REST API, no auth required
Remote-first, US jobs, full descriptions, salary data included
Docs: https://jobi.cy/apidocs
"""
import hashlib
import requests
from datetime import datetime
from config import EXCLUDE_KEYWORDS, MIN_SALARY

API = "https://jobicy.com/api/v2/remote-jobs"

TITLE_KEYWORDS = [
    "data scientist", "data science", "business analyst", "business systems",
    "data engineer", "ml engineer", "machine learning", "ai engineer",
    "technical project", "project manager", "analytics", "intelligence",
    "generative ai", "genai", "llm", "program manager",
]

LEVEL_BLOCKLIST = ["junior", "entry", "intern", "associate"]


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _matches_target(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in TITLE_KEYWORDS)


def _is_excluded(title: str, desc: str) -> bool:
    text = (title + " " + desc).lower()
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


def _is_junior(title: str, level: str) -> bool:
    t = (title + " " + (level or "")).lower()
    return any(s in t for s in LEVEL_BLOCKLIST)


def scrape_jobicy(max_results: int = 50) -> list[dict]:
    jobs = []
    seen = set()

    try:
        resp = requests.get(
            API,
            params={"count": max_results, "geo": "usa"},
            timeout=12,
        )
        if resp.status_code != 200:
            print(f"  Jobicy: HTTP {resp.status_code}")
            return []

        data = resp.json().get("jobs", [])
        for j in data:
                title = j.get("jobTitle", "")
                level = j.get("jobLevel", "")
                url = j.get("url", "")
                desc = j.get("jobDescription", "")
                excerpt = j.get("jobExcerpt", "")

                if not _matches_target(title):
                    continue
                if _is_excluded(title, desc):
                    continue
                if _is_junior(title, level):
                    continue

                # Salary gate — use salaryMin if available
                salary_min = j.get("salaryMin")
                if salary_min and int(salary_min) < MIN_SALARY:
                    continue

                job_id = _make_id(url)
                if job_id in seen:
                    continue
                seen.add(job_id)

                jobs.append({
                    "id": job_id,
                    "source": "jobicy",
                    "title": title,
                    "company": j.get("companyName", ""),
                    "location": j.get("jobGeo", "Remote"),
                    "url": url,
                    "description": desc or excerpt,
                    "posted_at": j.get("pubDate", datetime.utcnow().isoformat()),
                    "status": "new",
                    "score": None,
                    "cover_letter": None,
                    "salary_range": f"${salary_min:,}–${j['salaryMax']:,}" if salary_min and j.get("salaryMax") else None,
                })
    except Exception as e:
        print(f"  Jobicy error: {e}")

    return jobs
