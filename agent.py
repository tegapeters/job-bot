"""
Claude Agent — scores jobs and generates tailored cover letters.
- Scoring: claude-sonnet-4-6 (better reasoning about transferable skills)
- Cover letters: claude-sonnet-4-6, only for jobs scoring 8+
- Cheap scorer is resume-aware: extracts skills from resume text dynamically
- Prompt caching: resume sent as cached system prompt (~70% token savings)
"""
import json
import re
import time
import anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import (
    ANTHROPIC_API_KEY,
    REVIEW_MIN_SCORE,
    COVER_LETTER_MIN_SCORE,
    TARGET_ROLES,
    EXCLUDE_KEYWORDS,
    SCORING_BACKEND,
    HYBRID_CLAUDE_MIN_SCORE,
    ENABLE_COVER_LETTERS,
    LOCATIONS_REMOTE,
    LOCATIONS_ONSITE,
)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

SCORE_MODEL  = "claude-sonnet-4-6"
LETTER_MODEL = "claude-sonnet-4-6"


# ── Prompt templates ───────────────────────────────────────────────
# User-agnostic rubric: Claude reads the actual resume vs job — no hardcoded skills.
SCORE_SYSTEM_TEMPLATE = """You are a strict job fit evaluator. Score how well the CANDIDATE BACKGROUND fits the job posting on a 1–10 scale. Be conservative — it is better to underscore a mediocre fit than to overscore a weak one.

Scoring guidelines:
10 — Near-perfect: core skills match exactly, seniority fits, salary confirmed meets target. Rare.
 9 — Excellent: strong skill overlap across nearly all core requirements, right seniority level, candidate can contribute from week one with minimal ramp-up.
 8 — Good: majority of required skills present with only minor gaps, seniority is reasonable, candidate can do this job well within 1–2 months.
 7 — Partial: clear relevance but a meaningful gap in a core requirement (not just a nice-to-have), OR a domain stretch that requires real ramp-up, OR one tier of seniority mismatch.
 6 — Weak: some transferable skills but missing multiple core requirements OR significant domain mismatch OR two+ seniority tiers off.
 5 — Long shot: tangentially related background, would need 6+ months ramp-up on core skills to be effective.
1–4 — Poor/no match: wrong field, missing the primary required skills, or drastically over/under-qualified.

Calibration rules — apply these before finalising the score:
- When choosing between two adjacent scores, pick the lower one.
- "Strong transferable skills" alone is not sufficient for 8. The candidate must demonstrate the actual skills the job lists as required, not just adjacent ones.
- A role in a specialised domain (healthcare, legal, manufacturing, financial crime) where the candidate has no domain experience caps at 7 regardless of technical skill overlap.
- A confirmed salary below the candidate's target drops the score by 1 from wherever skill fit lands.
- A vague job description that makes fit hard to assess should score 6, not 7 — ambiguity is penalised, not rewarded.
- Unknown or unlisted salary is NEUTRAL — do not penalise for it.
- Work arrangement: if the job is Onsite and the candidate's resume indicates remote/hybrid preference, drop score by 1 unless the onsite city matches a city mentioned in the candidate's resume. Remote and Hybrid arrangements are NEUTRAL — do not penalise.

Evaluate in this order:
1. Skill fit (primary): do the candidate's demonstrated skills match what the job explicitly requires?
2. Seniority fit: is this a realistic level — not just a stretch, but a credible application?
3. Domain fit: does the candidate have relevant industry/domain context, or would they be starting from scratch?
4. Salary fit: only factor when salary is confirmed and clearly misaligned.
5. Location fit: only penalise if onsite and clearly outside candidate's stated locations.

CANDIDATE BACKGROUND:
{resume}

Respond in exactly this format (no extra text):
SCORE: <number 1-10>
REASON: <one sentence explaining the primary factor>
SENIORITY: <Junior|Mid|Senior|Director>
SALARY_MATCH: <Yes|No|Unknown>"""

SCORE_USER_TEMPLATE = """JOB POSTING:
Title: {title}
Company: {company}
Location: {location}
Work arrangement: {work_type}
Salary (from posting): {salary}
Candidate Salary Target: {salary_target}
Description:
{description}"""

