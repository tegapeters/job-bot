"""
Claude Agent — scores jobs and generates tailored cover letters.
- Scoring: claude-sonnet-4-6 (better at reasoning about transferable skills)
- Cover letters: claude-sonnet-4-6, only generated for jobs scoring 8+
- Deduplication in main.py ensures we never re-score a seen job.
"""
import re
import anthropic
from config import (
    ANTHROPIC_API_KEY,
    REVIEW_MIN_SCORE,
    COVER_LETTER_MIN_SCORE,
    RESUME_TEXT,
    TARGET_ROLES,
    EXCLUDE_KEYWORDS,
    SCORING_BACKEND,
    HYBRID_CLAUDE_MIN_SCORE,
    ENABLE_COVER_LETTERS,
    LOCATIONS_REMOTE,
    LOCATIONS_HYBRID,
    LOCATIONS_ONSITE,
    REMOTE_OK,
    HYBRID_OK,
    ONSITE_OK,
    MIN_SALARY,
)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

SCORE_MODEL  = "claude-sonnet-4-6"   # upgraded — better transferable-skill reasoning
LETTER_MODEL = "claude-sonnet-4-6"   # cover letters


SCORE_PROMPT = """You are a job fit evaluator. Given a candidate's background and a job description, score the fit from 1–10.

CANDIDATE BACKGROUND:
{resume}

JOB POSTING:
Title: {title}
Company: {company}
Location: {location}
Description:
{description}

Respond in this exact format (no extra text):
SCORE: <number 1-10>
REASON: <one sentence>
SENIORITY: <Junior|Mid|Senior|Director>
SALARY_MATCH: <Yes|No|Unknown>
"""

COVER_LETTER_PROMPT = """Write a concise, compelling cover letter for this job application. 3 paragraphs max.
Tone: confident, professional, specific — not generic.
Lead with the most relevant experience for THIS specific role.
Do not use filler phrases like "I am writing to express my interest."
Use the candidate's actual name as it appears in the resume below. Do not invent or assume a name.

CANDIDATE RESUME:
{resume}

JOB:
Title: {title}
Company: {company}
Description:
{description}

Write the cover letter now, signed with the candidate's name from the resume above:"""


