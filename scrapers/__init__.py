from .indeed import scrape_indeed
from .linkedin import scrape_linkedin
from .remotive import scrape_remotive

def scrape_all() -> list[dict]:
    print("🔍 Scraping Indeed...")
    indeed = scrape_indeed()
    print(f"   → {len(indeed)} jobs")

    print("🔍 Scraping LinkedIn...")
    linkedin = scrape_linkedin()
    print(f"   → {len(linkedin)} jobs")

    print("🔍 Scraping Remotive...")
    remotive = scrape_remotive()
    print(f"   → {len(remotive)} jobs")

    all_jobs = indeed + linkedin + remotive

    # Deduplicate by URL
    seen = set()
    unique = []
    for j in all_jobs:
        if j["url"] not in seen:
            seen.add(j["url"])
            unique.append(j)

    print(f"\n✅ Total unique jobs found: {len(unique)}")
    return unique