COVER_LETTER_SYSTEM_TEMPLATE = """Write a cover letter body for a job application. 3 paragraphs, ~250–350 words.

Rules:
- Write ONLY the letter body — no contact header, no address block, no date, no "Dear Hiring Manager" salutation
- Sign off with just the candidate's full name (as it appears in the resume) on its own line
- First person throughout — never refer to the candidate in third person
- Open with the strongest relevant experience match, not a generic intro line
- Second paragraph: 2–3 specific achievements with numbers or outcomes from the resume
- Third paragraph: forward-looking — why this company/role, what you bring from day one
- Never use filler phrases like "I am writing to express my interest" or "I am excited to apply"
- Be specific to the job description — reference the role's actual requirements

CANDIDATE RESUME:
{resume}"""

COVER_LETTER_USER_TEMPLATE = """Write a cover letter body for this role:

Title: {title}
Company: {company}
Job Description:
{description}"""


# ── Skill vocabulary for resume-aware cheap scoring ────────────────
_SKILL_VOCAB = [
    # Programming
    "python", "sql", "java", "javascript", "typescript", "scala", "golang", "rust",
    "c++", "c#", "r script", "bash", "shell",
    # Data / ML
    "spark", "pyspark", "kafka", "airflow", "dbt", "databricks", "flink", "hadoop",
    "hive", "presto", "trino", "luigi", "prefect",
    "machine learning", "deep learning", "tensorflow", "pytorch", "scikit-learn",
    "mlflow", "xgboost", "nlp", "llm", "generative ai", "genai", "rag",
    "data engineering", "data science", "etl", "elt", "pipeline", "analytics",
    "feature store", "model serving",
    # Cloud / infra
    "aws", "gcp", "azure", "oci", "snowflake", "redshift", "bigquery", "s3",
    "lambda", "glue", "emr", "dataflow", "kubernetes", "docker", "terraform",
    "ci/cd", "github actions", "devops",
    # BI / reporting
    "tableau", "power bi", "looker", "metabase", "qlik", "dax",
    # Databases
    "postgresql", "mysql", "mongodb", "cassandra", "dynamodb", "elasticsearch",
    # Finance / accounting
    "excel", "financial analysis", "financial modeling", "accounting", "budget",
    "forecasting", "accounts payable", "accounts receivable", "quickbooks",
    "sap", "oracle financials", "netsuite", "gaap", "cpa", "audit", "tax",
    # Project / ops / supply chain
    "project management", "pmp", "agile", "scrum", "kanban", "jira", "confluence",
    "vendor management", "operations", "logistics", "supply chain", "lean", "six sigma",
    "process improvement", "okr", "kpi",
    # Web / SWE
    "react", "node", "django", "flask", "rails", "spring", "angular", "vue",
    "rest api", "graphql", "microservices",
    # Legal
    "litigation", "contract law", "legal research", "case management", "deposition",
    "compliance", "regulatory", "intellectual property", "paralegal", "attorney",
    "legal writing", "mediation", "arbitration", "contract review", "due diligence",
    # Healthcare / clinical
    "nursing", "clinical", "patient care", "medical", "healthcare", "ehr", "emr",
    "hipaa", "patient safety", "clinical trials", "pharmacy", "therapy", "epic",
    "care coordination", "case management",
    # Sales / business development
    "salesforce", "crm", "prospecting", "negotiation", "territory management",
    "quota", "pipeline", "b2b", "b2c", "account executive", "business development",
    "lead generation", "cold calling", "account management", "revenue",
    # Marketing
    "seo", "sem", "content marketing", "email marketing", "social media",
    "brand management", "digital marketing", "campaign management", "copywriting",
    "google analytics", "hubspot", "marketo", "demand generation", "paid media",
    "growth marketing",
    # HR / recruiting
    "recruiting", "talent acquisition", "onboarding", "benefits administration",
    "compensation", "employee relations", "hris", "workday", "performance management",
    "workforce planning", "organizational development",
    # Product management
    "product management", "product roadmap", "stakeholder management", "user research",
    "sprint planning", "go-to-market", "product strategy", "user stories", "backlog",
    "product analytics",
    # Design / UX
    "figma", "sketch", "adobe xd", "user experience", "user interface", "wireframing",
    "prototyping", "design systems", "ux research", "visual design", "interaction design",
    # Writing / content
    "content writing", "technical writing", "grant writing", "editorial",
    "journalism", "communication", "documentation",
    # Customer success / support
    "customer success", "client management", "customer retention", "nps",
    "zendesk", "intercom", "customer experience", "implementation",
    # Education
    "curriculum", "instruction", "lesson planning", "classroom management",
    "e-learning", "lms", "training", "facilitation",
    # Engineering (non-software)
    "civil engineering", "mechanical engineering", "electrical engineering",
    "structural", "autocad", "solidworks", "construction management",
]


