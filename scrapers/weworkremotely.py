"""
We Work Remotely — RSS feed scraper
Free, no auth, updated frequently, US-skewed remote roles
"""
import feedparser
import hashlib
from datetime import datetime
from config import TARGET_ROLES, EXCLUDE_KEYWORDS

WWR_FEEDS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
    "https://weworkremotely.com/categories/remote-management-finance-jobs.rss",
    "https://weworkremotely.com/categories/remote-data-science-ai-statistics-jobs.rss",
    "https://weworkremotely.com/categories/remote-product-jobs.rss",
]

TITLE_KEYWORDS = [
    "data scientist", "data science", "business analyst", "business systems",
    "data engineer", "ml engineer", "machine learning", "ai engineer",
    "technical project", "project manager", "analytics", "intelligence",
    "generative ai", "genai", "llm", "program manager",
]


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _matches_target(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in TITLE_KEYWORDS)


def _is_excluded(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


def scrape_weworkremotely() -> list[dict]:
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

                if not _matches_target(title):
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
