"""
Fetches full job descriptions and company names from LinkedIn job pages.
Called for qualifying jobs (score 7+) before cover letter generation.
"""
import re
import time
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _clean(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#?\w+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_linkedin_job(url: str) -> dict:
    """Returns {description, company} scraped from a LinkedIn job page."""
    result = {"description": "", "company": ""}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return result
        html = resp.text

        # Company name
        company_match = re.search(
            r'class="[^"]*topcard__org-name-link[^"]*"[^>]*>(.*?)</a>',
            html, re.DOTALL
        )
        if not company_match:
            company_match = re.search(
                r'"companyName"\s*:\s*"([^"]+)"', html
            )
        if company_match:
            result["company"] = _clean(company_match.group(1))

        # Job description — LinkedIn wraps it in a specific div
        desc_match = re.search(
            r'class="[^"]*description__text[^"]*"[^>]*>(.*?)</div>',
            html, re.DOTALL
        )
        if not desc_match:
            # Fallback: JSON-LD description field
            desc_match = re.search(r'"description"\s*:\s*\{"value"\s*:\s*"(.*?)"', html)
        if desc_match:
            result["description"] = _clean(desc_match.group(1))[:4000]

    except Exception as e:
        print(f"  Fetch error ({url[:60]}): {e}")
    return result


def enrich_jobs(jobs: list[dict]) -> list[dict]:
    """Fetch full descriptions + company names for a list of jobs."""
    print(f"\n🌐 Fetching full descriptions for {len(jobs)} qualifying jobs...")
    for i, job in enumerate(jobs):
        url = job.get("url", "")
        if not url:
            continue
        print(f"  [{i+1}/{len(jobs)}] {job['title'][:50]}")
        data = fetch_linkedin_job(url)
        if data["description"]:
            job["description"] = data["description"]
        if data["company"] and not job.get("company"):
            job["company"] = data["company"]
        time.sleep(1.0)
    return jobs
