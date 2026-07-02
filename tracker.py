"""
Supabase tracker — stores all jobs and application status.
All read/write functions accept an optional user_id for per-user data isolation.
When user_id is None (CLI mode), queries behave as before (no user filter).
"""
import hashlib
from collections import Counter

from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY


def get_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _scope_id(raw_id: str, user_id: str | None) -> str:
    """Make job IDs user-specific so each user has isolated rows.

    Same URL + same user  → same scoped ID  → dedup still works.
    Same URL + diff user  → different scoped ID → separate rows.
    No user_id (CLI mode) → original ID unchanged.

    Uses 8-char user suffix (4B combinations) to make collisions negligible.
    Total ID: 8 chars job hash + 8 chars user hash = 16 chars, same length.
    """
    if not user_id:
        return raw_id
    suffix = hashlib.md5(user_id.encode()).hexdigest()[:8]
    return raw_id[:8] + suffix


def upsert_jobs(jobs: list[dict], user_id: str | None = None):
    """Insert/update jobs. When user_id is provided, IDs are scoped per user."""
    sb = get_client()
    rows = []
    for j in jobs:
        scoped_id = _scope_id(j["id"], user_id)
        row = {
            "id": scoped_id,
            "source": j.get("source", ""),
            "title": j.get("title", ""),
            "company": j.get("company", ""),
            "location": j.get("location", ""),
            "url": j.get("url", ""),
            "description": (j.get("description") or "")[:5000],
            "posted_at": j.get("posted_at", ""),
            "status": j.get("status", "new"),
            "score": j.get("score"),
            "score_reason": j.get("score_reason", ""),
            "seniority": j.get("seniority", ""),
            "salary_match": j.get("salary_match", "Unknown"),
            "cover_letter": j.get("cover_letter", ""),
        }
        if user_id:
            row["user_id"] = user_id
        rows.append(row)

    if rows:
        sb.table("job_applications").upsert(rows, on_conflict="id").execute()
        print(f"  💾 Saved {len(rows)} jobs to Supabase")


def update_status(job_id: str, status: str, user_id: str | None = None):
    """Update application status."""
    sb = get_client()
    q = sb.table("job_applications").update({"status": status}).eq("id", job_id)
    if user_id:
        q = q.eq("user_id", user_id)
    q.execute()


def log_event(job_id: str, event_type: str, detail: str = "", user_id: str | None = None):
    """Append an outcome/feedback event. Safe no-op if table is missing."""
    sb = get_client()
    try:
        row = {"job_id": job_id, "event_type": event_type, "detail": detail}
        if user_id:
            row["user_id"] = user_id
        sb.table("application_events").insert(row).execute()
    except Exception:
        pass


def get_event_counts(user_id: str | None = None) -> dict[str, int]:
    """Return event counts by type for dashboard analytics."""
    sb = get_client()
    try:
        q = sb.table("application_events").select("event_type")
        if user_id:
            q = q.eq("user_id", user_id)
        result = q.execute()
    except Exception:
        return {}

    counts: dict[str, int] = {}
    for row in (result.data or []):
        key = row.get("event_type") or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def log_experiment_run(
    run_label: str,
    scoring_mode: str,
    hybrid_threshold: int,
    cover_letters_enabled: bool,
    jobs_scraped: int,
    jobs_new: int,
    jobs_qualified: int,
    note: str = "",
    user_id: str | None = None,
):
    """Persist one pipeline experiment run. Safe no-op if table is missing."""
    sb = get_client()
    try:
        row = {
            "run_label": run_label,
            "scoring_mode": scoring_mode,
            "hybrid_threshold": hybrid_threshold,
            "cover_letters_enabled": bool(cover_letters_enabled),
            "jobs_scraped": int(jobs_scraped),
            "jobs_new": int(jobs_new),
            "jobs_qualified": int(jobs_qualified),
            "note": note or "",
        }
        if user_id:
            row["user_id"] = user_id
        sb.table("pipeline_runs").insert(row).execute()
    except Exception:
        pass


def get_recent_runs(limit: int = 10, user_id: str | None = None) -> list[dict]:
    """Fetch recent experiment runs for comparison."""
    sb = get_client()
    try:
        q = sb.table("pipeline_runs").select("*").order("created_at", desc=True).limit(limit)
        if user_id:
            q = q.eq("user_id", user_id)
        return q.execute().data or []
    except Exception:
        return []


def _chunked(ids: list, size: int):
    for i in range(0, len(ids), size):
        yield ids[i : i + size]


