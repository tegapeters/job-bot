"""
Networking event scrapers.
Sources:
  - Meetup  (RSS per group — no auth, reliable)
  - Luma    (city page JSON — no auth)
"""
import hashlib
import json
import re
import feedparser
import requests
from datetime import datetime, timezone

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Known active Meetup groups per city
CITY_MEETUP_GROUPS: dict[str, list[tuple[str, str]]] = {
    "houston": [
        ("houston-data-science",     "Houston Data Science"),
        ("houston-machine-learning", "Houston Machine Learning"),
        ("Houston-Big-Data-Meetup",  "Houston Big Data"),
    ],
    "austin": [
        ("Austin-Data-Science",      "Austin Data Science"),
    ],
    # Add more cities here as groups are confirmed
}

DEFAULT_MEETUP_GROUPS = CITY_MEETUP_GROUPS["houston"]


def _make_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:16]


def _clean_html(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    for ent, ch in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " ")]:
        text = text.replace(ent, ch)
    text = re.sub(r"&#?\w+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:3000]


def _parse_date(raw: str) -> str:
    """Normalise various date strings to ISO format."""
    if not raw:
        return ""
    try:
        # feedparser gives RFC 2822 e.g. "Thu, 03 Jul 2026 18:00:00 +0000"
        import email.utils
        t = email.utils.parsedate_to_datetime(raw)
        return t.isoformat()
    except Exception:
        return raw


# ── Meetup ────────────────────────────────────────────────────────

def scrape_meetup_groups(
    groups: list[tuple[str, str]] | None = None,
    city: str = "Houston, TX",
) -> list[dict]:
    """Scrape upcoming events from a list of Meetup group slugs via RSS."""
    groups = groups or DEFAULT_MEETUP_GROUPS
    events: list[dict] = []
    seen: set[str] = set()

    for slug, group_name in groups:
        url = f"https://www.meetup.com/{slug}/events/rss/"
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                continue
            for entry in feed.entries:
                event_url = entry.get("link", "").strip()
                if not event_url or event_url in seen:
                    continue
                seen.add(event_url)

                title = entry.get("title", "").strip()
                if not title:
                    continue

                raw_summary = entry.get("summary", "")
                desc = _clean_html(raw_summary)

                # Try to extract venue from description
                venue_match = re.search(
                    r'(?:Location|Venue|Where)[:\s]+([^\n<]{5,80})', desc, re.IGNORECASE
                )
                location = venue_match.group(1).strip() if venue_match else city

                events.append({
                    "id": _make_id(event_url),
                    "source": "meetup",
                    "title": title,
                    "description": desc,
                    "start_date": _parse_date(entry.get("published", "")),
                    "location": location,
                    "url": event_url,
                    "organizer": group_name,
                    "status": "new",
                    "relevance_score": None,
                    "relevance_reason": "",
                })
        except Exception as e:
            print(f"  Meetup error ({slug}): {e}")

    return events


# ── Luma ─────────────────────────────────────────────────────────

def scrape_luma_city(city_slug: str = "houston") -> list[dict]:
    """Scrape featured events from a Luma city page."""
    events: list[dict] = []
    seen: set[str] = set()

    try:
        r = requests.get(f"https://lu.ma/{city_slug}", headers=HEADERS, timeout=12)
        nd = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
        if not nd:
            return []

        data = json.loads(nd.group(1))
        raw = data["props"]["pageProps"]["initialData"]["data"].get("events", [])

        for entry in raw:
            ev = entry.get("event") or {}
            slug_or_url = ev.get("url") or ev.get("slug", "")
            event_url = (
                slug_or_url if slug_or_url.startswith("http")
                else f"https://lu.ma/{slug_or_url}"
            )
            if not slug_or_url or event_url in seen:
                continue
            seen.add(event_url)

            title = (ev.get("name") or "").strip()
            if not title:
                continue

            start_at = entry.get("start_at") or ev.get("start_at", "")

            geo = ev.get("geo_address_json") or {}
            if isinstance(geo, str):
                try:
                    geo = json.loads(geo)
                except Exception:
                    geo = {}
            location = (
                geo.get("city")
                or geo.get("locality")
                or ev.get("location", "")
                or city_slug.title()
            )

            cal = entry.get("calendar") or {}
            organizer = cal.get("name", "") if isinstance(cal, dict) else ""

            events.append({
                "id": _make_id(event_url),
                "source": "luma",
                "title": title,
                "description": _clean_html(ev.get("description", ""))[:2000],
                "start_date": start_at,
                "location": location,
                "url": event_url,
                "organizer": organizer,
                "status": "new",
                "relevance_score": None,
                "relevance_reason": "",
            })
    except Exception as e:
        print(f"  Luma error: {e}")

    return events


# ── Main entry point ─────────────────────────────────────────────

def scrape_events(
    cities: list[str] | None = None,
    city: str = "Houston",  # kept for backward compat
) -> list[dict]:
    """Scrape networking events from all sources for one or more cities."""
    # Support both new multi-city list and old single-city string
    target_cities = cities if cities else [city]

    all_events: list[dict] = []
    seen: set[str] = set()

    for c in target_cities:
        city_key = c.lower().split(",")[0].strip()
        groups = CITY_MEETUP_GROUPS.get(city_key, [])

        if groups:
            print(f"  📅 Meetup — {c} ({len(groups)} groups)...")
            m = scrape_meetup_groups(groups, city=c)
            for e in m:
                if e["id"] not in seen:
                    seen.add(e["id"])
                    all_events.append(e)
            print(f"     → {len(m)} events")

        print(f"  📅 Luma — {city_key}...")
        lu = scrape_luma_city(city_key)
        for e in lu:
            if e["id"] not in seen:
                seen.add(e["id"])
                all_events.append(e)
        print(f"     → {len(lu)} events")

    print(f"  Total unique events: {len(all_events)}")
    return all_events
