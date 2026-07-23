"""
Gmail inbox scanner — IMAP-based.

Scans the inbox of the email address you use to apply for jobs and
categorises matching emails into three buckets:
  - interview   : invitation to interview or advance in the process
  - action       : assessment, scheduling link, or reply needed
  - rejection    : declined / not moving forward

Credentials are NEVER persisted — they live only in memory for the session.
To use, you need a Gmail App Password:
  https://myaccount.google.com/apppasswords
"""
import imaplib
import email as _email_lib
import re
from datetime import datetime, timedelta
from email.header import decode_header as _decode_header

# ── Signal phrase lists ────────────────────────────────────────────────────────

REJECTION_PHRASES = [
    "not moving forward",
    "will not be moving forward",
    "decided not to move forward",
    "decided to move forward with other",
    "decided to pursue other",
    "chosen to move forward with other",
    "regret to inform",
    "regret to let you know",
    "not selected",
    "not the right fit",
    "position has been filled",
    "filled the position",
    "we have decided",
    "we've decided",
    "went with another",
    "other candidates",
    "no longer considering",
    "your application was not",
    "unfortunately, we",
    "unfortunately we",
    "after careful consideration",
]

# More specific phrases first — avoids false positives on "next steps" alone
INTERVIEW_PHRASES = [
    "invite you to interview",
    "invited to interview",
    "schedule an interview",
    "schedule a call",
    "schedule time to speak",
    "schedule a phone",
    "schedule a video",
    "like to set up",
    "would like to connect",
    "moving you forward",
    "moving forward with your",
    "selected you to move forward",
    "excited to move forward with you",
    "pleased to move forward",
    "advance to the next",
    "advance to the interview",
    "next round",
    "next step",
    "congratulations on moving",
    "you have been selected",
    "we'd love to chat",
    "we would love to chat",
    "let's find a time",
]

ACTION_PHRASES = [
    "please complete the following",
    "complete the assessment",
    "complete this assessment",
    "online assessment",
    "take-home assignment",
    "take home assignment",
    "coding challenge",
    "technical assessment",
    "technical screen",
    "skills assessment",
    "please reply",
    "kindly respond",
    "respond by",
    "action required",
    "response required",
    "reply by",
    "please schedule",
    "book a time",
    "book time",
    "use the link below to schedule",
    "calendly",
    "please confirm your availability",
    "confirm your attendance",
    "complete by",
]

# IMAP search terms — broad enough to pull candidates, phrase lists above do
# the precise filtering. Keep these short — IMAP BODY search is substring.
_IMAP_SEARCH_TERMS: dict[str, list[str]] = {
    "rejection": [
        "not moving forward",
        "regret to inform",
        "not selected",
        "unfortunately",
        "decided to pursue",
        "position has been filled",
        "after careful consideration",
    ],
    "interview": [
        "invite you to interview",
        "schedule an interview",
        "schedule a call",
        "moving forward with you",
        "next round",
        "next step",
    ],
    "action": [
        "complete the assessment",
        "online assessment",
        "coding challenge",
        "take-home",
        "action required",
        "please schedule",
        "calendly",
        "respond by",
    ],
}

_ATS_DOMAINS = {
    "greenhouse.io", "lever.co", "workday.com", "ashbyhq.com",
    "breezy.hr", "smartrecruiters.com", "jobvite.com", "icims.com",
    "taleo.net", "successfactors.com", "recruiterbox.com", "rippling.com",
    "myworkdayjobs.com", "bamboohr.com", "hiring.workable.com",
}