def _event_is_positive(event_type: str, detail: str) -> bool:
    d = (detail or "").lower()
    et = (event_type or "").lower()
    if et in ("applied", "recruiter_response", "interview_scheduled"):
        return True
    if et == "status_change" and ("-> applied" in d or "-> interview" in d):
        return True
    return False


def _event_is_negative(event_type: str, detail: str) -> bool:
    d = (detail or "").lower()
    et = (event_type or "").lower()
    if et in ("rejected", "no_response_14d"):
        return True
    if et == "status_change" and ("-> skipped" in d or "-> rejected" in d):
        return True
    return False


def get_personalization_context(event_limit: int = 400, user_id: str | None = None) -> dict:
    """Build lightweight signals from events + job rows for queue reranking."""
    sb = get_client()
    try:
        q = (
            sb.table("application_events")
            .select("job_id, event_type, detail, created_at")
            .order("created_at", desc=True)
            .limit(event_limit)
        )
        if user_id:
            q = q.eq("user_id", user_id)
        ev_res = q.execute()
    except Exception:
        return {"has_signals": False}

    events = ev_res.data or []
    job_ids = list({e.get("job_id") for e in events if e.get("job_id")})
    if not job_ids:
        return {"has_signals": False}

    jobs_by_id: dict[str, dict] = {}
    try:
        for chunk in _chunked(job_ids, 100):
            q = sb.table("job_applications").select("id, company, title, source").in_("id", chunk)
            if user_id:
                q = q.eq("user_id", user_id)
            for row in q.execute().data or []:
                jobs_by_id[row["id"]] = row
    except Exception:
        return {"has_signals": False}

    pos_companies: set[str] = set()
    neg_companies: set[str] = set()
    pos_sources: Counter[str] = Counter()
    title_tokens: Counter[str] = Counter()

    for e in events:
        jid = e.get("job_id")
        job = jobs_by_id.get(jid)
        if not job:
            continue
        company = (job.get("company") or "").lower().strip()
        title = (job.get("title") or "").lower()
        src = (job.get("source") or "").strip() or "unknown"
        et = e.get("event_type") or ""
        detail = e.get("detail") or ""

        if _event_is_positive(et, detail):
            if company:
                pos_companies.add(company)
            if src:
                pos_sources[src] += 1
            for w in title.replace("/", " ").split():
                w = w.strip(".,()[]")
                if len(w) > 3:
                    title_tokens[w] += 1
        elif _event_is_negative(et, detail):
            if company:
                neg_companies.add(company)

    top_tokens = {t for t, _ in title_tokens.most_common(25)}
    good_sources = {s for s, c in pos_sources.most_common(5) if c >= 1}

    has_signals = bool(pos_companies or neg_companies or top_tokens or good_sources)
    return {
        "has_signals": has_signals,
        "pos_companies": pos_companies,
        "neg_companies": neg_companies,
        "good_sources": good_sources,
        "title_tokens": top_tokens,
    }


def personalization_bonus(job: dict, ctx: dict, weights: dict | None = None) -> tuple[float, str]:
    """Return (bonus_points, short_reason) for reranking; bonus typically within [-1, 2]."""
    if not ctx.get("has_signals"):
        return 0.0, ""

    w = weights or {}
    pos_company_w = float(w.get("pos_company", 1.2))
    neg_company_w = float(w.get("neg_company", -0.9))
    good_source_w = float(w.get("good_source", 0.35))
    title_token_per_hit_w = float(w.get("title_token_per_hit", 0.2))
    title_token_cap_w = float(w.get("title_token_cap", 1.0))
    title_min_hits = int(w.get("title_min_hits", 2))

    company = (job.get("company") or "").lower().strip()
    title = (job.get("title") or "").lower()
    src = (job.get("source") or "").strip() or "unknown"

    bonus = 0.0
    reasons: list[str] = []

    if company and company in ctx.get("pos_companies", set()):
        bonus += pos_company_w
        reasons.append("company you engaged positively before")
    if company and company in ctx.get("neg_companies", set()):
        bonus += neg_company_w
        reasons.append("company you skipped/rejected before")

    if src in ctx.get("good_sources", set()):
        bonus += good_source_w
        reasons.append("source with past positive outcomes")

    tokens = ctx.get("title_tokens") or set()
    if tokens:
        hits = sum(1 for w in title.replace("/", " ").split() if w.strip(".,()[]") in tokens)
        if hits >= title_min_hits:
            tbonus = min(title_token_cap_w, title_token_per_hit_w * hits)
            bonus += tbonus
            reasons.append("title overlap with roles you liked")

    hint = " · ".join(reasons) if reasons else ""
    return round(bonus, 2), hint


