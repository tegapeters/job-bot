"""
Company research — DuckDuckGo instant answers + About page scrape.
Results are cached in Supabase (company_research table) so each company
is only fetched once. Builds a reusable knowledge base for future RAG.

Table (already created):
    company_research (
        company TEXT PRIMARY KEY,
        summary TEXT, about_text TEXT, website TEXT,
        funding TEXT, research_text TEXT,
        fetched_at TIMESTAMPTZ DEFAULT now()
    )
"""
import re
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from tracker import get_client

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
_TIMEOUT = 8

_SKIP_DOMAINS = (
    "linkedin.com", "indeed.com", "glassdoor", "facebook.com",
    "twitter.com", "x.com", "wikipedia.org", "bloomberg.com",
    "crunchbase.com", "ycombinator.com", "builtin.com", "ziprecruiter.com",
    "monster.com", "careerbuilder.com", "simplyhired.com",
)

_SKIP_PATHS = ("/careers", "/jobs", "/job/", "/open-positions", "/apply", "/hiring")


# ── Supabase cache ────────────────────────────────────────────────────

def _cache_key(company: str) -> str:
    return company.strip().lower()


def load_cached(company: str) -> dict | None:
    try:
        sb = get_client()
        res = sb.table("company_research").select("*").eq("company", _cache_key(company)).execute()
        if res.data:
            return res.data[0]
    except Exception:
        pass
    return None


def save_cached(company: str, data: dict) -> None:
    try:
        sb = get_client()
        from datetime import datetime, timezone
        sb.table("company_research").upsert({
            "company": _cache_key(company),
            **data,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="company").execute()
    except Exception:
        pass


# ── Search helpers ────────────────────────────────────────────────────

def _ddg_text(query: str, max_results: int = 5) -> list[dict]:
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception:
        return []


def _ddg_company_summary(company: str, job_title: str = "") -> dict:
    """Top DDG result for the company, disambiguated by job title if needed."""
    hint = f"{job_title} company" if job_title else "company"
    results = _ddg_text(f"{company} {hint} about")
    if not results:
        return {}
    # Prefer result whose URL looks like the company's own domain
    slug = re.sub(r"[^a-z0-9]", "", company.lower())
    for r in results:
        if slug[:6] in r.get("href", "").lower():
            return r
    return results[0]


def _find_homepage(company: str, job_title: str = "") -> str | None:
    hint = f"{job_title} " if job_title else ""
    results = _ddg_text(f"{hint}{company} official website", max_results=8)
    for r in results:
        url = r.get("href", "")
        if not url:
            continue
        if any(s in url for s in _SKIP_DOMAINS):
            continue
        if any(p in url for p in _SKIP_PATHS):
            continue
        return url.rstrip("/")
    return None


def _ddg_funding(company: str) -> str:
    """Try to find funding / valuation from DDG."""
    results = _ddg_text(f"{company} funding valuation raised", max_results=3)
    for r in results:
        body = r.get("body", "")
        # Look for dollar amounts
        if re.search(r"\$[\d,.]+\s*(million|billion|M|B)\b", body, re.I):
            snippet = re.sub(r"\s+", " ", body)
            return snippet[:300]
    return ""


# ── Scraper ───────────────────────────────────────────────────────────

def _scrape_about(url: str) -> str:
    """Scrape meaningful text from the company's homepage or /about page."""
    candidates = [url, f"{url}/about", f"{url}/about-us", f"{url}/company"]
    for candidate in candidates:
        try:
            resp = requests.get(candidate, headers=_HEADERS, timeout=_TIMEOUT,
                                allow_redirects=True)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["nav", "footer", "script", "style", "header", "aside",
                              "noscript", "iframe"]):
                tag.decompose()

            # Prefer an explicitly labelled about section
            about = (
                soup.find(id=re.compile(r"about", re.I))
                or soup.find(class_=re.compile(r"about|mission|story|who-we-are", re.I))
            )
            if about:
                text = re.sub(r"\s+", " ", about.get_text(" ", strip=True))
                if len(text) > 120:
                    return text[:1500]

            # Fall back to body paragraphs
            paras = [
                p.get_text(" ", strip=True)
                for p in soup.find_all("p")
                if len(p.get_text(strip=True)) > 60
            ]
            if paras:
                return re.sub(r"\s+", " ", " ".join(paras[:8]))[:1500]
        except Exception:
            continue
    return ""


# ── Public API ────────────────────────────────────────────────────────

def research_company(company: str, job_title: str = "", force_refresh: bool = False) -> dict:
    """
    Research a company. Returns a dict with keys:
        company, summary, about_text, website, funding, research_text
    Results are cached in Supabase. Pass force_refresh=True to re-scrape.
    """
    company = company.strip()
    if not company:
        return {}

    if not force_refresh:
        cached = load_cached(company)
        if cached:
            return cached

    # Fetch fresh
    ddg = _ddg_company_summary(company, job_title)
    homepage = _find_homepage(company, job_title)
    about_text = _scrape_about(homepage) if homepage else ""
    funding = _ddg_funding(company)

    summary = ddg.get("body", "")[:600] if ddg else ""
    if not summary and about_text:
        summary = about_text[:300]

    # Build the formatted text block for LLM injection
    parts = [f"[COMPANY RESEARCH: {company}]"]
    if summary:
        parts.append(f"Summary: {summary}")
    if homepage:
        parts.append(f"Website: {homepage}")
    if funding:
        parts.append(f"Funding/Valuation: {funding}")
    if about_text:
        parts.append(f"\nAbout (from their site):\n{about_text[:1000]}")

    research_text = "\n".join(parts)

    data = {
        "company": _cache_key(company),
        "summary": summary,
        "about_text": about_text,
        "website": homepage or "",
        "funding": funding,
        "research_text": research_text,
    }
    save_cached(company, data)
    return data
