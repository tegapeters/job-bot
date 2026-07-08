"""
Jobicy — free public REST API, no auth required
Remote-first, US jobs, full descriptions, salary data included
Docs: https://jobi.cy/apidocs
"""
import hashlib
import requests
from datetime import datetime
from config import EXCLUDE_KEYWORDS, MIN_SALARY

API = "https://jobicy.com/api/v2/remote-jobs"

LEVEL_BLOCKLIST = ["junior", "entry", "intern"]

# Maps role/profession keywords → Jobicy API tag slugs (verified working).
# Used to derive per-user tags from their target_roles instead of hardcoding.
_TAG_MAP: dict[str, str] = {
    # Data / tech
    "data":            "data",
    "analyst":         "analytics",
    "analytics":       "analytics",
    "engineer":        "data",
    "scientist":       "data",
    "python":          "python",
    "machine learning":"data",
    "ml ":             "data",
    " ai ":            "data",
    "genai":           "data",
    "generative":      "data",
    "intelligence":    "analytics",
    # Business / ops
    "business":        "business",
    "operations":      "operations",
    "consultant":      "consulting",
    "consulting":      "consulting",
    "product":         "product",
    "program manager": "operations",
    "project manager": "operations",
    "systems analyst": "business",
    # Finance
    "finance":         "finance",
    "accounting":      "accounting",
    "accountant":      "accounting",
    "financial":       "finance",
    # Sales / marketing
    "sales":           "sales",
    "marketing":       "marketing",
    "growth":          "marketing",
    "content":         "writing",
    "copywriter":      "writing",
    "writing":         "writing",
    # CRM / Salesforce
    "salesforce":      "salesforce",
    "crm":             "salesforce",
    # Design
    "design":          "design",
    "ux":              "design",
    "ui ":             "design",
    # Legal
    "legal":           "legal",
    "attorney":        "legal",
    "lawyer":          "legal",
    "paralegal":       "legal",
    # Healthcare
    "healthcare":      "healthcare",
    "medical":         "healthcare",
    "nurse":           "healthcare",
    "clinical":        "healthcare",
    # HR
    "recruiting":      "operations",
    "talent":          "operations",
    "human resources": "operations",
}

_FALLBACK_TAGS = ["data", "analytics", "business"]


def _derive_tags(target_roles: list[str] | None) -> list[str]:
    """Derive up to 4 Jobicy tag slugs from the user's target roles."""
    if not target_roles:
        return _FALLBACK_TAGS
    seen: set[str] = set()
    tags: list[str] = []
    for role in target_roles:
        role_l = f" {role.lower()} "  # word-boundary padding
        for keyword, tag in _TAG_MAP.items():
            if keyword in role_l and tag not in seen:
                seen.add(tag)
                tags.append(tag)
        if len(tags) >= 4:
            break
    return tags if tags else _FALLBACK_TAGS


def _make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _matches_target(title: str, target_roles: list[str] | None) -> bool:
    t = title.lower()
    if not target_roles:
        return True
    return any(r.lower() in t for r in target_roles)


def _is_excluded(title: str, desc: str) -> bool:
    text = (title + " " + desc).lower()
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


def _is_junior(title: str, level: str) -> bool:
    t = (title + " " + (level or "")).lower()
    return any(s in t for s in LEVEL_BLOCKLIST)


def scrape_jobicy(max_results: int = 50, target_roles: list[str] = None, min_salary: int = 0) -> list[dict]:
    jobs = []
    seen = set()
    tags = _derive_tags(target_roles)

    for tag in tags:
        try:
            resp = requests.get(
                API,
                params={"count": max_results, "geo": "usa", "tag": tag},
                timeout=12,
            )
            if resp.status_code != 200:
                print(f"  Jobicy: HTTP {resp.status_code} (tag={tag})")
                continue

            data = resp.json().get("jobs", [])
            for j in data:
                title = j.get("jobTitle", "")
                level = j.get("jobLevel", "")
                url = j.get("url", "")
                desc = j.get("jobDescription", "")
                excerpt = j.get("jobExcerpt", "")

                if not _matches_target(title, target_roles=target_roles):
                    continue
                if _is_excluded(title, desc):
                    continue
                if _is_junior(title, level):
                    continue

                # Salary gate — only apply if user has set a floor
                effective_min = min_salary or 0
                salary_min = j.get("salaryMin")
                if salary_min and effective_min and int(salary_min) < effective_min:
                    continue

                job_id = _make_id(url)
                if job_id in seen:
                    continue
                seen.add(job_id)

                jobs.append({
                    "id": job_id,
                    "source": "jobicy",
                    "title": title,
                    "company": j.get("companyName", ""),
                    "location": j.get("jobGeo", "Remote"),
                    "url": url,
                    "description": desc or excerpt,
                    "posted_at": j.get("pubDate", datetime.utcnow().isoformat()),
                    "status": "new",
                    "score": None,
                    "cover_letter": None,
                    "salary_range": f"${salary_min:,}–${j['salaryMax']:,}" if salary_min and j.get("salaryMax") else None,
                })
        except Exception as e:
            print(f"  Jobicy error (tag={tag}): {e}")

    return jobs
