from .linkedin import scrape_linkedin
from .remotive import scrape_remotive
from .weworkremotely import scrape_weworkremotely
from .jobicy import scrape_jobicy
from .remoteok import scrape_remoteok
from .adzuna import scrape_adzuna
from .usajobs import scrape_usajobs
from .themuse import scrape_themuse
from .google_jobs import scrape_google_jobs
from .handshake import scrape_handshake
from .higheredjobs import scrape_higheredjobs
from .insidehighered import scrape_insidehighered
import inspect
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import ACADEMIC_TITLE_KEYWORDS

# Short words that carry no meaning for role matching
_STOPWORDS = {"and", "or", "the", "for", "of", "in", "at", "a", "an", "to", "by",
              "with", "from", "as", "is", "it", "be", "on", "up", "new", "we"}


def _role_keywords(role: str) -> list[str]:
    """Extract meaningful keywords from a role string (len >= 2, not a stopword)."""
    words = re.sub(r"[^a-z0-9 ]", " ", role.lower()).split()
    return [w for w in words if len(w) >= 2 and w not in _STOPWORDS]


def _title_matches_roles(title: str, roles: list[str], vertical: str = "tech") -> bool:
    """
    Return True if the job title matches at least one target role.

    Match strategy (either condition is sufficient):
    1. Full role phrase in title  (e.g. "data engineer" in "senior data engineer")
    2. ≥60% of role keywords in title (handles word-order differences and abbreviations)
       e.g. role "ICU Registered Nurse" → keywords ["icu","registered","nurse"]
            title "Registered Nurse ICU" matches on all 3 keywords

    Academic mode: any generic faculty keyword (professor/adjunct/lecturer/…)
    also counts as a match, so discipline-specific target roles don't drop
    legitimate faculty titles.
    """
    if not roles:
        return True
    t = title.lower()
    if vertical == "academic" and any(kw in t for kw in ACADEMIC_TITLE_KEYWORDS):
        return True
    for role in roles:
        if role.lower() in t:
            return True
        keywords = _role_keywords(role)
        if not keywords:
            continue
        hits = sum(1 for kw in keywords if kw in t)
        if hits >= max(1, round(len(keywords) * 0.6)):
            return True
    return False


_REMOTE_ONLY_SOURCES = {"RemoteOK", "Remotive", "We Work Remotely", "Jobicy"}


def _wants_remote(locations: list[str] | None) -> bool:
    """True if the user's location list includes a remote/nationwide option, or is unset."""
    if not locations:
        return True  # no preference = include everything
    return any(l.lower() in ("remote", "united states", "us", "anywhere") for l in locations)


def scrape_all(target_roles: list[str] = None, min_salary: int = 0,
               locations: list[str] | None = None,
               vertical: str = "tech") -> list[dict]:
    results = {}

    include_remote = _wants_remote(locations)

    if vertical == "academic":
        # Higher-ed faculty vertical: academic boards only. Remote-only tech
        # boards and the generic tech sources don't carry faculty postings.
        sources = [
            ("HigherEdJobs",     scrape_higheredjobs),
            ("Inside Higher Ed", scrape_insidehighered),
        ]
    else:
        sources = [
            ("LinkedIn",         scrape_linkedin),
            ("Google Jobs",      scrape_google_jobs),
            ("RemoteOK",         scrape_remoteok),
            ("Remotive",         scrape_remotive),
            ("We Work Remotely", scrape_weworkremotely),
            ("Jobicy",           scrape_jobicy),
            ("Adzuna",           scrape_adzuna),
            ("USAJobs",          scrape_usajobs),
            ("The Muse",         scrape_themuse),
        ]

    # Skip remote-only boards when user explicitly wants onsite/hybrid cities only
    if not include_remote:
        skipped = [n for n, _ in sources if n in _REMOTE_ONLY_SOURCES]
        sources = [(n, fn) for n, fn in sources if n not in _REMOTE_ONLY_SOURCES]
        print(f"   📍 Location filter active — skipping remote-only sources: {', '.join(skipped)}")

    def _run_scraper(name: str, fn) -> tuple[str, list[dict]]:
        print(f"🔍 Scraping {name}...")
        sig = inspect.signature(fn).parameters
        kwargs = {}
        if "target_roles" in sig:
            kwargs["target_roles"] = target_roles
        if "min_salary" in sig:
            kwargs["min_salary"] = min_salary
        if "locations" in sig:
            kwargs["locations"] = locations or []
        jobs = fn(**kwargs)
        # Backfill work_type for sources that don't set it themselves
        _remote_sources = {"RemoteOK", "Remotive", "We Work Remotely", "Jobicy"}
        _onsite_sources = {"USAJobs"}
        for j in jobs:
            if "work_type" not in j or not j["work_type"]:
                if name in _remote_sources:
                    j["work_type"] = "remote"
                elif name in _onsite_sources:
                    j["work_type"] = "onsite"
                else:
                    # Adzuna, Indeed, The Muse — infer from location field
                    loc = (j.get("location") or "").lower()
                    if "remote" in loc or "anywhere" in loc:
                        j["work_type"] = "remote"
                    elif loc and loc not in ("", "united states", "us"):
                        j["work_type"] = "onsite"
                    else:
                        j["work_type"] = "unknown"
        print(f"   → {name}: {len(jobs)} jobs")
        return name, jobs

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_run_scraper, name, fn): name for name, fn in sources}
        for future in as_completed(futures):
            name = futures[future]
            try:
                n, jobs = future.result()
                results[n] = jobs
            except Exception as e:
                print(f"   ⚠️  {name} failed: {e}")
                results[name] = []

    all_jobs = [j for jobs in results.values() for j in jobs]

    # ── Dedup by URL ──────────────────────────────────────────────
    seen_urls: set[str] = set()
    url_unique = []
    for j in all_jobs:
        key = j.get("url") or j.get("id")
        if key and key not in seen_urls:
            seen_urls.add(key)
            url_unique.append(j)

    # ── Cross-source dedup by (title, company) ────────────────────
    # Same role posted on LinkedIn, Google Jobs, Indeed etc. will have
    # different URLs but identical title+company. Keep whichever copy
    # has the longest description (most detail for scoring).
    tc_best: dict[tuple, dict] = {}
    for j in url_unique:
        key = (
            (j.get("title") or "").lower().strip(),
            (j.get("company") or "").lower().strip(),
        )
        existing = tc_best.get(key)
        if existing is None or len(j.get("description") or "") > len(existing.get("description") or ""):
            tc_best[key] = j
    unique = list(tc_best.values())

    cross_dupes = len(url_unique) - len(unique)
    if cross_dupes:
        print(f"   🔁 Cross-source dedup removed {cross_dupes} duplicate(s) (same title+company, different source)")

    # ── Strict role enforcement (safety net) ─────────────────────
    if target_roles:
        before = len(unique)
        unique = [j for j in unique if _title_matches_roles(j.get("title", ""), target_roles, vertical=vertical)]
        removed = before - len(unique)
        if removed:
            print(f"   🎯 Role filter removed {removed} off-target jobs")

    print(f"\n✅ Total unique jobs after role filter: {len(unique)}  "
          f"({' | '.join(f'{n}: {len(v)}' for n, v in results.items())})")
    return unique