_SALARY_PATTERNS = [
    # Minimum $106,500 - Midpoint $133,000 - Maximum $159,500  (3-part $)
    (r'[Mm]inimum\s*\$\s*([\d,]+).*?[Mm]aximum\s*\$\s*([\d,]+)', 2),
    # Minimum Salary: US Dollar (USD) 106,500 ... Maximum Salary: US Dollar (USD) 159,500
    (r'[Mm]inimum\s+[Ss]alary\s*:.*?(\d[\d,]+).*?[Mm]aximum\s+[Ss]alary\s*:.*?(\d[\d,]+)', 2),
    # Min Salary: $106,500 / Max Salary: $159,500
    (r'[Mm]in(?:imum)?\s*(?:Salary|Pay)?:?\s*\$\s*([\d,]+)\D+[Mm]ax(?:imum)?\s*(?:Salary|Pay)?:?\s*\$\s*([\d,]+)', 2),
    # $117,500—$172,800 USD  |  $117,500–$172,800  |  $117,500 - $172,800 a year
    (r'\$\s?([\d,]+)\s*[—–\-]+\s*\$?\s?([\d,]+)\s*(?:USD|/yr|/year|a year|per year|annually)?', 2),
    # $120K - $160K
    (r'\$\s?([\d]+)[kK]\s*[—–\-]+\s*\$?\s?([\d]+)[kK]', 2),
    # $150,000 to $200,000
    (r'\$\s?([\d,]+)\s*to\s*\$\s?([\d,]+)', 2),
    # Base salary range: $X - $Y
    (r'[Bb]ase\s+[Ss]alary\s*(?:range)?:?\s*\$\s*([\d,]+)\s*[—–\-]+\s*\$?\s*([\d,]+)', 2),
    # Compensation: $X,000 - $Y,000
    (r'[Cc]ompensation\s*:?\s*\$\s*([\d,]+)\s*[—–\-]+\s*\$?\s*([\d,]+)', 2),
    # salary range of $X to $Y
    (r'[Ss]alary\s+(?:range\s+)?of\s+\$\s?([\d,]+)\s*(?:to|-)\s*\$?\s?([\d,]+)', 2),
    # Up to $180,000
    (r'[Uu]p\s+to\s+\$\s?([\d,]+)', 1),
    # $150,000/year  or  $150,000 per year
    (r'\$\s?([\d,]+)\s*(?:/yr|/year|per year|annually)', 1),
    # Starting at $120,000
    (r'[Ss]tarting\s+at\s+\$\s?([\d,]+)', 1),
    # Hourly: $50/hr - $75/hr  or  $50 - $75/hour
    (r'\$\s?([\d]+(?:\.\d+)?)\s*[—–\-]+\s*\$?\s?([\d]+(?:\.\d+)?)\s*/\s*h(?:ou)?r', 2),
    # $50/hr or $50 per hour (single)
    (r'\$\s?([\d]+(?:\.\d+)?)\s*(?:/hr|/hour|per hour)', 1),
]


def _to_dollars(val: str) -> int:
    """Convert string like '120,000', '120' (K), or '50.5' (hourly) to integer dollars."""
    try:
        n = int(float(val.replace(",", "")))
    except (ValueError, TypeError):
        return 0
    return n * 1000 if n < 1000 else n


def _extract_salary_from_text(text: str) -> str | None:
    """Pull the first salary range or figure out of raw text."""
    if not text:
        return None
    for pat, n_groups in _SALARY_PATTERNS:
        m = re.search(pat, text, re.DOTALL)
        if not m:
            continue
        groups = [g for g in m.groups() if g][:n_groups]
        if len(groups) == 2:
            lo = _to_dollars(groups[0])
            hi = _to_dollars(groups[1])
            if lo > hi:          # swap if order reversed
                lo, hi = hi, lo
            return f"${lo:,}–${hi:,}"
        elif len(groups) == 1:
            val = _to_dollars(groups[0])
            return f"${val:,}+"
    return None


def _extract_skills(text: str) -> frozenset[str]:
    """Extract recognized skill tokens from text."""
    t = (text or "").lower()
    return frozenset(s for s in _SKILL_VOCAB if s in t)


_ROLE_STOPWORDS = {"and", "or", "the", "for", "of", "in", "at", "a", "an",
                   "to", "by", "with", "from", "as", "is", "it", "on"}


