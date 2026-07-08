"""
We Work Remotely — RSS feed scraper
Free, no auth, updated frequently, US-skewed remote roles
"""
import feedparser
import hashlib
from datetime import datetime
from config import EXCLUDE_KEYWORDS

# All confirmed-live WWR category feeds (as of 2026-07-08).
# Many category feeds (marketing, sales, legal, finance, hr, writing) return 301.
# These 5 are the only ones currently returning entries.
_ALL_LIVE_FEEDS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
    "https://weworkremotely.com/categories/remote-product-jobs.rss",
    "https://weworkremotely.com/categories/remote-design-jobs.rss",
    "https://weworkremotely.com/categories/remote-customer-support-jobs.rss",
]

# Maps role keywords → which feeds are most relevant.
# Feeds not in this map still get searched if no roles match (fallback to all).
_FEED_AFFINITY: dict[str, list[str]] = {
    # All keys space-padded for consistent word-boundary matching.
    " engineer ":         ["remote-programming-jobs", "remote-devops-sysadmin-jobs"],
    " developer ":        ["remote-programming-jobs"],
    " devops ":           ["remote-devops-sysadmin-jobs"],
    " infrastructure ":   ["remote-devops-sysadmin-jobs"],
    " cloud ":            ["remote-devops-sysadmin-jobs"],
    " product ":          ["remote-product-jobs"],
    " analyst ":          ["remote-product-jobs", "remote-programming-jobs"],
    " manager ":          ["remote-product-jobs"],
    " design ":           ["remote-design-jobs"],
    " ux ":               ["remote-design-jobs"],
    " ui ":               ["remote-design-jobs"],
    " support ":          ["remote-customer-support-jobs"],
    " customer success ": ["remote-customer-support-jobs"],
    " data ":             ["remote-programming-jobs", "remote-product-jobs"],
    " scientist ":        ["remote-programming-jobs"],
    " machine learning ": ["remote-programming-jobs"],
    " ai ":               ["remote-programming-jobs"],
}


def _select_feeds(target_roles: list[str] | None) -> list[str]:
    """Return ordered list of feed URLs relevant to the user's target roles."""
    if not target_roles:
        return _ALL_LIVE_FEEDS

    slug_set: set[str] = set()
    for role in target_roles:
        role_l = f" {role.lower()} "
        for keyword, slugs in _FEED_AFFINITY.items():
            if keyword in role_l:
                slug_set.update(slugs)

    if not slug_set:
        return _ALL_LIVE_FEEDS

    # Build ordered URL list — matched feeds first, then remaining
    base = "https://weworkremotely.com/categories/"
    matched = [f"{base}{s}.rss" for s in slug_set]
    rest = [f for f in _ALL_LIVE_FEEDS if f not in matched]
    return matched + rest


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _matches_target(title: str, target_roles: list[str] | None) -> bool:
    t = title.lower()
    if not target_roles:
        return True
    return any(r.lower() in t for r in target_roles)


def _is_excluded(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


def scrape_weworkremotely(target_roles: list[str] = None) -> list[dict]:
    jobs = []
    seen = set()
    feeds = _select_feeds(target_roles)

    for feed_url in feeds:
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
