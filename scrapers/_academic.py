"""
Shared helpers for higher-ed (academic) job scrapers.

Academic postings differ from tech listings in ways the generic pipeline
doesn't capture: the meaningful signal is faculty *rank* and *appointment
type*, not remote/hybrid/onsite work arrangement or a salary band. These
helpers parse a standard RSS entry into the pipeline's job dict shape and
enrich it with `rank` and `appointment_type` extracted from the title/body.

Kept in one module (rather than duplicated per scraper, as the tech scrapers
do for trivial helpers) because the rank/appointment extraction is non-trivial
and both academic scrapers need identical behavior.
"""
import hashlib
import re
from datetime import datetime

from config import ACADEMIC_EXCLUDE_TERMS, ACADEMIC_TITLE_KEYWORDS


def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def is_excluded(title: str, desc: str) -> bool:
    """Academic-mode exclusions only (NOT the tech 'junior/entry-level' list —
    an entry-rank faculty role is still a valid match)."""
    text = (title + " " + desc).lower()
    return any(kw in text for kw in ACADEMIC_EXCLUDE_TERMS)


def matches_roles(title: str, target_roles: list[str] | None) -> bool:
    """True if the title looks like a faculty role the user wants.

    Matches when the title contains any target-role phrase OR any generic
    faculty keyword (professor/lecturer/adjunct/…). Discipline-only target
    roles (e.g. 'Statistics') still match via substring."""
    t = (title or "").lower()
    if any(kw in t for kw in ACADEMIC_TITLE_KEYWORDS):
        return True
    if not target_roles:
        return False
    return any((r or "").lower() in t for r in target_roles)


# Rank detection — order matters (check most specific first).
_RANK_PATTERNS: list[tuple[str, str]] = [
    (r"\badjunct\b",                              "Adjunct"),
    (r"\bvisiting\b",                             "Visiting"),
    (r"\b(post[- ]?doc(toral)?|postdoc)\b",       "Postdoc"),
    (r"\bfull professor\b",                       "Full"),
    (r"\bassociate professor\b",                  "Associate"),
    (r"\bassistant professor\b",                  "Assistant"),
    (r"\b(lecturer|senior lecturer)\b",           "Lecturer"),
    (r"\binstructor\b",                           "Instructor"),
    (r"\bprofessor\b",                            "Professor"),  # generic fallback
]


def extract_rank(title: str, desc: str = "") -> str:
    """Best-effort faculty rank from the title (falls back to description)."""
    hay = f"{title or ''} {desc or ''}".lower()
    for pat, label in _RANK_PATTERNS:
        if re.search(pat, hay):
            return label
    return "Unknown"


def extract_appointment_type(title: str, desc: str = "") -> str:
    """Appointment type: Adjunct / Part-time / Full-time / Tenure-track / Visiting."""
    hay = f"{title or ''} {desc or ''}".lower()
    if "adjunct" in hay:
        return "Adjunct"
    if "tenure-track" in hay or "tenure track" in hay:
        return "Tenure-track"
    if "visiting" in hay:
        return "Visiting"
    if re.search(r"\bpart[- ]?time\b", hay):
        return "Part-time"
    if re.search(r"\bfull[- ]?time\b", hay):
        return "Full-time"
    return "Unknown"


def entry_to_job(entry: dict, source: str) -> dict | None:
    """Convert a feedparser RSS entry to the pipeline job dict shape.

    Returns None if the entry lacks a usable URL. The institution goes in the
    `company` field (the pipeline's employer slot); rank/appointment_type are
    added as academic-specific extras that downstream code reads when present.
    """
    url = entry.get("link", "") or ""
    if not url:
        return None

    raw_title = (entry.get("title", "") or "").strip()
    summary = entry.get("summary", "") or entry.get("description", "") or ""
    # Strip HTML tags feedparser may leave in the summary.
    desc = re.sub(r"<[^>]+>", " ", summary)
    desc = re.sub(r"\s+", " ", desc).strip()

    # Institution: prefer explicit RSS fields; fall back to "Institution: Title"
    # pattern that Inside Higher Ed uses in its title field.
    company = (entry.get("author", "") or entry.get("publisher", "") or "").strip()
    if ":" in raw_title and not company:
        company, _, raw_title = raw_title.partition(":")
        company = company.strip()
        raw_title = raw_title.strip()
    title = raw_title

    # Location: feeds vary; try common fields, else leave blank.
    location = (entry.get("location", "") or "").strip()

    return {
        "id": make_id(url),
        "source": source,
        "title": title,
        "company": company or "Unknown institution",
        "location": location,
        "url": url,
        "description": desc[:5000],
        "posted_at": entry.get("published", datetime.utcnow().isoformat()),
        "status": "new",
        "score": None,
        "cover_letter": None,
        "rank": extract_rank(title, desc),
        "appointment_type": extract_appointment_type(title, desc),
        # Work arrangement is not meaningful for faculty roles; mark explicitly
        # so scrape_all's backfill leaves it alone.
        "work_type": "onsite",
    }
