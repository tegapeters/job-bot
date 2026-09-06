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

To enable the academic (faculty/adjunct) vertical, add:
    alter table user_sessions add column if not exists vertical text default 'tech';
    alter table user_sessions add column if not exists schedule_pref text;
Both are handled defensively below — the app still works if the columns are
absent (the vertical just won't persist across refreshes until they're added).
"""
import uuid
from datetime import datetime, timezone
from tracker import get_client


def save_session(uid: str, resume_text: str, target_roles: list[str],
                 preferred_locations: list[str] | None = None,
                 vertical: str | None = None,
                 schedule_pref: str | None = None) -> str:
    """Upsert session. Returns the uid.

    `vertical` and `schedule_pref` are written when the columns exist; if they
    don't, the upsert is retried without them so saving still succeeds."""
    sb = get_client()
    row = {
        "id": uid,
        "resume_text": resume_text,
        "target_roles": target_roles,
        "preferred_locations": preferred_locations or [],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if vertical is not None:
        row["vertical"] = vertical
    if schedule_pref is not None:
        row["schedule_pref"] = schedule_pref
    try:
        sb.table("user_sessions").upsert(row, on_conflict="id").execute()
    except Exception:
        # Column(s) missing from schema cache — drop the optional ones and retry.
        for k in ("vertical", "schedule_pref"):
            row.pop(k, None)
        sb.table("user_sessions").upsert(row, on_conflict="id").execute()
    return uid


def load_session(uid: str) -> dict | None:
    """Return {resume_text, target_roles, gmail_scan_enabled, preferred_locations,
    vertical, schedule_pref} or None if not found. Falls back gracefully when
    the vertical columns are absent."""
    sb = get_client()
    try:
        result = sb.table("user_sessions").select(
            "resume_text,target_roles,gmail_scan_enabled,preferred_locations,vertical,schedule_pref"
        ).eq("id", uid).execute()
    except Exception:
        result = sb.table("user_sessions").select(
            "resume_text,target_roles,gmail_scan_enabled,preferred_locations"
        ).eq("id", uid).execute()
    if result.data:
        return result.data[0]
    return None


def save_gmail_opt_in(uid: str, enabled: bool) -> None:
    """Persist the Gmail rejection-scan opt-in flag for a user."""
    sb = get_client()
    try:
        sb.table("user_sessions").upsert({
            "id": uid,
            "gmail_scan_enabled": enabled,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="id").execute()
    except Exception:
        pass


def clear_session(uid: str):
    """Delete the saved resume/roles for this user so Setup starts blank."""
    sb = get_client()
    try:
        sb.table("user_sessions").delete().eq("id", uid).execute()
    except Exception:
        pass


def new_uid() -> str:
    return uuid.uuid4().hex[:16]


def save_chat_history(user_id: str, messages: list[dict]) -> None:
    """Upsert assistant chat history for a user."""
    sb = get_client()
    sb.table("assistant_chats").upsert({
        "user_id": user_id,
        "messages": messages,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="user_id").execute()


def load_chat_history(user_id: str) -> list[dict]:
    """Return saved chat messages for a user, or empty list."""
    sb = get_client()
    try:
        result = sb.table("assistant_chats").select("messages").eq("user_id", user_id).execute()
        if result.data:
            return result.data[0].get("messages") or []
    except Exception:
        pass
    return []


def clear_chat_history(user_id: str) -> None:
    """Delete saved chat history for a user."""
    sb = get_client()
    try:
        sb.table("assistant_chats").delete().eq("user_id", user_id).execute()
    except Exception:
        pass