def _role_matches_title(title: str, roles: list[str]) -> bool:
    """
    Keyword-overlap role matching — more forgiving than strict substring.
    A job title matches a role if ≥60% of the role's meaningful keywords appear in the title.
    Example: role 'ICU Registered Nurse' matches title 'Registered Nurse, ICU'
             role 'Data Engineer' matches 'Senior Data Engineer'
    """
    t = title.lower()
    for role in roles:
        if role.lower() in t:  # fast exact path
            return True
        words = [w for w in re.sub(r"[^a-z0-9 ]", " ", role.lower()).split()
                 if len(w) >= 2 and w not in _ROLE_STOPWORDS]
        if not words:
            continue
        hits = sum(1 for w in words if w in t)
        if hits >= max(1, round(len(words) * 0.6)):
            return True
    return False


def _parse_score_response(text: str) -> dict:
    score_match    = re.search(r"SCORE:\s*(\d+)", text)
    reason_match   = re.search(r"REASON:\s*(.+?)(?:\n|$)", text)
    seniority_match = re.search(r"SENIORITY:\s*(Junior|Mid|Senior|Director)", text, re.IGNORECASE)
    salary_match   = re.search(r"SALARY_MATCH:\s*(Yes|No|Unknown)", text, re.IGNORECASE)

    if not score_match:
        raise ValueError(f"No SCORE field in response: {text!r}")
    score = int(score_match.group(1))
    if not 1 <= score <= 10:
        raise ValueError(f"Score {score} out of valid range 1–10")

    return {
        "score":        score,
        "score_reason": reason_match.group(1).strip() if reason_match else "",
        "seniority":    seniority_match.group(1).capitalize() if seniority_match else "",
        "salary_match": salary_match.group(1).capitalize() if salary_match else "Unknown",
    }


def score_job_claude(job: dict, resume_text: str = None, min_salary: int = 0) -> dict:
    """Score a job with Claude. Requires resume_text — no fallback to config."""
    if not resume_text:
        job.update({"score": 0, "score_reason": "No resume loaded", "seniority": "", "salary_match": "Unknown"})
        return job
    if not client:
        job.update({"score": 0, "score_reason": "Anthropic key missing", "seniority": "", "salary_match": "Unknown"})
        return job

    desc = job.get("description", "")

    # Extract salary from description if not already in the dedicated field
    salary_field = job.get("salary_range") or job.get("salary")
    if not salary_field:
        salary_field = _extract_salary_from_text(desc) or "Not listed"
        if salary_field != "Not listed":
            job["salary_range"] = salary_field  # cache for UI display

    salary_target = f"${min_salary:,}+" if min_salary else "Not specified (infer from resume if stated)"

    system_text = SCORE_SYSTEM_TEMPLATE.format(resume=resume_text)
    _wt = job.get("work_type") or "unknown"
    work_type_label = {"remote": "Remote", "hybrid": "Hybrid (flexible)", "onsite": "Onsite"}.get(_wt, "Not specified")

    user_text = SCORE_USER_TEMPLATE.format(
        title=job["title"],
        company=job.get("company", ""),
        location=job.get("location", ""),
        work_type=work_type_label,
        salary=salary_field,
        salary_target=salary_target,
        description=desc[:3000],
    )

    # Compute lightweight features alongside Claude — persisted for future model training
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity as _cos_sim
        _vec = TfidfVectorizer(max_features=4000, ngram_range=(1, 2),
                               stop_words="english", sublinear_tf=True)
        _mat = _vec.fit_transform([resume_text or "", desc or "title"])
        job["tfidf_sim"] = round(float(_cos_sim(_mat[0:1], _mat[1:2])[0][0]), 4)
        resume_skills = _extract_skills((resume_text or "").lower())
        job_skills = _extract_skills(f"{job.get('title','')} {desc}".lower())
        job["skill_ratio"] = round(
            len(resume_skills & job_skills) / max(len(job_skills), 1), 4
        ) if job_skills else 0.0
    except Exception:
        pass  # never block scoring on feature extraction

    for attempt in range(3):
        try:
            msg = client.messages.create(
                model=SCORE_MODEL,
                max_tokens=150,
                system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user_text}],
            )
            parsed = _parse_score_response(msg.content[0].text.strip())
            job.update(parsed)
            job["scored_by"] = SCORE_MODEL
            return job
        except anthropic.RateLimitError:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                print(f"  Score error ({job['title']}): rate limit")
                break
        except ValueError as e:
            if attempt < 2:
                continue
            print(f"  Score parse error ({job['title']}): {e}")
            break
        except Exception as e:
            print(f"  Score error ({job['title']}): {e}")
            break

    job.update({"score": 0, "score_reason": "Scoring error", "seniority": "", "salary_match": "Unknown"})
    return job


