"""
Embedding-based job scorer — Phase 1 of the ML scoring roadmap.

Uses TF-IDF cosine similarity (sklearn) + feature engineering to score jobs
1-10 without any LLM calls. Designed to replace the cheap heuristic in hybrid
mode, routing only the uncertain band (5-7) to Claude Sonnet.

Architecture:
  Pass 1  — heuristic pre-filter (agent.py, existing, keeps clear mismatches)
  Pass 2  — this file (TF-IDF similarity, no API cost)
  Pass 3  — Claude Sonnet (uncertain 5-7 band only)

Upgrade path (see BUILDPLAN.md):
  1k scored jobs  → swap TF-IDF for sentence-transformers + XGBoost on Sonnet labels
  5k signals      → fine-tune DistilBERT on (resume, description) → apply probability
"""
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# Similarity score ceiling for normalization.
# Most resume-vs-job-description pairs land between 0.05–0.35.
# Jobs at or above this ceiling get the full similarity contribution.
_SIM_CEIL = 0.30


def _tfidf_sim(text_a: str, text_b: str) -> float:
    """Cosine similarity between two documents via TF-IDF."""
    if not text_a or not text_b:
        return 0.0
    try:
        vec = TfidfVectorizer(
            max_features=4000,
            ngram_range=(1, 2),
            stop_words="english",
            sublinear_tf=True,  # log normalization — reduces impact of very common terms
        )
        mat = vec.fit_transform([text_a, text_b])
        return float(cosine_similarity(mat[0:1], mat[1:2])[0][0])
    except Exception:
        return 0.0


def score_job_embed(
    job: dict,
    resume_text: str = None,
    min_salary: int = 0,
    target_roles: list[str] = None,
) -> dict:
    """
    Score a single job 1-10 using TF-IDF similarity + feature engineering.
    Mutates job in-place and returns it (same contract as score_job_cheap).

    Fields set:
      score, score_reason, seniority, salary_match, scored_by
      _embed_score, _tfidf_sim, _skill_ratio  (for future XGBoost training)
    """
    # Lazy import avoids circular dependency (agent.py imports embedder lazily too)
    from agent import _extract_skills, _role_matches_title

    resume = (resume_text or "").lower()
    title = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()
    job_text = f"{title} {description}"

    # ── TF-IDF cosine similarity ──────────────────────────────────
    sim = _tfidf_sim(resume, job_text)
    normalized_sim = min(sim / _SIM_CEIL, 1.0)  # 0-1, ceiling at _SIM_CEIL

    # ── Skill overlap ─────────────────────────────────────────────
    resume_skills = _extract_skills(resume) if resume else frozenset()
    job_skills = _extract_skills(job_text)
    skill_ratio = len(resume_skills & job_skills) / max(len(job_skills), 1) if job_skills else 0.0

    # ── Title / role fit ──────────────────────────────────────────
    roles = [r.lower() for r in (target_roles or [])]
    if roles and _role_matches_title(title, roles):
        title_boost = 1.0
        title_reason = "target role in title"
    elif roles and any(r in description[:200] for r in roles):
        title_boost = 0.5
        title_reason = "target role in description"
    else:
        title_boost = 0.0
        title_reason = "role not matched"

    # ── Salary filter ─────────────────────────────────────────────
    salary_nums = re.findall(r"\$?\s?(\d{2,3})\s?[kK]\b", job_text)
    effective_min = min_salary or 0
    salary_penalty = 0.0
    salary_reason = ""
    salary_match = "Unknown"
    if salary_nums:
        high_k = max(int(n) for n in salary_nums) * 1000
        if effective_min and high_k < effective_min:
            salary_penalty = 1.0
            salary_reason = "salary below minimum"
            salary_match = "No"
        else:
            salary_match = "Yes"

    # ── Combine → 1-10 ───────────────────────────────────────────
    # Weights: similarity (6 pts) + skill overlap (2 pts) + role fit (1 pt) + base (1 pt)
    raw = (
        normalized_sim * 6.0
        + skill_ratio * 2.0
        + title_boost
        + 1.0           # minimum base so floor is ~1
        - salary_penalty
    )
    score = max(1, min(10, round(raw)))

    # ── Reasoning ─────────────────────────────────────────────────
    if sim >= 0.20:
        sim_label = f"strong text match ({sim:.2f})"
    elif sim >= 0.10:
        sim_label = f"moderate text match ({sim:.2f})"
    else:
        sim_label = f"low text overlap ({sim:.2f})"

    overlap_count = len(resume_skills & job_skills)
    skill_label = f"{overlap_count} skills matched" if resume_skills else "no resume skills"

    parts = [sim_label, skill_label]
    if title_reason:
        parts.append(title_reason)
    if salary_reason:
        parts.append(salary_reason)

    # ── Persist ───────────────────────────────────────────────────
    job["score"]        = score
    job["score_reason"] = ", ".join(parts)
    job["seniority"]    = "Unknown"
    job["salary_match"] = salary_match
    job["scored_by"]    = "embed-tfidf-v1"

    # Training signal fields — not yet in DB schema, used for future XGBoost
    job["_embed_score"]  = score
    job["_tfidf_sim"]    = round(sim, 4)
    job["_skill_ratio"]  = round(skill_ratio, 4)

    return job