def _decode_str(value) -> str:
    if value is None:
        return ""
    parts = _decode_header(value)
    out = []
    for part, enc in parts:
        if isinstance(part, bytes):
            out.append(part.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(str(part))
    return " ".join(out)


def _body_text(msg) -> str:
    """Extract plain-text body, first 1500 chars."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(errors="ignore")[:1500]
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(errors="ignore")[:1500]
    return ""


def _categorise(subject: str, body: str) -> str | None:
    """
    Return 'interview', 'action', 'rejection', or None.
    Order matters: interview checked before rejection to avoid
    "we're moving forward" getting swallowed by a rejection pattern.
    """
    combined = (subject + " " + body).lower()
    if any(p in combined for p in INTERVIEW_PHRASES):
        return "interview"
    if any(p in combined for p in ACTION_PHRASES):
        return "action"
    if any(p in combined for p in REJECTION_PHRASES):
        return "rejection"
    return None


def _company_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _match_score(sender: str, subject: str, body: str, company: str, title: str) -> float:
    cslug = _company_slug(company)
    if not cslug:
        return 0.0

    sender_domain = re.search(r"@([\w.-]+)", sender.lower())
    if sender_domain:
        domain = sender_domain.group(1)
        if not any(ats in domain for ats in _ATS_DOMAINS):
            parts = domain.split(".")
            core = parts[-2] if len(parts) >= 2 else parts[0]
            if cslug in core or core in cslug:
                return 0.90

    subj_lower = subject.lower()
    body_lower = body.lower()
    company_lower = company.lower()

    if company_lower in subj_lower:
        return 0.85
    if cslug in re.sub(r"[^a-z0-9]", "", subj_lower):
        return 0.80
    if company_lower in body_lower:
        return 0.65
    if cslug in re.sub(r"[^a-z0-9]", "", body_lower[:600]):
        return 0.60

    return 0.0


# ── Public API ─────────────────────────────────────────────────────────────────

def scan_inbox(
    gmail_email: str,
    app_password: str,
    applied_jobs: list[dict],
    lookback_days: int = 90,
) -> dict[str, list[dict]]:
    """
    Scan Gmail inbox and return categorised matches against applied_jobs.

    Returns:
        {
          "interview":  [...],   # invitations to advance / schedule
          "action":     [...],   # assessments, scheduling links, reply-needed
          "rejection":  [...],   # declined emails
        }

    Each item in a list:
        job, email_from, email_subject, email_date, snippet, confidence, category
    """
    empty = {"interview": [], "action": [], "rejection": []}
    if not applied_jobs:
        return empty

    _dt = datetime.now() - timedelta(days=lookback_days)
    _months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    since_date = f"{_dt.day:02d}-{_months[_dt.month - 1]}-{_dt.year}"

    def _ascii(s: str) -> str:
        return s.encode("ascii", errors="ignore").decode("ascii")

    gmail_email  = _ascii(gmail_email.strip())
    app_password = _ascii(app_password.strip())

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(gmail_email, app_password)
        mail.select("INBOX")
    except imaplib.IMAP4.error as e:
        raise ConnectionError(
            f"Gmail login failed — check email/app password. ({e})"
        ) from e

    # Collect candidate message IDs across all categories
    candidate_ids: set[bytes] = set()
    for _cat, terms in _IMAP_SEARCH_TERMS.items():
        for phrase in terms:
            try:
                _, data = mail.search(None, f'SINCE {since_date} BODY "{phrase}"')
                if data and data[0]:
                    candidate_ids.update(data[0].split())
            except Exception:
                continue

    results: dict[str, list[dict]] = {"interview": [], "action": [], "rejection": []}
    seen_job_ids: set[str] = set()

    for msg_bytes_id in candidate_ids:
        try:
            _, raw = mail.fetch(msg_bytes_id, "(RFC822)")
            if not raw or not raw[0]:
                continue
            msg = _email_lib.message_from_bytes(raw[0][1])
        except Exception:
            continue

        subject = _decode_str(msg.get("Subject", ""))
        sender  = _decode_str(msg.get("From", ""))
        date    = msg.get("Date", "")
        body    = _body_text(msg)

        category = _categorise(subject, body)
        if not category:
            continue

        best_score = 0.0
        best_job   = None
        for job in applied_jobs:
            if job.get("id") in seen_job_ids:
                continue
            score = _match_score(sender, subject, body,
                                  job.get("company", ""), job.get("title", ""))
            if score > best_score:
                best_score = score
                best_job   = job

        if best_job and best_score >= 0.60:
            seen_job_ids.add(best_job["id"])
            results[category].append({
                "job":           best_job,
                "email_from":    sender,
                "email_subject": subject,
                "email_date":    date,
                "snippet":       body[:300].strip(),
                "confidence":    best_score,
                "category":      category,
            })

    mail.logout()

    for cat in results:
        results[cat].sort(key=lambda m: m["confidence"], reverse=True)

    return results
