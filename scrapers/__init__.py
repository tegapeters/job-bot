from .linkedin import scrape_linkedin
from .remotive import scrape_remotive
from .weworkremotely import scrape_weworkremotely
from .jobicy import scrape_jobicy
from .remoteok import scrape_remoteok
import inspect
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# Short words that carry no meaning for role matching
_STOPWORDS = {"and", "or", "the", "for", "of", "in", "at", "a", "an", "to", "by",
              "with", "from", "as", "is", "it", "be", "on", "up", "new", "we"}


def _role_keywords(role: str) -> list[str]:
    """Extract meaningful keywords from a role string (len >= 2, not a stopword)."""
    words = re.sub(r"[^a-z0-9 ]", " ", role.lower()).split()
    return [w for w in words if len(w) >= 2 and w not in _STOPWORDS]


def _title_matches_roles(title: str, roles: list[str]) -> bool:
    """
    Return True if the job title matches at least one target role.

    Match strategy (either condition is sufficient):
    1. Full role phrase in title  (e.g. "data engineer" in "senior data engineer")
    2. ≥60% of role keywords in title (handles word-order differences and abbreviations)
       e.g. role "ICU Registered Nurse" → keywords ["icu","registered","nurse"]
            title "Registered Nurse ICU" matches on all 3 keywords
    """
    if not roles:
        return True
    t = title.lower()
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


def scrape_all(target_roles: list[str] = None, min_salary: int = 0) -> list[dict]:
    results = {}

    sources = [
        ("LinkedIn",         scrape_linkedin),
        ("RemoteOK",         scrape_remoteok),
        ("Remotive",         scrape_remotive),
        ("We Work Remotely", scrape_weworkremotely),
        ("Jobicy",           scrape_jobicy),
    ]

    def _run_scraper(name: str, fn) -> tuple[str, list[dict]]:
        print(f"🔍 Scraping {name}...")
        sig = inspect.signature(fn).parameters
        kwargs = {}
        if "target_roles" in sig:
            kwargs["target_roles"] = target_roles
        if "min_salary" in sig:
            kwargs["min_salary"] = min_salary
        jobs = fn(**kwargs)
        print(f"   → {name}: {len(jobs)} jobs")
        return name, jobs

    with ThreadPoolExecutor(max_workers=5) as pool:
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
    unique = []
    for j in all_jobs:
        key = j.get("url") or j.get("id")
        if key and key not in seen_urls:
            seen_urls.add(key)
            unique.append(j)

    # ── Strict role enforcement (safety net) ─────────────────────
    if target_roles:
        before = len(unique)
        unique = [j for j in unique if _title_matches_roles(j.get("title", ""), target_roles)]
        removed = before - len(unique)
        if removed:
            print(f"   🎯 Role filter removed {removed} off-target jobs")

    print(f"\n✅ Total unique jobs after role filter: {len(unique)}  "
          f"({' | '.join(f'{n}: {len(v)}' for n, v in results.items())})")
    return unique
