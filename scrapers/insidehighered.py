"""
Inside Higher Ed Careers — keyword-searchable RSS (Madgex platform, free/no auth).

The Madgex job platform behind Inside Higher Ed Careers exposes an RSS feed
whose results follow the ?keywords= query. We build one feed URL per target
role (capped) and merge the results. The feed template lives in
config.INSIDEHIGHERED_FEED_TEMPLATE (override with the ACADEMIC_FEED_INSIDEHIGHERED
env var).

Chosen over Chronicle for the first academic release because its RSS is
keyword-query-friendly; a Chronicle scraper can be added the same way (its own
module reading a feed URL from config) once its feed is verified.

Live fetch cannot be verified from the dev sandbox (egress is locked down); it
runs against the real feed in the deployed app.
"""
import feedparser
from urllib.parse import quote_plus

from config import INSIDEHIGHERED_FEED_TEMPLATE, ACADEMIC_ROLES
from ._academic import entry_to_job, is_excluded, matches_roles

_MAX_QUERIES = 4


def _queries(target_roles: list[str] | None) -> list[str]:
    roles = target_roles or ACADEMIC_ROLES
    seen: set[str] = set()
    out: list[str] = []
    for r in roles:
        q = (r or "").strip().lower()
        if q and q not in seen:
            seen.add(q)
            out.append(r.strip())
        if len(out) >= _MAX_QUERIES:
            break
    return out


def scrape_insidehighered(target_roles: list[str] = None,
                          locations: list[str] = None) -> list[dict]:
    jobs: list[dict] = []
    seen: set[str] = set()

    for query in _queries(target_roles):
        feed_url = INSIDEHIGHERED_FEED_TEMPLATE.format(query=quote_plus(query))
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                job = entry_to_job(entry, source="insidehighered")
                if job is None:
                    continue
                if job["id"] in seen:
                    continue
                if is_excluded(job["title"], job["description"]):
                    continue
                # The keyword feed already filters server-side; keep a light
                # client-side faculty check to drop obvious staff/admin noise.
                if not matches_roles(job["title"], target_roles):
                    continue
                seen.add(job["id"])
                jobs.append(job)
        except Exception as e:
            print(f"  Inside Higher Ed error (query={query!r}): {e}")

    return jobs