def score_job_claude(job: dict, resume_text: str = None) -> dict:
    """Score a job with Claude."""
    if not client:
        job["score"] = 0
        job["score_reason"] = "Anthropic key missing"
        job["seniority"] = "Unknown"
        job["salary_match"] = "Unknown"
        return job
    prompt = SCORE_PROMPT.format(
        resume=resume_text or RESUME_TEXT or "",
        title=job["title"],
        company=job.get("company", ""),
        location=job.get("location", ""),
        description=job.get("description", "")[:3000],
    )
    try:
        msg = client.messages.create(
            model=SCORE_MODEL,
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        lines = {l.split(":")[0].strip(): l.split(":", 1)[1].strip()
                 for l in text.splitlines() if ":" in l}
        job["score"] = int(lines.get("SCORE", 0))
        job["score_reason"] = lines.get("REASON", "")
        job["seniority"] = lines.get("SENIORITY", "")
        job["salary_match"] = lines.get("SALARY_MATCH", "Unknown")
    except Exception as e:
        print(f"  Score error ({job['title']}): {e}")
        job["score"] = 0
        job["score_reason"] = "Error"
    return job


def score_job_cheap(job: dict, resume_text: str = None) -> dict:
    """
    Local heuristic scorer (no LLM call).
    Used for cost reduction and as stage-1 in hybrid mode.
    """
    title = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()
    location = (job.get("location") or "").lower()
    text = f"{title} {description} {location}"

    score = 4
    reasons = []

    # Role/title fit gets the highest weight in cheap mode.
    title_role_hits = sum(1 for role in TARGET_ROLES if role.lower() in title)
    body_role_hits = sum(1 for role in TARGET_ROLES if role.lower() in description)
    if title_role_hits >= 1:
        score += 3
        reasons.append("target role in title")
    elif body_role_hits >= 1:
        score += 2
        reasons.append("target role in description")

    # Core skill keywords from your profile.
    skill_patterns = [
        r"\bpython\b", r"\bsql\b", r"\bdata engineer(ing)?\b", r"\bai\b",
        r"\bgenai\b", r"\bmachine learning\b", r"\banalyst\b", r"\bproduct\b",
        r"\bagile\b", r"\bscrum\b",
    ]
    skill_hits = sum(1 for pat in skill_patterns if re.search(pat, text))
    if skill_hits >= 4:
        score += 2
        reasons.append("strong skill overlap")
    elif skill_hits >= 2:
        score += 1
        reasons.append("skill overlap")

    # Location fit based on configured preferences.
    location_score = 0
    loc = location.strip()
    is_remote = ("remote" in loc) or ("work from home" in loc) or ("anywhere" in loc)
    onsite_match = any(city.lower() in loc for city in LOCATIONS_ONSITE)
    hybrid_match = any(city.lower() in loc for city in LOCATIONS_HYBRID)
    remote_region_match = any(region.lower() in loc for region in LOCATIONS_REMOTE)

    if is_remote and REMOTE_OK:
        location_score += 2
        reasons.append("remote location fit")
    elif is_remote and not REMOTE_OK:
        location_score -= 2
        reasons.append("remote not preferred")
    elif onsite_match and ONSITE_OK:
        location_score += 1
        reasons.append("onsite location fit")
    elif hybrid_match and HYBRID_OK:
        location_score += 1
        reasons.append("hybrid location fit")
    elif remote_region_match and (REMOTE_OK or HYBRID_OK or ONSITE_OK):
        location_score += 1
        reasons.append("region match")
    else:
        location_score -= 1
        reasons.append("location mismatch")
    score += location_score

    # Simple salary signal (only if posting mentions amounts).
    salary_numbers = re.findall(r"\$?\s?(\d{2,3})\s?[kK]\b", text)
    if salary_numbers:
        high_k = max(int(n) for n in salary_numbers) * 1000
        if high_k >= MIN_SALARY:
            score += 1
            reasons.append("salary target likely met")
        else:
            score -= 1
            reasons.append("salary likely below target")

    exclude_hits = sum(1 for kw in EXCLUDE_KEYWORDS if kw in text)
    if exclude_hits > 0:
        score -= min(4, exclude_hits)
        reasons.append("contains excluded keywords")

    if re.search(r"\b(senior|staff|principal|lead)\b", text):
        score += 2
        reasons.append("seniority fit")
    elif re.search(r"\b(junior|entry level|intern)\b", text):
        score -= 3
        reasons.append("likely too junior")

    final_score = max(1, min(10, score))
    job["score"] = final_score
    job["score_reason"] = ", ".join(reasons) if reasons else "heuristic fit estimate"
    job["seniority"] = "Unknown"
    job["salary_match"] = "Unknown"
    return job


def score_job(
    job: dict,
    resume_text: str = None,
    scoring_backend: str = None,
    hybrid_claude_min_score: int = None,
) -> dict:
    """Dispatch scoring based on configured backend."""
    backend = (scoring_backend or SCORING_BACKEND or "claude").strip().lower()
    hybrid_min = (
        hybrid_claude_min_score
        if hybrid_claude_min_score is not None
        else HYBRID_CLAUDE_MIN_SCORE
    )
    if backend == "cheap":
        return score_job_cheap(job, resume_text=resume_text)
    if backend == "hybrid":
        stage1 = score_job_cheap(job, resume_text=resume_text)
        if (stage1.get("score") or 0) >= hybrid_min:
            return score_job_claude(job, resume_text=resume_text)
        return stage1
    return score_job_claude(job, resume_text=resume_text)


def generate_cover_letter(job: dict, resume_text: str = None) -> str:
    """Generate cover letter using Sonnet — only called for qualified jobs."""
    if not resume_text:
        return "No resume loaded — cannot generate a personalised cover letter."
    if not client:
        return "Anthropic key missing — cannot generate cover letter."
    prompt = COVER_LETTER_PROMPT.format(
        resume=resume_text,
        title=job["title"],
        company=job.get("company", "the company"),
        description=job.get("description", "")[:3000],
    )
    try:
        msg = client.messages.create(
            model=LETTER_MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        return f"Error generating cover letter: {e}"


def process_jobs(
    jobs: list[dict],
    verbose: bool = True,
    resume_text: str = None,
    scoring_backend: str = None,
    enable_cover_letters: bool = None,
    hybrid_claude_min_score: int = None,
) -> tuple[list[dict], list[dict]]:
    """Score all jobs with Haiku, generate cover letters with Sonnet for 7+ only.
    Returns (all_scored, qualified) — all_scored saved to dedup cache, qualified for review.
    resume_text: override the default resume (used for beta multi-user mode).
    """
    mode = (scoring_backend or SCORING_BACKEND or "claude").strip().lower()
    if mode not in {"cheap", "hybrid", "claude"}:
        mode = "claude"
    print(f"\n🤖 Scoring {len(jobs)} new jobs with mode={mode}...")
    scored = []

    for i, job in enumerate(jobs):
        job = score_job(
            job,
            resume_text=resume_text,
            scoring_backend=mode,
            hybrid_claude_min_score=hybrid_claude_min_score,
        )
        if verbose:
            flag = "✅" if job["score"] >= REVIEW_MIN_SCORE else "  "
            print(f"  {flag} [{i+1}/{len(jobs)}] {job['title']} @ {job.get('company','')} "
                  f"— {job['score']}/10")
        scored.append(job)

    qualified = [j for j in scored if j["score"] >= REVIEW_MIN_SCORE]
    skipped = len(scored) - len(qualified)
    print(f"\n✅ {len(qualified)} jobs scored {REVIEW_MIN_SCORE}+ (8+ threshold) | {skipped} below threshold — skipped")

    from fetcher import enrich_jobs
    qualified = enrich_jobs(qualified)

    letters_enabled = ENABLE_COVER_LETTERS if enable_cover_letters is None else bool(enable_cover_letters)
    if letters_enabled and client and mode != "cheap":
        cover_letter_jobs = [j for j in qualified if (j.get("score") or 0) >= COVER_LETTER_MIN_SCORE]
        print(f"\n✍️  Generating cover letters for {len(cover_letter_jobs)} jobs scoring {COVER_LETTER_MIN_SCORE}+ (skipping {len(qualified) - len(cover_letter_jobs)} below threshold)...")
        for i, job in enumerate(cover_letter_jobs):
            print(f"  [{i+1}/{len(cover_letter_jobs)}] {job['title']} @ {job.get('company','')}")
            job["cover_letter"] = generate_cover_letter(job, resume_text=resume_text)
    else:
        print("\n✍️  Cover letters disabled for this run (no Claude usage).")

    return scored, qualified