def score_job_cheap(
    job: dict,
    resume_text: str = None,
    min_salary: int = 0,
    target_roles: list[str] = None,
) -> dict:
    """
    Local heuristic scorer. Resume-aware when resume_text is provided:
    extracts skills from the resume and counts overlap with the job description.
    Falls back to config-based patterns when resume_text is absent (CLI mode).
    """
    title       = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()
    location    = (job.get("location") or "").lower()
    job_text    = f"{title} {description} {location}"

    resume_skills = _extract_skills(resume_text) if resume_text else frozenset()
    roles = [r.lower() for r in (target_roles or [])]

    score = 4
    reasons = []

    # ── Role / title fit ──────────────────────────────────────────
    check_roles = roles if roles else [r.lower() for r in TARGET_ROLES]
    if _role_matches_title(title, check_roles):
        score += 3
        reasons.append("target role in title")
    elif any(_role_matches_title(r, [description[:200]]) for r in check_roles):
        score += 2
        reasons.append("target role in description")
    elif roles:  # only penalise when user has set explicit roles
        score -= 1
        reasons.append("role not in posting")

    # ── Skill overlap ─────────────────────────────────────────────
    if resume_skills:
        job_skills = _extract_skills(job_text)
        overlap = resume_skills & job_skills
        if len(overlap) >= 4:
            score += 2
            reasons.append(f"strong skill match ({len(overlap)} skills)")
        elif len(overlap) >= 2:
            score += 1
            reasons.append(f"skill overlap ({len(overlap)} skills)")
        elif len(overlap) == 0:
            score -= 2
            reasons.append("no skill overlap with resume")
    # No resume provided — skip skill overlap entirely (neutral, no penalty/bonus).
    # Applying hardcoded tech patterns here would silently break non-tech users.

    # ── Location ──────────────────────────────────────────────────
    is_remote = any(kw in location for kw in ("remote", "work from home", "anywhere"))
    onsite_match = any(city.lower() in location for city in LOCATIONS_ONSITE)
    region_match = any(r.lower() in location for r in LOCATIONS_REMOTE)

    if is_remote or region_match:
        score += 1
        reasons.append("remote / region match")
    elif onsite_match:
        score += 1
        reasons.append("onsite location match")

    # ── Salary ────────────────────────────────────────────────────
    effective_min = min_salary or 0  # 0 = no floor; never fall back to config.MIN_SALARY
    salary_nums = re.findall(r"\$?\s?(\d{2,3})\s?[kK]\b", job_text)
    if salary_nums and effective_min:
        high_k = max(int(n) for n in salary_nums) * 1000
        if high_k >= effective_min:
            score += 1
            reasons.append("salary target met")
        else:
            score -= 1
            reasons.append("salary below target")

    # ── Exclusions ────────────────────────────────────────────────
    exclude_hits = sum(1 for kw in EXCLUDE_KEYWORDS if kw in job_text)
    if exclude_hits:
        score -= min(4, exclude_hits)
        reasons.append("excluded keywords")

    # ── Seniority ─────────────────────────────────────────────────
    if re.search(r"\b(senior|staff|principal|lead)\b", job_text):
        score += 1
        reasons.append("seniority match")
    elif re.search(r"\b(junior|entry.?level|intern)\b", job_text):
        score -= 3
        reasons.append("too junior")

    job["score"] = max(1, min(10, score))
    job["score_reason"] = ", ".join(reasons) if reasons else "heuristic estimate"
    job["seniority"] = "Unknown"
    job["salary_match"] = "Unknown"
    job["scored_by"] = "heuristic"
    return job


def score_job(
    job: dict,
    resume_text: str = None,
    scoring_backend: str = None,
    hybrid_claude_min_score: int = None,
    min_salary: int = 0,
    target_roles: list[str] = None,
) -> dict:
    """Dispatch scoring based on configured backend."""
    backend   = (scoring_backend or SCORING_BACKEND or "claude").strip().lower()
    hybrid_min = hybrid_claude_min_score if hybrid_claude_min_score is not None else HYBRID_CLAUDE_MIN_SCORE

    cheap_kwargs = dict(resume_text=resume_text, min_salary=min_salary, target_roles=target_roles)

    if backend == "cheap":
        return score_job_cheap(job, **cheap_kwargs)
    if backend == "hybrid":
        stage1 = score_job_cheap(job, **cheap_kwargs)
        if (stage1.get("score") or 0) >= hybrid_min:
            return score_job_claude(job, resume_text=resume_text, min_salary=min_salary)
        return stage1
    return score_job_claude(job, resume_text=resume_text, min_salary=min_salary)


