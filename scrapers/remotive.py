"""
Remotive.com — free public API, no auth required.
https://remotive.com/api/remote-jobs
Note: the category param is unreliable; we fetch by keyword search per role
and rely on title matching to keep results relevant.
"""
import hashlib
import re
import requests
from datetime import datetime
from config import EXCLUDE_KEYWORDS

API = "https://remotive.com/api/remote-jobs"


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _is_excluded(title: str, desc: str) -> bool:
    text = (title + " " + desc).lower()
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


def scrape_remotive(target_roles: list[str] = None, min_salary: int = 0) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    # Build search queries from target roles (deduplicated, max 4)
    queries: list[str] = []
    seen_q: set[str] = set()
    if target_roles:
        for role in target_roles:
            # Use first two meaningful words as the search term
            words = [w for w in role.lower().split() if len(w) > 2]
            q = " ".join(words[:2])
            if q and q not in seen_q:
                seen_q.add(q)
                queries.append(q)
            if len(queries) >= 4:
                break
    else:
        queries = ["data engineer", "software engineer"]

    for query in queries:
        try:
            resp = requests.get(
                API,
                params={"search": query, "limit": 20},
                timeout=12,
            )
            if resp.status_code != 200:
                continue

            for j in resp.json().get("jobs", []):
                title = j.get("title", "")
                url   = j.get("url", "")
                desc  = j.get("description", "") or ""

                if not url:
                    continue

                job_id = _make_id(url)
                if job_id in seen:
                    continue
                seen.add(job_id)

                if _is_excluded(title, desc):
                    continue

                # Salary gate
                salary_str = j.get("salary", "")
                if salary_str and min_salary:
                    nums = [int(n.replace(",", "")) for n in
                            re.findall(r"\d[\d,]+", salary_str)]
                    if nums and max(nums) < min_salary:
                        continue

                jobs.append({
                    "id": job_id,
                    "source": "remotive",
                    "title": title,
                    "company": j.get("company_name", ""),
                    "location": "Remote",
                    "url": url,
                    "description": desc[:5000],
                    "posted_at": j.get("publication_date", datetime.utcnow().isoformat()),
                    "status": "new",
                    "score": None,
                    "cover_letter": None,
                    "salary_range": salary_str or None,
                })

        except Exception as e:
            print(f"  Remotive error (query={query!r}): {e}")

    return jobs
