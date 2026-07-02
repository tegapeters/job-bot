"""
User session persistence — stores resume + target roles in Supabase
keyed by a UUID carried in st.query_params so refreshes restore state.

Table (run once in Supabase SQL editor):
    create table if not exists user_sessions (
        id          text primary key,
        resume_text text,
        target_roles jsonb,
        updated_at  timestamptz default now()
    );
"""
import uuid
from datetime import datetime, timezone
from tracker import get_client


def save_session(uid: str, resume_text: str, target_roles: list[str]) -> str:
    """Upsert session. Returns the uid."""
    sb = get_client()
    sb.table("user_sessions").upsert({
        "id": uid,
        "resume_text": resume_text,
        "target_roles": target_roles,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="id").execute()
    return uid


def load_session(uid: str) -> dict | None:
    """Return {resume_text, target_roles} or None if not found."""
    sb = get_client()
    result = sb.table("user_sessions").select("resume_text,target_roles").eq("id", uid).execute()
    if result.data:
        return result.data[0]
    return None


def clear_session(uid: str):
    """Delete the saved resume/roles for this user so Setup starts blank."""
    sb = get_client()
    try:
        sb.table("user_sessions").delete().eq("id", uid).execute()
    except Exception:
        pass


def new_uid() -> str:
    return uuid.uuid4().hex[:16]
