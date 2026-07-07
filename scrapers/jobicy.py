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

# Jobicy tag queries that return relevant results. "data-engineer" returns 404;
# "data", "analytics", and "python" are the supported tags that match our roles.
SCRAPE_TAGS = ["data", "analytics", "python"]


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _matches_target(title: str, target_roles: list[str] = None) -> bool:
    t = title.lower()
    keywords = [r.lower() for r in target_roles] if target_roles else TITLE_KEYWORDS
    return any(k in t for k in keywords)


def _is_excluded(title: str, desc: str) -> bool:
    text = (title + " " + desc).lower()
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


def _is_junior(title: str, level: str) -> bool:
    t = (title + " " + (level or "")).lower()
    return any(s in t for s in LEVEL_BLOCKLIST)


def scrape_jobicy(max_results: int = 50, target_roles: list[str] = None, min_salary: int = 0) -> list[dict]:
    jobs = []
    seen = set()

    for tag in SCRAPE_TAGS:
        try:
            resp = requests.get(
                API,
                params={"count": max_results, "geo": "usa", "tag": tag},
                timeout=12,
            )
            if resp.status_code != 200:
                print(f"  Jobicy: HTTP {resp.status_code} (tag={tag})")
                continue

            data = resp.json().get("jobs", [])
            for j in data:
                title = j.get("jobTitle", "")
                level = j.get("jobLevel", "")
                url = j.get("url", "")
                desc = j.get("jobDescription", "")
                excerpt = j.get("jobExcerpt", "")

                if not _matches_target(title, target_roles=target_roles):
                    continue
                if _is_excluded(title, desc):
                    continue
                if _is_junior(title, level):
                    continue

                # Salary gate — use user's min_salary if set, else config floor
                effective_min = min_salary if min_salary else MIN_SALARY
                salary_min = j.get("salaryMin")
                if salary_min and effective_min and int(salary_min) < effective_min:
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
            print(f"  Jobicy error (tag={tag}): {e}")

    return jobs
