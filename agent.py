"""
Claude Agent — scores jobs and generates tailored cover letters.
- Scoring: claude-sonnet-4-6 (better at reasoning about transferable skills)
- Cover letters: claude-sonnet-4-6, only generated for jobs scoring 8+
- Deduplication in main.py ensures we never re-score a seen job.
"""
import anthropic
from config import ANTHROPIC_API_KEY, REVIEW_MIN_SCORE, COVER_LETTER_MIN_SCORE, RESUME_TEXT

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

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


def score_job(job: dict, resume_text: str = None) -> dict:
    """Score a job using Haiku — fast and cheap."""
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


def generate_cover_letter(job: dict, resume_text: str = None) -> str:
    """Generate cover letter using Sonnet — only called for qualified jobs."""
    if not resume_text:
        return "No resume loaded — cannot generate a personalised cover letter."
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


def process_jobs(jobs: list[dict], verbose: bool = True, resume_text: str = None) -> tuple[list[dict], list[dict]]:
    """Score all jobs with Haiku, generate cover letters with Sonnet for 7+ only.
    Returns (all_scored, qualified) — all_scored saved to dedup cache, qualified for review.
    resume_text: override the default resume (used for beta multi-user mode).
    """
    print(f"\n🤖 Scoring {len(jobs)} new jobs with Haiku...")
    scored = []

    for i, job in enumerate(jobs):
        job = score_job(job, resume_text=resume_text)
        if verbose:
            flag = "✅" if job["score"] >= REVIEW_MIN_SCORE else "  "
            print(f"  {flag} [{i+1}/{len(jobs)}] {job['title']} @ {job.get('company','')} "
                  f"— {job['score']}/10")
        scored.append(job)

    qualified = [j for j in scored if j["score"] >= REVIEW_MIN_SCORE]
    skipped = len(scored) - len(qualified)
    print(f"\n✅ {len(qualified)} jobs scored {REVIEW_MIN_SCORE}+ | {skipped} below threshold (saved to skip list)")

    from fetcher import enrich_jobs
    qualified = enrich_jobs(qualified)

    cover_letter_jobs = [j for j in qualified if (j.get("score") or 0) >= COVER_LETTER_MIN_SCORE]
    print(f"\n✍️  Generating cover letters for {len(cover_letter_jobs)} jobs scoring {COVER_LETTER_MIN_SCORE}+ (skipping {len(qualified) - len(cover_letter_jobs)} below threshold)...")
    for i, job in enumerate(cover_letter_jobs):
        print(f"  [{i+1}/{len(cover_letter_jobs)}] {job['title']} @ {job.get('company','')}")
        job["cover_letter"] = generate_cover_letter(job, resume_text=resume_text)

    return scored, qualified
