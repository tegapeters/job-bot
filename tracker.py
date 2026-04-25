"""
Supabase tracker — stores all jobs and application status
Table: job_applications
"""
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY


def get_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def upsert_jobs(jobs: list[dict]):
    """Insert new jobs, skip duplicates."""
    sb = get_client()
    rows = []
    for j in jobs:
        rows.append({
            "id": j["id"],
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
        })

    if rows:
        sb.table("job_applications").upsert(
            rows,
            on_conflict="id",
        ).execute()
        print(f"  💾 Saved {len(rows)} jobs to Supabase")


def update_status(job_id: str, status: str):
    """Update application status: new | reviewing | applied | rejected | interview"""
    sb = get_client()
    sb.table("job_applications").update({"status": status}).eq("id", job_id).execute()


def get_review_queue(min_score: int = 7) -> list[dict]:
    """Fetch jobs pending review."""
    sb = get_client()
    result = (
        sb.table("job_applications")
        .select("*")
        .eq("status", "new")
        .gte("score", min_score)
        .order("score", desc=True)
        .execute()
    )
    return result.data or []


def get_manual_queue() -> list[dict]:
    """Fetch jobs that need manual application (no Easy Apply)."""
    sb = get_client()
    result = (
        sb.table("job_applications")
        .select("*")
        .eq("status", "manual_review")
        .order("score", desc=True)
        .execute()
    )
    return result.data or []


def get_seen_ids() -> set[str]:
    """Return all job IDs already stored in Supabase."""
    sb = get_client()
    result = sb.table("job_applications").select("id").execute()
    return {row["id"] for row in (result.data or [])}


def get_all_applications() -> list[dict]:
    sb = get_client()
    result = (
        sb.table("job_applications")
        .select("*")
        .order("score", desc=True)
        .execute()
    )
    return result.data or []