def generate_cover_letter(job: dict, resume_text: str = None) -> str | None:
    """Generate cover letter. Returns None (not an error string) if prerequisites unmet."""
    if not resume_text or not client:
        return None

    system_text = COVER_LETTER_SYSTEM_TEMPLATE.format(resume=resume_text)
    user_text = COVER_LETTER_USER_TEMPLATE.format(
        title=job["title"],
        company=job.get("company", "the company"),
        description=job.get("description", "")[:3000],
    )

    try:
        msg = client.messages.create(
            model=LETTER_MODEL,
            max_tokens=900,
            system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_text}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        print(f"  Cover letter error ({job['title']}): {e}")
        return None


def process_jobs(
    jobs: list[dict],
    verbose: bool = True,
    resume_text: str = None,
    scoring_backend: str = None,
    enable_cover_letters: bool = None,
    hybrid_claude_min_score: int = None,
    min_salary: int = 0,
    target_roles: list[str] = None,
) -> tuple[list[dict], list[dict]]:
    """
    Score all jobs, generate cover letters for qualified ones.
    Returns (all_scored, qualified).

    Pass 1: fast cheap pre-filter using resume skills + target roles.
    Pass 2: full scoring (claude / hybrid / cheap) on jobs that pass threshold.
    """
    import time as _time

    mode = (scoring_backend or SCORING_BACKEND or "claude").strip().lower()
    if mode not in {"cheap", "hybrid", "claude"}:
        mode = "claude"

    cheap_kwargs = dict(resume_text=resume_text, min_salary=min_salary, target_roles=target_roles)
    score_kwargs = dict(
        resume_text=resume_text,
        scoring_backend=mode,
        hybrid_claude_min_score=hybrid_claude_min_score,
        min_salary=min_salary,
        target_roles=target_roles,
    )

    timings: dict[str, float] = {}

    # Pass 1: cheap pre-filter
    print(f"\n🤖 Pass 1 — pre-filtering {len(jobs)} jobs...")
    _t = _time.perf_counter()
    prescored = [score_job_cheap(job, **cheap_kwargs) for job in jobs]
    timings["pass1_s"] = round(_time.perf_counter() - _t, 1)

    to_enrich      = [j for j in prescored if (j.get("score") or 0) >= 5]
    rejected_early = [j for j in prescored if (j.get("score") or 0) < 5]
    print(f"  {len(to_enrich)} passed pre-filter · {len(rejected_early)} rejected early  ({timings['pass1_s']}s)")

    from fetcher import enrich_jobs
    _t = _time.perf_counter()
    to_enrich = enrich_jobs(to_enrich)
    timings["enrich_s"] = round(_time.perf_counter() - _t, 1)

    # Pass 2: full scoring — parallel
    n = len(to_enrich)
    print(f"\n🤖 Pass 2 — full scoring {n} jobs (mode={mode}, workers=8)...")
    _t = _time.perf_counter()
    scored = list(rejected_early)

    if n == 0:
        pass
    elif mode == "cheap":
        for job in to_enrich:
            scored.append(score_job(job, **score_kwargs))
    else:
        done = 0
        lock_print = __import__("threading").Lock()

        def _score_one(job):
            return score_job(job, **score_kwargs)

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(_score_one, job): job for job in to_enrich}
            for future in as_completed(futures):
                result = future.result()
                done += 1
                if verbose:
                    flag = "✅" if result["score"] >= REVIEW_MIN_SCORE else "  "
                    with lock_print:
                        print(f"  {flag} [{done}/{n}] {result['title']} @ {result.get('company','')} — {result['score']}/10")
                scored.append(result)

    timings["pass2_s"] = round(_time.perf_counter() - _t, 1)

    qualified = [j for j in scored if j["score"] >= REVIEW_MIN_SCORE]
    print(f"\n✅ {len(qualified)} jobs scored {REVIEW_MIN_SCORE}+ | {len(scored)-len(qualified)} below threshold  ({timings['pass2_s']}s)")

    letters_enabled = ENABLE_COVER_LETTERS if enable_cover_letters is None else bool(enable_cover_letters)
    _t = _time.perf_counter()
    if letters_enabled and client and mode != "cheap":
        cl_jobs = [j for j in qualified if (j.get("score") or 0) >= COVER_LETTER_MIN_SCORE]
        print(f"\n✍️  Cover letters for {len(cl_jobs)} jobs scoring {COVER_LETTER_MIN_SCORE}+ (workers=3)...")

        cl_done = 0
        def _gen_letter(job):
            return job, generate_cover_letter(job, resume_text=resume_text)

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(_gen_letter, job): job for job in cl_jobs}
            for future in as_completed(futures):
                job, cl = future.result()
                cl_done += 1
                print(f"  [{cl_done}/{len(cl_jobs)}] {job['title']} @ {job.get('company','')}")
                if cl:
                    job["cover_letter"] = cl
    else:
        print("\n✍️  Cover letters skipped.")

    timings["cover_letters_s"] = round(_time.perf_counter() - _t, 1)
    return scored, qualified, timings