def rank_queue_with_personalization(
    jobs: list[dict],
    *,
    weights: dict | None = None,
    ctx: dict | None = None,
    user_id: str | None = None,
) -> list[dict]:
    """Mutate each job with _personal_bonus, _effective_score, _personal_hint; sort descending."""
    ctx = ctx or get_personalization_context(user_id=user_id)
    for j in jobs:
        b, hint = personalization_bonus(j, ctx, weights=weights)
        base = float(j.get("score") or 0)
        j["_personal_bonus"] = b
        j["_effective_score"] = round(base + b, 2)
        j["_personal_hint"] = hint
    jobs.sort(key=lambda x: (x.get("_effective_score") or 0), reverse=True)
    return jobs


def get_source_health(apps: list[dict] | None = None, review_min_score: int = 7,
                      user_id: str | None = None) -> list[dict]:
    """Per-source totals, avg score, qualified count, and review queue share."""
    if apps is None:
        apps = get_all_applications(user_id=user_id)
    buckets: dict[str, dict] = {}
    for row in apps:
        src = (row.get("source") or "unknown").strip() or "unknown"
        if src not in buckets:
            buckets[src] = {"n": 0, "scores": [], "qualified": 0, "in_review": 0}
        b = buckets[src]
        b["n"] += 1
        sc = row.get("score")
        if sc is not None:
            b["scores"].append(int(sc))
        if (sc or 0) >= review_min_score:
            b["qualified"] += 1
        if row.get("status") == "new" and (sc or 0) >= review_min_score:
            b["in_review"] += 1

    out: list[dict] = []
    for src, b in sorted(buckets.items(), key=lambda x: -x[1]["n"]):
        scores = b["scores"]
        n = b["n"]
        out.append({
            "source": src,
            "total": n,
            "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
            "qualified_7plus": b["qualified"],
            "qualified_pct": round(100.0 * b["qualified"] / n, 1) if n else 0.0,
            "in_review_queue": b["in_review"],
        })
    return out


def get_review_queue(min_score: int = 7, user_id: str | None = None) -> list[dict]:
    """Fetch jobs pending review, deduped by (title, company)."""
    sb = get_client()
    q = (
        sb.table("job_applications")
        .select("*")
        .eq("status", "new")
        .gte("score", min_score)
        .order("score", desc=True)
    )
    if user_id:
        q = q.eq("user_id", user_id)
    rows = q.execute().data or []

    seen: dict[tuple, dict] = {}
    for row in rows:
        key = (
            (row.get("title") or "").lower().strip(),
            (row.get("company") or "").lower().strip(),
        )
        if key not in seen or (row.get("score") or 0) > (seen[key].get("score") or 0):
            seen[key] = row
    return list(seen.values())


def get_manual_queue(user_id: str | None = None) -> list[dict]:
    """Fetch jobs that need manual application."""
    sb = get_client()
    q = (
        sb.table("job_applications")
        .select("*")
        .eq("status", "manual_review")
        .order("score", desc=True)
    )
    if user_id:
        q = q.eq("user_id", user_id)
    return q.execute().data or []


def get_seen_ids(user_id: str | None = None) -> set[str]:
    """Return all job IDs already stored (scoped to user when provided)."""
    sb = get_client()
    q = sb.table("job_applications").select("id")
    if user_id:
        q = q.eq("user_id", user_id)
    result = q.execute()
    return {row["id"] for row in (result.data or [])}


def clear_queue(user_id: str | None = None):
    """Delete all status='new' jobs for the user (clears the review queue)."""
    sb = get_client()
    q = sb.table("job_applications").delete().eq("status", "new")
    if user_id:
        q = q.eq("user_id", user_id)
    q.execute()


def clear_all_data(user_id: str | None = None):
    """Delete all jobs, events, and pipeline runs for the user."""
    sb = get_client()
    if user_id:
        # Delete events for this user's jobs first (FK constraint)
        sb.table("application_events").delete().eq("user_id", user_id).execute()
        sb.table("job_applications").delete().eq("user_id", user_id).execute()
        sb.table("pipeline_runs").delete().eq("user_id", user_id).execute()
    else:
        # CLI / unscoped — wipe rows with no user_id
        sb.table("application_events").delete().is_("user_id", "null").execute()
        sb.table("job_applications").delete().is_("user_id", "null").execute()
        sb.table("pipeline_runs").delete().is_("user_id", "null").execute()


def get_all_applications(user_id: str | None = None) -> list[dict]:
    sb = get_client()
    q = sb.table("job_applications").select("*").order("score", desc=True)
    if user_id:
        q = q.eq("user_id", user_id)
    return q.execute().data or []
