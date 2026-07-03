"""
Networking event scrapers.
Sources:
  - Meetup     (RSS per group — no auth, reliable)
  - Luma       (city page JSON — no auth)
  - Eventbrite (ld+json structured data — no auth)
"""
import hashlib
import json
import re
import feedparser
import requests
from datetime import datetime, timezone

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Known active Meetup groups per city (verified to have upcoming events)
CITY_MEETUP_GROUPS: dict[str, list[tuple[str, str]]] = {
    "houston": [
        ("houston-data-science",       "Houston Data Science"),
        ("houston-machine-learning",   "Houston Machine Learning"),
        ("Houston-Big-Data-Meetup",    "Houston Big Data"),
        ("ai-professionals-houston",   "AI Professionals Houston"),
    ],
    "austin": [
        ("Austin-Data-Science",        "Austin Data Science"),
    ],
}

# Eventbrite categories to scrape per city slug
EVENTBRITE_CATEGORIES = [
    "professional-networking",
    "technology",
    "business",
]

# Words in Meetup event titles that signal virtual/global cross-posts
_VIRTUAL_SIGNALS = frozenset([
    "virtual", "global", "worldwide", "online", "webinar", "zoom", "around the world",
])

# City slug normalisation: bare city name → (luma_slug, eb_state, eb_slug)
# Add entries here as new cities are supported.
CITY_SLUG_MAP: dict[str, dict[str, str]] = {
    "houston":       {"luma": "houston",       "eb_state": "tx", "eb_slug": "houston"},
    "austin":        {"luma": "austin",         "eb_state": "tx", "eb_slug": "austin"},
    "dallas":        {"luma": "dallas",         "eb_state": "tx", "eb_slug": "dallas"},
    "san antonio":   {"luma": "san-antonio",    "eb_state": "tx", "eb_slug": "san-antonio"},
    "new york":      {"luma": "nyc",            "eb_state": "ny", "eb_slug": "new-york-city"},
    "los angeles":   {"luma": "los-angeles",    "eb_state": "ca", "eb_slug": "los-angeles"},
    "chicago":       {"luma": "chicago",        "eb_state": "il", "eb_slug": "chicago"},
    "atlanta":       {"luma": "atlanta",        "eb_state": "ga", "eb_slug": "atlanta"},
    "marietta":      {"luma": "atlanta",        "eb_state": "ga", "eb_slug": "atlanta"},
    "seattle":       {"luma": "seattle",        "eb_state": "wa", "eb_slug": "seattle"},
    "san francisco": {"luma": "sf",             "eb_state": "ca", "eb_slug": "san-francisco"},
    "miami":         {"luma": "miami",          "eb_state": "fl", "eb_slug": "miami"},
    "boston":        {"luma": "boston",         "eb_state": "ma", "eb_slug": "boston"},
    "denver":        {"luma": "denver",         "eb_state": "co", "eb_slug": "denver"},
    "washington":    {"luma": "dc",             "eb_state": "dc", "eb_slug": "washington-dc"},
}