# ── Event relevance scoring ────────────────────────────────────────

def score_event(event: dict, resume_text: str = None) -> dict:
    """
    Score a networking event 1–10 for resume relevance using skill overlap.
    No LLM call — fast heuristic so the whole event list scores instantly.
    """
    if not resume_text:
        event["relevance_score"] = 5
        event["relevance_reason"] = "No resume loaded — default score"
        return event

    resume_skills = _extract_skills(resume_text)
    text = f"{event.get('title','')} {event.get('description','')} {event.get('organizer','')}".lower()
    event_skills = _extract_skills(text)

    overlap = resume_skills & event_skills
    score = 4
    reasons: list[str] = []

    # Domain keyword signals — capped so one event can't inflate to 10 on domains alone
    title = event.get("title", "").lower()
    domain_hits = {
        "ai":             ["ai", "artificial intelligence", "llm", "genai", "generative", "gpt", "claude", "openai"],
        "data":           ["data engineering", "data engineer", "etl", "pipeline", "spark", "databricks", "dbt"],
        "ml":             ["machine learning", "deep learning", "neural", "model", "tensorflow", "pytorch"],
        "cloud":          ["aws", "gcp", "azure", "cloud", "oci"],
        "analytics":      ["analytics", "business intelligence", "bi", "tableau", "power bi", "sql"],
        "networking":     ["networking", "career", "hiring", "job fair", "recruiter", "panel", "workshop"],
        "business":       ["mba", "business school", "chamber of commerce", "entrepreneurship", "startup", "leadership"],
        "university":     ["university", "college", "graduate", "research", "faculty", "academic", "stem"],
        "legal":          ["legal", "attorney", "lawyer", "law", "bar association", "litigation", "compliance",
                           "paralegal", "contract", "intellectual property", "regulatory"],
        "healthcare":     ["healthcare", "medical", "nursing", "clinical", "patient", "hospital", "health",
                           "pharmacy", "therapy", "wellness", "public health"],
        "sales":          ["sales", "business development", "revenue", "account executive", "prospecting",
                           "crm", "salesforce", "pipeline", "b2b", "b2c"],
        "marketing":      ["marketing", "seo", "content", "digital marketing", "brand", "campaign",
                           "social media", "growth", "demand generation"],
        "hr":             ["human resources", "hr", "recruiting", "talent", "people ops", "onboarding",
                           "benefits", "compensation", "employee"],
        "finance":        ["finance", "accounting", "fintech", "investment", "audit", "tax",
                           "financial planning", "cfo", "cpa", "budgeting"],
        "design":         ["design", "ux", "ui", "user experience", "product design", "figma",
                           "creative", "visual", "branding"],
        "product":        ["product management", "product manager", "roadmap", "user research",
                           "go-to-market", "product strategy"],
        "education":      ["education", "teaching", "curriculum", "e-learning", "training",
                           "professional development", "edtech"],
        "engineering":    ["engineering", "mechanical", "civil", "electrical", "structural",
                           "infrastructure", "construction", "manufacturing"],
    }
    matched_domains: list[str] = []
    domain_score = 0
    for domain, keywords in domain_hits.items():
        if any(kw in title for kw in keywords):
            matched_domains.append(domain)
            domain_score += 2
        elif any(kw in text for kw in keywords):
            matched_domains.append(domain)
            domain_score += 1

    domain_score = min(domain_score, 4)  # cap: no single event maxes out on domains alone
    score += domain_score
    if matched_domains:
        reasons.append(f"relevant topics: {', '.join(matched_domains[:3])}")

    # Skill overlap bonus
    if len(overlap) >= 3:
        score += 2
        reasons.append(f"strong skill overlap ({len(overlap)} skills)")
    elif len(overlap) >= 1:
        score += 1
        reasons.append(f"skill overlap ({len(overlap)} skills)")

    # Professional / seniority signals
    if any(w in text for w in ["professional", "senior", "executive", "leader", "director", "mentor"]):
        score += 1
        reasons.append("professional-level event")

    # Penalise student/beginner events
    if any(w in text for w in ["student", "beginner", "intro to", "101", "bootcamp"]):
        score -= 2
        reasons.append("beginner/student focus")

    event["relevance_score"] = max(1, min(10, score))
    event["relevance_reason"] = ", ".join(reasons) if reasons else "general professional event"
    return event


