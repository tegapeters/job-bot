from .indeed import scrape_indeed
from .linkedin import scrape_linkedin
from .remotive import scrape_remotive
from .weworkremotely import scrape_weworkremotely
from .jobicy import scrape_jobicy


def scrape_all() -> list[dict]:
    results = {}

    sources = [
        ("Indeed",           scrape_indeed),
        ("LinkedIn",         scrape_linkedin),
        ("Remotive",         scrape_remotive),
        ("We Work Remotely", scrape_weworkremotely),
        ("Jobicy",           scrape_jobicy),
    ]

    for name, fn in sources:
        try:
            print(f"🔍 Scraping {name}...")
            jobs = fn()
            results[name] = jobs
            print(f"   → {len(jobs)} jobs")
        except Exception as e:
            print(f"   ⚠️  {name} failed: {e}")
            results[name] = []

    all_jobs = [j for jobs in results.values() for j in jobs]

    # Deduplicate by URL
    seen = set()
    unique = []
    for j in all_jobs:
        key = j.get("url") or j.get("id")
        if key and key not in seen:
            seen.add(key)
            unique.append(j)

    print(f"\n✅ Total unique jobs: {len(unique)}  "
          f"({' | '.join(f'{n}: {len(v)}' for n, v in results.items())})")
    return unique
