"""
Indeed RSS scraper — pulls job listings for target roles
"""
import feedparser
import hashlib
from datetime import datetime
from config import TARGET_ROLES, LOCATIONS_REMOTE, LOCATIONS_HYBRID, LOCATIONS_ONSITE, MIN_SALARY, EXCLUDE_KEYWORDS


INDEED_RSS = "https://www.indeed.com/rss?q={query}&l={location}&sort=date&fromage=3"


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _is_excluded(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


def _is_junior(title: str) -> bool:
    t = title.lower()
    junior_signals = ["junior", "entry", "associate", "intern", "i ", " i,", "level 1", "lvl 1"]
    return any(s in t for s in junior_signals)


def scrape_indeed(max_per_query: int = 20) -> list[dict]:
    jobs = []
    seen = set()

    queries = [r.replace(" ", "+") for r in TARGET_ROLES]

    # Build location list: remote/hybrid as "Remote", onsite across US cities
    all_locations = (
        [l.replace(" ", "+").replace(",", "%2C") for l in LOCATIONS_REMOTE[:1]] +
        [l.replace(" ", "+").replace(",", "%2C") for l in LOCATIONS_ONSITE]
    )

    for query in queries:
        for loc in all_locations:
            url = INDEED_RSS.format(query=query, location=loc)
            feed = feedparser.parse(url)

            for entry in feed.entries[:max_per_query]:
                job_id = _make_id(entry.get("link", entry.get("id", "")))
                if job_id in seen:
                    continue
                seen.add(job_id)

                title = entry.get("title", "")
                summary = entry.get("summary", "")

                if _is_excluded(title, summary) or _is_junior(title):
                    continue

                jobs.append({
                    "id": job_id,
                    "source": "indeed",
                    "title": title,
                    "company": entry.get("author", "Unknown"),
                    "location": entry.get("indeed_city", loc.replace("+", " ")),
                    "url": entry.get("link", ""),
                    "description": summary,
                    "posted_at": entry.get("published", datetime.utcnow().isoformat()),
                    "status": "new",
                    "score": None,
                    "cover_letter": None,
                })

    return jobs
