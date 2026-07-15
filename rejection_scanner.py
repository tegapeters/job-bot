"""
Gmail rejection scanner — IMAP-based.

Scans the inbox of the email address you use to apply for jobs,
finds rejection emails, and matches them against applied jobs in Supabase.

Credentials are NEVER persisted — they live only in memory for the session.
To use, you need a Gmail App Password for the applying email:
  https://myaccount.google.com/apppasswords
  (Google Account → Security → 2-Step Verification → App passwords)
"""
import imaplib
import email as _email_lib
import re
from datetime import datetime, timedelta
from email.header import decode_header as _decode_header

# ── Rejection signal phrases ───────────────────────────────────────────────────
# Order matters: more specific phrases first to avoid false positives.
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
    "after careful consideration",  # common opener before "we won't be..."
]

# Domains that send on behalf of companies — check subject/body, not sender domain
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
    """Extract plain-text body from an email.Message, first 1200 chars."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(errors="ignore")[:1200]
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            return payload.decode(errors="ignore")[:1200]
    return ""


def _is_rejection(subject: str, body: str) -> bool:
    combined = (subject + " " + body).lower()
    return any(phrase in combined for phrase in REJECTION_PHRASES)


def _company_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _match_score(sender: str, subject: str, body: str, company: str, title: str) -> float:
    """
    Returns 0.0–1.0 confidence that this email is about <company>/<title>.
    Strategy:
      1. Sender domain contains company slug         → 0.90
      2. ATS domain + subject contains company name  → 0.85
      3. Subject contains company name               → 0.80
      4. Body contains company name                  → 0.65
    """
    cslug = _company_slug(company)
    if not cslug:
        return 0.0

    # 1. Check sender domain (skip ATS domains)
    sender_domain = re.search(r"@([\w.-]+)", sender.lower())
    if sender_domain:
        domain = sender_domain.group(1)
        if not any(ats in domain for ats in _ATS_DOMAINS):
            # strip subdomains: hr.acme.com → acme
            parts = domain.split(".")
            core = parts[-2] if len(parts) >= 2 else parts[0]
            if cslug in core or core in cslug:
                return 0.90

    # 2–4. Check subject and body
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
) -> list[dict]:
    """
    Connect to Gmail via IMAP, find rejection emails, match against applied_jobs.

    Returns list of match dicts:
        job          — the matched job dict from applied_jobs
        email_from   — sender string
        email_subject
        email_date
        snippet      — first 300 chars of body
        confidence   — 0.0–1.0 match score
    """
    if not applied_jobs:
        return []

    since_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%d-%b-%Y")

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(gmail_email, app_password)
        mail.select("INBOX")
    except imaplib.IMAP4.error as e:
        raise ConnectionError(
            f"Gmail login failed — check email/app password. ({e})"
        ) from e

    # Collect message IDs matching any rejection phrase (IMAP OR not supported,
    # so we union the per-phrase searches)
    candidate_ids: set[bytes] = set()
    search_phrases = [
        "not moving forward",
        "regret to inform",
        "not selected",
        "unfortunately",
        "decided to pursue",
        "position has been filled",
        "after careful consideration",
    ]
    for phrase in search_phrases:
        try:
            _, data = mail.search(None, f'SINCE {since_date} BODY "{phrase}"')
            if data and data[0]:
                candidate_ids.update(data[0].split())
        except Exception:
            continue

    matches: list[dict] = []
    seen_job_ids: set[str] = set()  # avoid duplicate matches per job

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

        if not _is_rejection(subject, body):
            continue

        # Try to match against each applied job
        best_score = 0.0
        best_job   = None
        for job in applied_jobs:
            if job.get("id") in seen_job_ids:
                continue
            score = _match_score(
                sender, subject, body,
                job.get("company", ""),
                job.get("title", ""),
            )
            if score > best_score:
                best_score = score
                best_job   = job

        if best_job and best_score >= 0.60:
            seen_job_ids.add(best_job["id"])
            matches.append({
                "job":           best_job,
                "email_from":    sender,
                "email_subject": subject,
                "email_date":    date,
                "snippet":       body[:300].strip(),
                "confidence":    best_score,
            })

    mail.logout()

    # Sort by confidence descending
    matches.sort(key=lambda m: m["confidence"], reverse=True)
    return matches
