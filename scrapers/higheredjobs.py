"""
HigherEdJobs — standard RSS 2.0 category feeds (free, no auth).

HigherEdJobs publishes per-category RSS feeds for faculty disciplines. The
active feed URLs live in config.HIGHEREDJOBS_FEEDS (override per deployment
with the ACADEMIC_FEEDS_HIGHEREDJOBS env var) so a changed catID is a config
fix, not a code change. Follows the same feedparser pattern as
scrapers/weworkremotely.py.

NOTE: like every scraper here, a feed that is unreachable or empty is skipped
gracefully (returns no rows) rather than raising — the pipeline tolerates a
dead source. Live fetch cannot be verified from the dev sandbox (egress is
locked down); it runs against real feeds in the deployed app.
"""
import feedparser

from config import HIGHEREDJOBS_FEEDS
from ._academic import entry_to_job, is_excluded, matches_roles


def scrape_higheredjobs(target_roles: list[str] = None,
                        locations: list[str] = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    for feed_url in HIGHEREDJOBS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                job = entry_to_job(entry, source="higheredjobs")
                if job is None:
                    continue
                if job["id"] in seen:
                    continue
                if is_excluded(job["title"], job["description"]):
                    continue
                if not matches_roles(job["title"], target_roles):
                    continue
                seen.add(job["id"])
                jobs.append(job)
        except Exception as e:
            print(f"  HigherEdJobs error ({feed_url}): {e}")

    return jobs
