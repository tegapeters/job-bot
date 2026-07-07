"""
We Work Remotely — RSS feed scraper
Free, no auth, updated frequently, US-skewed remote roles
"""
import feedparser
import hashlib
from datetime import datetime
from config import TARGET_ROLES, EXCLUDE_KEYWORDS

WWR_FEEDS = [
    # The data-science and management-finance category feeds went dead (301).
    # Programming is the only category still returning relevant results.
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
]

TITLE_KEYWORDS = [
    "data scientist", "data science", "business analyst", "business systems",
    "data engineer", "ml engineer", "machine learning", "ai engineer",
    "technical project", "project manager", "analytics", "intelligence",
    "generative ai", "genai", "llm", "program manager",
]


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _matches_target(title: str, target_roles: list[str] = None) -> bool:
    t = title.lower()
    keywords = [r.lower() for r in target_roles] if target_roles else [k.lower() for k in TITLE_KEYWORDS]
    return any(k in t for k in keywords)


def _is_excluded(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


def scrape_weworkremotely(target_roles: list[str] = None) -> list[dict]:
    jobs = []
    seen = set()

    for feed_url in WWR_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                title = entry.get("title", "")
                # WWR title format: "Company: Job Title" — extract job title
                if ": " in title:
                    title = title.split(": ", 1)[1]

                if not _matches_target(title, target_roles=target_roles):
                    continue

                url = entry.get("link", "")
                summary = entry.get("summary", "")

                if _is_excluded(title, summary):
                    continue

                job_id = _make_id(url)
                if job_id in seen:
                    continue
                seen.add(job_id)

                jobs.append({
                    "id": job_id,
                    "source": "weworkremotely",
                    "title": title,
                    "company": entry.get("author", "Unknown"),
                    "location": "Remote",
                    "url": url,
                    "description": summary,
                    "posted_at": entry.get("published", datetime.utcnow().isoformat()),
                    "status": "new",
                    "score": None,
                    "cover_letter": None,
                })
        except Exception as e:
            print(f"  WWR error ({feed_url}): {e}")

    return jobs