# Max per-city Luma page-fetch enrichment calls (caps sequential HTTP blocking)
_LUMA_ENRICH_LIMIT = 5

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

                # Skip virtual/global events cross-posted into local groups
                if any(w in title.lower() for w in _VIRTUAL_SIGNALS):
                    continue

                raw_summary = entry.get("summary", "")
                desc = _clean_html(raw_summary)

                # Also skip if description signals virtual attendance
                if any(w in desc[:500].lower() for w in _VIRTUAL_SIGNALS):
                    continue

                venue_match = re.search(
                    r'(?:Location|Venue|Where)[:\s]+([^\n<]{5,80})', desc, re.IGNORECASE
                )
                extracted = venue_match.group(1).strip() if venue_match else ""
                # Sanity-check extracted location: must contain a digit or comma
                # (real addresses do; garbage prose matches don't)
                location = extracted if extracted and re.search(r'[\d,]', extracted) else city

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
    """Scrape featured events from a Luma city page, enriching with full descriptions."""
    events: list[dict] = []
    seen: set[str] = set()
    enrich_count = 0  # cap sequential HTTP enrichment calls

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

            # Prefer description from the city page; enrich from event page if short
            desc = _clean_html(ev.get("description", ""))
            if (not desc or len(desc) < 80) and enrich_count < _LUMA_ENRICH_LIMIT:
                fetched = _fetch_luma_description(event_url)
                if fetched:
                    desc = fetched
                enrich_count += 1

            events.append({
                "id": _make_id(event_url),
                "source": "luma",
                "title": title,
                "description": desc[:2000],
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


def _fetch_luma_description(event_url: str) -> str:
    """Fetch the full description from an individual Luma event page."""
    try:
        r = requests.get(event_url, headers=HEADERS, timeout=10)
        nd = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
        if not nd:
            return ""
        data = json.loads(nd.group(1))
        # Walk common paths for event description
        pp = data.get("props", {}).get("pageProps", {})
        ev = pp.get("initialData", {}).get("data", {}).get("event") or pp.get("event") or {}
        desc = ev.get("description", "") or ev.get("desc", "")
        return _clean_html(desc)[:2000]
    except Exception:
        return ""


# ── Eventbrite ────────────────────────────────────────────────────

def scrape_eventbrite_city(city_slug: str = "houston", state: str = "tx") -> list[dict]:
    """Scrape professional/tech/business events from Eventbrite via ld+json."""
    events: list[dict] = []
    seen: set[str] = set()

    for category in EVENTBRITE_CATEGORIES:
        url = f"https://www.eventbrite.com/d/{state}--{city_slug}/{category}/"
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            ld_blocks = re.findall(
                r'<script type="application/ld\+json">(.*?)</script>', r.text, re.DOTALL
            )
            for block in ld_blocks:
                try:
                    data = json.loads(block)
                    if data.get("@type") != "ItemList":
                        continue
                    for item in data.get("itemListElement", []):
                        ev = item.get("item", item)
                        event_url = ev.get("url", "").strip()
                        if not event_url or event_url in seen:
                            continue
                        seen.add(event_url)

                        title = (ev.get("name") or "").strip()
                        if not title:
                            continue

                        # Skip online-only events
                        mode = ev.get("eventAttendanceMode", "")
                        if "Online" in mode:
                            continue

                        loc_data = ev.get("location") or {}
                        addr = loc_data.get("address") or {}
                        location = ", ".join(filter(None, [
                            loc_data.get("name", ""),
                            addr.get("addressLocality", ""),
                            addr.get("addressRegion", ""),
                        ])) or city_slug.title()

                        events.append({
                            "id": _make_id(event_url),
                            "source": "eventbrite",
                            "title": title,
                            "description": _clean_html(ev.get("description", ""))[:2000],
                            "start_date": ev.get("startDate", ""),
                            "location": location,
                            "url": event_url,
                            "organizer": "",
                            "status": "new",
                            "relevance_score": None,
                            "relevance_reason": "",
                        })
                except Exception:
                    continue
        except Exception as e:
            print(f"  Eventbrite error ({category}): {e}")

    return events


# ── Main entry point ─────────────────────────────────────────────

def scrape_events(
    cities: list[str] | None = None,
    city: str = "Houston",  # kept for backward compat
) -> list[dict]:
    """Scrape networking events from all sources for one or more cities."""
    target_cities = cities if cities else [city]

    all_events: list[dict] = []
    seen: set[str] = set()

    for c in target_cities:
        city_key = c.lower().split(",")[0].strip()
        slugs = CITY_SLUG_MAP.get(city_key)

        groups = CITY_MEETUP_GROUPS.get(city_key, [])
        if groups:
            print(f"  📅 Meetup — {c} ({len(groups)} groups)...")
            meetup_before = len(all_events)
            for e in scrape_meetup_groups(groups, city=c):
                if e["id"] not in seen:
                    seen.add(e["id"])
                    all_events.append(e)
            print(f"     → {len(all_events) - meetup_before} events")

        luma_slug = slugs["luma"] if slugs else city_key.replace(" ", "-")
        print(f"  📅 Luma — {luma_slug}...")
        luma_before = len(all_events)
        for e in scrape_luma_city(luma_slug):
            if e["id"] not in seen:
                seen.add(e["id"])
                all_events.append(e)
        print(f"     → {len(all_events) - luma_before} events")

        if slugs:
            eb_slug = slugs["eb_slug"]
            eb_state = slugs["eb_state"]
        else:
            print(f"  ⚠️  No Eventbrite config for '{city_key}' — skipping (add to CITY_SLUG_MAP)")
            eb_slug = eb_state = None

        if eb_slug:
            print(f"  📅 Eventbrite — {eb_slug}...")
            eb_before = len(all_events)
            for e in scrape_eventbrite_city(city_slug=eb_slug, state=eb_state):
                if e["id"] not in seen:
                    seen.add(e["id"])
                    all_events.append(e)
            print(f"     → {len(all_events) - eb_before} events")

    print(f"  Total unique events: {len(all_events)}")
    return all_events