_NON_CITY_WORDS = {
    "confluence", "jira", "agile", "scrum", "python", "oracle", "remote",
    "united", "states", "american", "national", "federal", "university",
    "college", "institute", "center", "systems", "solutions", "services",
    "technologies", "analytics", "intelligence", "management", "operations",
}


def extract_cities_from_resume(resume_text: str) -> list[str]:
    """Pull unique cities mentioned in resume text (e.g. 'Houston, TX')."""
    if not resume_text:
        return ["Houston"]

    STATE_ABBREVS = (
        "AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|"
        "MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|"
        "SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC"
    )
    pattern = rf'\b([A-Z][a-zA-Z ]+?),\s*(?:{STATE_ABBREVS})\b'
    matches = re.findall(pattern, resume_text)

    seen: set[str] = set()
    cities: list[str] = []
    for city in matches:
        city = city.strip()
        if (2 < len(city) < 25
                and city.lower() not in seen
                and city.lower() not in _NON_CITY_WORDS
                and not any(w in city.lower() for w in _NON_CITY_WORDS)):
            seen.add(city.lower())
            cities.append(city)

    return cities if cities else ["Houston"]


def score_events(events: list[dict], resume_text: str = None) -> list[dict]:
    """Score events: Claude batch call when resume available, heuristic fallback."""
    if resume_text and events:
        try:
            return _score_events_claude(events, resume_text)
        except Exception as e:
            print(f"  Claude event scoring failed, falling back to heuristic: {e}")
            # Clear any partial Claude scores/reasons so heuristic is consistent
            for ev in events:
                ev.pop("relevance_score", None)
                ev.pop("relevance_reason", None)

    scored = [score_event(e, resume_text=resume_text) for e in events]
    scored.sort(key=lambda e: e.get("relevance_score") or 0, reverse=True)
    return scored


def _safe_score(val, default: int = 5) -> int:
    """Parse a Claude score value to int, clamped 1–10. Returns default on any error."""
    if val is None:
        return default
    try:
        return max(1, min(10, int(float(val))))
    except (TypeError, ValueError):
        return default


_CLAUDE_BATCH_SIZE = 20


def _score_events_claude(events: list[dict], resume_text: str) -> list[dict]:
    """Score events in batches via Claude Haiku for accuracy."""
    import anthropic
    from config import ANTHROPIC_API_KEY

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resume_excerpt = resume_text[:1500]

    for batch_start in range(0, len(events), _CLAUDE_BATCH_SIZE):
        batch = events[batch_start: batch_start + _CLAUDE_BATCH_SIZE]

        event_list = "\n".join(
            f"{i+1}. TITLE: {e.get('title','')}\n"
            f"   DESC: {(e.get('description','') or '')[:200]}"
            for i, e in enumerate(batch)
        )

        prompt = f"""Score these networking/professional events 1–10 for career value to this candidate.

RESUME:
{resume_excerpt}

EVENTS:
{event_list}

Scoring:
9–10: Directly relevant tech/data/AI event with strong networking or learning value
7–8: Professional networking, relevant industry, good career value
5–6: Tangentially relevant (business, MBA, adjacent field)
3–4: Social or general event, low career value
1–2: Concert, sports, entertainment

Return ONLY a JSON array in the same order, no explanation:
[{{"score": 8, "reason": "one short phrase"}}, ...]"""

        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = resp.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        scores = json.loads(raw)

        for i, e in enumerate(batch):
            if i < len(scores):
                e["relevance_score"] = _safe_score(scores[i].get("score"))
                e["relevance_reason"] = scores[i].get("reason") or ""

    events.sort(key=lambda e: e.get("relevance_score") or 0, reverse=True)
    return events
