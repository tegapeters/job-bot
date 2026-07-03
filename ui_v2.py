"""
Job Pal — Streamlit UI v2 (Techturi branded)
Run: streamlit run ui_v2.py
"""
import io
import re
from datetime import datetime, timezone
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tracker import (
    get_all_applications, get_review_queue,
    update_status, get_seen_ids, log_event, get_event_counts,
    log_experiment_run, get_recent_runs,
    rank_queue_with_personalization, get_source_health,
    clear_queue, upsert_events, get_events, update_event_status,
    _scope_id,
)
from sessions import save_session, load_session, clear_session, new_uid
from auth import render_auth_wall, restore_user_session, get_user_id, get_user_email, sign_out
from config import REVIEW_MIN_SCORE

# ── Page config ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Pal · techturi",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="auto",
)

# ── Brand styles ───────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..900;1,9..144,300..900&family=JetBrains+Mono:wght@400;500;600&display=swap');
  /* ── Base ── */
  html, body, [data-testid="stApp"] { background: #0A0A0B; }
  [data-testid="stSidebar"] {
    background: #0f0f10;
    border-right: 1px solid #1f1f22;
  }
  [data-testid="stSidebar"] > div { padding-top: 0 !important; }

  /* ── Logo ── */
  .tt-logo {
    font-family: 'JetBrains Mono', monospace;
    font-size: 20px;
    font-weight: 500;
    color: #F5F4EE;
    letter-spacing: -0.01em;
    padding: 28px 20px 0;
  }
  .tt-logo .bracket, .tt-logo .dot { color: #D4FF3A; }
  .tt-product {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.25em;
    color: #4A4A45;
    text-transform: uppercase;
    padding: 6px 20px 20px;
    border-bottom: 1px solid #1f1f22;
    margin-bottom: 12px;
  }

  /* ── Page header ── */
  .page-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding-bottom: 20px;
    border-bottom: 1px solid #1f1f22;
    margin-bottom: 28px;
  }
  .page-header .eyebrow {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.25em;
    color: #D4FF3A;
    text-transform: uppercase;
    margin-bottom: 4px;
  }
  .page-header h1 {
    font-family: 'Fraunces', serif !important;
    font-size: 40px !important;
    font-weight: 300 !important;
    color: #F5F4EE !important;
    letter-spacing: -0.03em !important;
    line-height: 1 !important;
    margin: 0 !important;
    padding: 0 !important;
  }
  .page-header h1 em {
    font-style: italic;
    color: #D4FF3A;
  }

  /* ── Metric cards ── */
  .metric-card {
    background: #131315;
    border: 1px solid #1f1f22;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 12px;
  }
  .metric-card .label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: #4A4A45;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    margin-bottom: 8px;
  }
  .metric-card .value {
    font-family: 'Fraunces', serif;
    font-size: 36px;
    font-weight: 400;
    color: #F5F4EE;
    line-height: 1;
  }
  .metric-card .sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: #4A4A45;
    margin-top: 6px;
  }
  .metric-card.accent { border-left: 3px solid #D4FF3A; }

  /* ── Score / status badges ── */
  .score-high { color: #D4FF3A; font-weight: 600; font-family: 'JetBrains Mono', monospace; }
  .score-mid  { color: #f5c518; font-weight: 600; font-family: 'JetBrains Mono', monospace; }
  .score-low  { color: #ff6b6b; font-weight: 600; font-family: 'JetBrains Mono', monospace; }
  .tag {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    padding: 3px 10px;
    border-radius: 2px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-right: 4px;
  }
  .tag-new                { background: #1a1f0a; color: #D4FF3A; border: 1px solid #2a3510; }
  .tag-applied            { background: #0a1a1f; color: #3ad4ff; border: 1px solid #102a35; }
  .tag-interview          { background: #1a0f1a; color: #d43aff; border: 1px solid #2a1035; }
  .tag-rejected           { background: #1f0a0a; color: #ff3a3a; border: 1px solid #350f0f; }
  .tag-skipped            { background: #1a1a1a; color: #666; border: 1px solid #333; }
  .tag-application_closed { background: #1a1208; color: #ff9a3a; border: 1px solid #352010; }

  /* ── Cover letter block ── */
  .cover-letter {
    background: #131315;
    border: 1px solid #1f1f22;
    border-left: 3px solid #D4FF3A;
    border-radius: 4px;
    padding: 20px 24px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    color: #c8c8c0;
    white-space: pre-wrap;
    line-height: 1.8;
  }

  /* ── Section divider label ── */
  .section-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.2em;
    color: #4A4A45;
    text-transform: uppercase;
    margin-bottom: 16px;
    padding-bottom: 10px;
    border-bottom: 1px solid #1f1f22;
  }

  /* ── Pipeline status box ── */
  .pipeline-card {
    background: #131315;
    border: 1px solid #1f1f22;
    border-radius: 8px;
    padding: 24px;
  }
  .pipeline-card h4 {
    font-family: 'Fraunces', serif !important;
    font-size: 22px !important;
    font-weight: 400 !important;
    color: #F5F4EE !important;
    margin: 0 0 8px 0 !important;
  }
  .pipeline-card p {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: #8B8B85;
    line-height: 1.7;
    margin: 0 !important;
  }

  /* ── All buttons — base reset ── */
  div.stButton > button,
  div[data-testid="stButton"] > button,
  div[data-testid="stDownloadButton"] > button,
  div[data-testid="stFormSubmitButton"] > button,
  [data-testid="baseButton-primary"],
  [data-testid="baseButton-secondary"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    letter-spacing: 0.05em !important;
    border-radius: 3px !important;
    transition: background 0.15s, border-color 0.15s !important;
  }

  /* ── Primary buttons (white) ── */
  div.stButton > button[kind="primary"],
  div[data-testid="stButton"] > button[kind="primary"],
  div[data-testid="stFormSubmitButton"] > button[kind="primary"],
  [data-testid="baseButton-primary"] {
    background: #F5F4EE !important;
    color: #0A0A0B !important;
    border: 1px solid #F5F4EE !important;
    font-weight: 600 !important;
  }
  div.stButton > button[kind="primary"]:hover,
  div[data-testid="stButton"] > button[kind="primary"]:hover,
  [data-testid="baseButton-primary"]:hover {
    background: #ffffff !important;
    border-color: #ffffff !important;
  }

  /* ── Secondary / default buttons (dark grey) ── */
  div.stButton > button[kind="secondary"],
  div.stButton > button:not([kind="primary"]),
  div[data-testid="stButton"] > button[kind="secondary"],
  div[data-testid="stDownloadButton"] > button,
  [data-testid="baseButton-secondary"] {
    background: #1f1f22 !important;
    color: #c8c8c0 !important;
    border: 1px solid #2e2e32 !important;
    font-weight: 500 !important;
  }
  div.stButton > button[kind="secondary"]:hover,
  div.stButton > button:not([kind="primary"]):hover,
  div[data-testid="stButton"] > button[kind="secondary"]:hover,
  div[data-testid="stDownloadButton"] > button:hover,
  [data-testid="baseButton-secondary"]:hover {
    background: #2a2a2e !important;
    border-color: #3e3e44 !important;
    color: #F5F4EE !important;
  }

  /* ── Multiselect tags ── */
  [data-testid="stMultiSelect"] span[data-baseweb="tag"],
  span[data-baseweb="tag"] {
    background: #2a2a2e !important;
    color: #c8c8c0 !important;
    border: 1px solid #3e3e44 !important;
  }
  [data-testid="stMultiSelect"] span[data-baseweb="tag"] span,
  span[data-baseweb="tag"] span {
    color: #c8c8c0 !important;
  }

  /* ── Slider thumb + track ── */
  [data-testid="stSlider"] [role="slider"] {
    background: #c8c8c0 !important;
    border-color: #c8c8c0 !important;
  }
  [data-testid="stSlider"] [data-testid="stSliderThumbValue"] {
    color: #c8c8c0 !important;
  }

  /* ── Footer ── */
  .tt-footer {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: #4A4A45;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    padding-top: 8px;
    border-top: 1px solid #1f1f22;
    margin-top: 4px;
  }

  /* ══════════════════════════════════════════════════════════════
     MOBILE  (≤ 768px)
     ══════════════════════════════════════════════════════════════ */
  @media (max-width: 768px) {

    /* ── Main content padding ── */
    .main .block-container {
      padding-left: 16px !important;
      padding-right: 16px !important;
      padding-top: 16px !important;
    }

    /* ── Stack all Streamlit columns ── */
    [data-testid="stHorizontalBlock"] {
      flex-wrap: wrap !important;
      gap: 0 !important;
    }
    [data-testid="column"] {
      min-width: 100% !important;
      width: 100% !important;
      flex: 1 1 100% !important;
    }

    /* ── Page header ── */
    .page-header { margin-bottom: 20px; padding-bottom: 16px; }
    .page-header h1 {
      font-size: 28px !important;
      letter-spacing: -0.02em !important;
    }

    /* ── Auth / landing hero ── */
    div[style*="max-width:440px"],
    div[style*="max-width: 440px"] {
      margin-top: 32px !important;
    }
    div[style*="font-size:42px"],
    div[style*="font-size: 42px"] {
      font-size: 30px !important;
    }

    /* ── Metric cards: smaller value, tighter padding ── */
    .metric-card { padding: 14px 16px; }
    .metric-card .value { font-size: 26px; }

    /* ── Buttons: bigger tap targets ── */
    div.stButton > button,
    div[data-testid="stButton"] > button,
    div[data-testid="stDownloadButton"] > button,
    div[data-testid="stFormSubmitButton"] > button {
      min-height: 48px !important;
      font-size: 13px !important;
    }

    /* ── Cover letter: smaller mono text ── */
    .cover-letter {
      font-size: 11px !important;
      padding: 14px 16px !important;
      line-height: 1.7 !important;
    }

    /* ── Pipeline card ── */
    .pipeline-card { padding: 16px; }
    .pipeline-card h4 { font-size: 18px !important; }

    /* ── Section label spacing ── */
    .section-label { margin-bottom: 12px; }

    /* ── Tabs: smaller text ── */
    [data-testid="stTabs"] button {
      font-size: 11px !important;
      padding: 6px 10px !important;
    }

    /* ── Expander header ── */
    [data-testid="stExpander"] summary {
      font-size: 13px !important;
      padding: 10px 14px !important;
    }

    /* ── Sidebar logo on mobile ── */
    .tt-logo { font-size: 17px !important; padding: 20px 16px 0 !important; }
    .tt-product { padding: 4px 16px 16px !important; }

    /* ── Sliders: wider touch area ── */
    [data-testid="stSlider"] [role="slider"] {
      width: 22px !important;
      height: 22px !important;
    }

    /* ── Dataframes: allow horizontal scroll ── */
    [data-testid="stDataFrame"] {
      overflow-x: auto !important;
    }
    [data-testid="stDataFrame"] > div {
      min-width: 480px;
    }
  }
</style>
""", unsafe_allow_html=True)


# ── Auth wall — must be authenticated to use the app ──────────────
render_auth_wall()
restore_user_session()
_USER_ID = get_user_id()  # set once per Streamlit run, passed to all tracker calls


# ── Session persistence: restore from ?uid= query param ───────────
def _try_restore_session():
    """On first load, if ?uid= is in the URL, pull resume from Supabase."""
    if st.session_state.get("_session_restored"):
        return  # already ran this run
    st.session_state["_session_restored"] = True

    uid = st.query_params.get("uid")
    if not uid:
        return
    if st.session_state.get("resume_text"):
        return  # already have resume in memory

    try:
        data = load_session(uid)
        if data and data.get("resume_text"):
            st.session_state["resume_text"] = data["resume_text"]
            st.session_state["session_uid"] = uid
            if data.get("target_roles"):
                st.session_state["target_roles"] = data["target_roles"]
    except Exception:
        pass  # silently skip — DB down or uid not found

_try_restore_session()

# ── Sidebar: Techturi-branded nav ──────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="tt-logo">
      <span class="bracket">[</span>techturi<span class="dot">.</span><span class="bracket">]</span>
    </div>
    <div class="tt-product">Job Pal</div>
    """, unsafe_allow_html=True)

    # Show logged-in user + resume status
    user_email = get_user_email() or ""
    st.markdown(
        f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#4A4A45;'
        f'letter-spacing:0.1em;padding:0 20px 4px;overflow:hidden;text-overflow:ellipsis;'
        f'white-space:nowrap" title="{user_email}">{user_email}</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.get("resume_text"):
        st.markdown('<div style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#D4FF3A;letter-spacing:0.15em;padding:0 20px 12px">✓ RESUME LOADED</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#ff6b6b;letter-spacing:0.15em;padding:0 20px 12px">⚠ NO RESUME — START HERE</div>', unsafe_allow_html=True)

    page = st.radio(
        "Navigate",
        ["Setup", "Run Pipeline", "Review Queue", "Applied", "Interviews", "Events", "Dashboard", "All Applications"],
        label_visibility="collapsed",
    )

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Sign Out", use_container_width=True, key="sidebar_signout"):
        sign_out()
        st.rerun()
    st.markdown('<div class="tt-footer" style="margin-top:8px">techturi.org · Tega Eshareturi</div>', unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────
def score_badge(score):
    score = score or 0
    cls = "score-high" if score >= 8 else "score-mid" if score >= 6 else "score-low"
    return f'<span class="{cls}">{score}/10</span>'

def status_tag(status):
    cls = f"tag tag-{status}" if status in ("new","applied","interview","rejected","skipped","application_closed") else "tag"
    label = "closed" if status == "application_closed" else status
    return f'<span class="{cls}">{label}</span>'

def safe_get_apps():
    """Fetch all applications for the current user."""
    try:
        return get_all_applications(user_id=_USER_ID)
    except Exception as e:
        st.error(f"Cannot connect to database. Check Supabase secrets in Streamlit Cloud settings. Error: `{e}`")
        st.stop()

def safe_get_queue(min_score=8):
    try:
        return get_review_queue(min_score=min_score, user_id=_USER_ID)
    except Exception as e:
        st.error(f"Cannot connect to database. Check Supabase secrets. Error: `{e}`")
        st.stop()

def _days_in_queue(job: dict) -> int | None:
    raw = job.get("created_at")
    if not raw:
        return None
    try:
        created = datetime.fromisoformat(raw)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - created).days
    except Exception:
        return None


def job_card(job, key_prefix, next_statuses, expanded=False):
    """Render a full job card with details, cover letter, and status controls."""
    score = job.get("score") or 0
    icon = "🟢" if score >= 8 else "🟡" if score >= 6 else "🔴"
    eff = job.get("_effective_score")
    title_suffix = f"  (rank {eff})" if eff is not None and eff != score else ""
    days = _days_in_queue(job)
    days_label = f"  ·  {days}d" if days is not None else ""
    with st.expander(
        f"{icon}  {score}/10{title_suffix}  —  {job['title']} @ {job.get('company', '?')}{days_label}",
        expanded=expanded,
    ):
        hint = job.get("_personal_hint")
        bonus = job.get("_personal_bonus")
        if hint or (bonus and bonus != 0):
            st.caption(
                f"Personalized Δ {bonus:+.2f} — {hint}" if hint else f"Personalized Δ {bonus:+.2f}"
            )

        if days is not None:
            color = "#8B8B85" if days <= 7 else "#f5c518" if days <= 14 else "#ff6b6b"
            st.markdown(
                f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:{color};'
                f'letter-spacing:0.1em">{days}d in queue</span>',
                unsafe_allow_html=True,
            )

        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"**Location:** {job.get('location', 'Unknown')}")
            st.markdown(f"**Score reason:** {job.get('score_reason', '')}")
            st.markdown(f"**Salary match:** {job.get('salary_match', 'Unknown')}")
            st.markdown(f"**Seniority:** {job.get('seniority', 'Unknown')}")
            st.markdown(f"**Source:** {job.get('source', '')}")
            if job.get("url"):
                st.markdown(f"[Open job posting ↗]({job['url']})")

        # Status → outcome mapping: moving to a status auto-logs the matching event
        STATUS_OUTCOME_MAP = {
            "applied":              "applied",
            "interview":            "interview_scheduled",
            "rejected":             "rejected",
            "skipped":              None,
            "application_closed":   None,
            "manual_review":        None,
        }

        with col2:
            new_status = st.selectbox(
                "Move to",
                ["— no change —"] + next_statuses,
                key=f"{key_prefix}_sel_{job['id']}",
            )
            if new_status != "— no change —":
                if st.button("Save", key=f"{key_prefix}_save_{job['id']}", type="secondary"):
                    update_status(job["id"], new_status, user_id=_USER_ID)
                    auto_event = STATUS_OUTCOME_MAP.get(new_status)
                    if auto_event:
                        log_event(job["id"], auto_event, f"status moved to {new_status}", user_id=_USER_ID)
                    else:
                        log_event(job["id"], "status_change", f"{job.get('status', 'unknown')} -> {new_status}", user_id=_USER_ID)
                    st.success(f"→ {new_status}")
                    st.rerun()

        # Only show manual signals that have no corresponding status
        st.markdown('<div class="section-label" style="margin-top:16px">Additional Signal</div>', unsafe_allow_html=True)
        signal = st.selectbox(
            "Log signal",
            ["— none —", "recruiter_response", "no_response_14d"],
            key=f"{key_prefix}_signal_{job['id']}",
            help="For events that don't change your status — recruiter reached out, or you've heard nothing after 2 weeks.",
        )
        if signal != "— none —":
            note = st.text_input(
                "Optional note",
                key=f"{key_prefix}_signal_note_{job['id']}",
                placeholder="e.g. recruiter replied in 2 days",
            )
            if st.button("Log Signal", key=f"{key_prefix}_signal_save_{job['id']}"):
                log_event(job["id"], signal, note.strip(), user_id=_USER_ID)
                st.success(f"Logged: {signal}")
                st.rerun()

        if job.get("cover_letter"):
            cl_col, dl_col = st.columns([5, 1])
            with cl_col:
                st.markdown("**Cover Letter**")
            with dl_col:
                import io
                from docx import Document
                from docx.shared import Pt
                doc = Document()
                doc.add_heading(f"{job.get('title', '')} — {job.get('company', '')}", level=1)
                for para in job["cover_letter"].split("\n"):
                    if para.strip():
                        doc.add_paragraph(para.strip())
                buf = io.BytesIO()
                doc.save(buf)
                buf.seek(0)
                safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", f"{job.get('company','')}_{job.get('title','')}").strip("_")
                st.download_button(
                    "⬇ .docx",
                    data=buf,
                    file_name=f"cover_letter_{safe_name}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"dl_{job['id']}",
                )
            st.markdown(
                f'<div class="cover-letter">{job["cover_letter"]}</div>',
                unsafe_allow_html=True,
            )

def _categorize(title: str) -> str:
    t = (title or "").lower()
    if any(k in t for k in ["genai", "gen ai", "generative", "llm", "ai engineer", "ml engineer", "machine learning"]):
        return "AI / ML"
    if any(k in t for k in ["data engineer", "etl", "pipeline", "databricks", "spark", "platform engineer"]):
        return "Data Engineering"
    if any(k in t for k in ["analytics engineer", "data analyst", "business intelligence", "bi engineer", "data scientist"]):
        return "Analytics"
    if any(k in t for k in ["program manager", "project manager", "tpm", "technical program", "scrum"]):
        return "Program Management"
    if any(k in t for k in ["software engineer", "backend", "frontend", "full stack", "fullstack", "swe"]):
        return "Software Engineering"
    if any(k in t for k in ["data architect", "cloud architect", "solutions architect"]):
        return "Architecture"
    return "Other"


def page_header(eyebrow, title_html):
    st.markdown(f"""
    <div class="page-header">
      <div>
        <div class="eyebrow">{eyebrow}</div>
        <h1>{title_html}</h1>
      </div>
    </div>
    """, unsafe_allow_html=True)

def metric(col, label, value, sub="", accent=False):
    col.markdown(f"""
    <div class="metric-card{"  accent" if accent else ""}">
      <div class="label">{label}</div>
      <div class="value">{value}</div>
      {"<div class='sub'>" + sub + "</div>" if sub else ""}
    </div>""", unsafe_allow_html=True)


def _boolish(v) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).lower() in ("true", "1", "t", "yes")


def enrich_experiment_runs_df(df: pd.DataFrame) -> pd.DataFrame:
    """Add qualified_pct and human-readable cost_mode for experiment comparison."""
    if df.empty:
        return df
    out = df.copy()

    def qualified_pct_row(row):
        new = int(row.get("jobs_new") or 0)
        q = int(row.get("jobs_qualified") or 0)
        return round(100.0 * q / new, 1) if new else None

    def cost_mode_row(row):
        mode = str(row.get("scoring_mode") or "").lower().strip()
        letters = _boolish(row.get("cover_letters_enabled"))
        if mode == "cheap":
            return "No LLM"
        if mode == "hybrid":
            return "Hybrid + letters" if letters else "Hybrid (score only)"
        return "Claude + letters" if letters else "Claude (score only)"

    out["qualified_pct"] = out.apply(qualified_pct_row, axis=1)
    out["cost_mode"] = out.apply(cost_mode_row, axis=1)
    return out


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════
BETA_JOB_LIMIT = 50  # max jobs scored per pipeline run for beta users

# ═══════════════════════════════════════════════════════════════════
# SETUP — resume onboarding (required before pipeline runs)
# ═══════════════════════════════════════════════════════════════════
if page == "Setup":
    page_header("Setup", "Start <em>here.</em>")

    # ── How it works ─────────────────────────────────────────────
    st.markdown("""
    <div class="pipeline-card" style="margin-bottom:24px">
      <h4>How Job Pal works</h4>
      <p>
        1. Paste your resume below — Job Pal uses it to score every job 1–10 for fit.<br><br>
        2. Go to <b>Run Pipeline</b> — it scrapes LinkedIn, Indeed, Remotive, and more, then our AI scores each job against your background and writes a custom cover letter for every match scoring 7+.<br><br>
        3. Review your matches in <b>Review Queue</b>, move jobs through <b>Applied → Interviews</b>, and track everything on the <b>Dashboard</b>.
      </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Resume status + start-fresh action ───────────────────────
    if st.session_state.get("resume_text"):
        status_col, clear_col = st.columns([3, 1])
        with status_col:
            st.success("✓ Resume loaded — update below and hit Save to switch resumes.")
        with clear_col:
            if st.button("Start Fresh", use_container_width=True, key="setup_start_fresh"):
                if st.session_state.get("_confirm_setup_clear"):
                    from tracker import clear_all_data
                    clear_all_data(user_id=_USER_ID)
                    if _USER_ID:
                        clear_session(_USER_ID)
                    for _k in ("resume_text", "target_roles", "min_salary", "session_uid",
                               "_suggested_roles", "_roles_text_area", "_confirm_setup_clear",
                               "_session_restored"):
                        st.session_state.pop(_k, None)
                    st.session_state["_user_session_restored_for"] = _USER_ID
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.session_state["_confirm_setup_clear"] = True
        if st.session_state.get("_confirm_setup_clear"):
            st.warning("This clears all jobs, pipeline runs, and your saved resume. Click **Start Fresh** again to confirm.")
    else:
        st.info("Upload or paste your resume below, then hit **Save**.")

    # ── Resume input: upload or paste ────────────────────────────
    st.markdown('<div class="section-label">Your Resume</div>', unsafe_allow_html=True)
    tab_upload, tab_paste = st.tabs(["Upload File", "Paste Text"])

    uploaded_text = None   # from file upload
    pasted_text   = None   # from paste tab

    with tab_upload:
        uploaded = st.file_uploader(
            "Upload your resume",
            type=["pdf", "docx", "txt"],
            label_visibility="collapsed",
            help="PDF, DOCX, or TXT — text is extracted automatically",
        )
        if uploaded:
            try:
                if uploaded.type == "application/pdf":
                    import fitz  # PyMuPDF
                    doc = fitz.open(stream=uploaded.read(), filetype="pdf")
                    uploaded_text = "\n".join(page.get_text() for page in doc)
                elif uploaded.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    from docx import Document
                    doc = Document(uploaded)
                    uploaded_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                else:
                    uploaded_text = uploaded.read().decode("utf-8", errors="ignore")

                st.success(f"✓ {uploaded.name} extracted — {len(uploaded_text)} characters")
                st.markdown(
                    f'<div class="cover-letter" style="max-height:200px;overflow-y:auto">{uploaded_text[:800]}{"..." if len(uploaded_text) > 800 else ""}</div>',
                    unsafe_allow_html=True,
                )
            except Exception as e:
                st.error(f"Could not read file: {e}")

    with tab_paste:
        pasted = st.text_area(
            "Paste resume text",
            value=st.session_state.get("resume_text") or "",
            height=280,
            placeholder="Paste your full resume as plain text — work history, skills, education, certifications...",
            label_visibility="collapsed",
        )
        if pasted.strip():
            pasted_text = pasted.strip()

    # Upload takes priority over paste; paste is fallback
    extracted_text = uploaded_text or pasted_text

    # ── Salary preference ────────────────────────────────────────
    st.markdown('<div class="section-label" style="margin-top:20px">Minimum Salary (optional)</div>', unsafe_allow_html=True)
    salary_options = [
        "No minimum",
        "$80,000+",
        "$100,000+",
        "$120,000+",
        "$140,000+",
        "$160,000+",
        "$180,000+",
        "$200,000+",
        "$220,000+",
    ]
    salary_map = {
        "No minimum": 0,
        "$80,000+": 80_000,
        "$100,000+": 100_000,
        "$120,000+": 120_000,
        "$140,000+": 140_000,
        "$160,000+": 160_000,
        "$180,000+": 180_000,
        "$200,000+": 200_000,
        "$220,000+": 220_000,
    }
    current_min = st.session_state.get("min_salary", 0)
    current_label = next((k for k, v in salary_map.items() if v == current_min), "No minimum")
    selected_salary = st.selectbox(
        "Minimum salary",
        salary_options,
        index=salary_options.index(current_label),
        label_visibility="collapsed",
    )

    # ── Target roles ─────────────────────────────────────────────
    st.markdown('<div class="section-label" style="margin-top:20px">Target Roles — one per line</div>', unsafe_allow_html=True)

    saved_roles = st.session_state.get("target_roles") or []
    default_roles = "\n".join(saved_roles)

    suggest_col, _ = st.columns([1, 3])
    with suggest_col:
        suggest_btn = st.button(
            "Suggest from resume",
            disabled=not bool(extracted_text),
            help="Uses AI to infer target job titles from your resume. Paste or upload your resume first.",
        )

    if suggest_btn and extracted_text:
        with st.spinner("Reading your resume..."):
            try:
                import anthropic as _ant
                from config import ANTHROPIC_API_KEY
                _ac = _ant.Anthropic(api_key=ANTHROPIC_API_KEY)
                _msg = _ac.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=300,
                    messages=[{
                        "role": "user",
                        "content": (
                            "Based on this resume, list 8–12 specific job titles this person should target "
                            "in their job search. Output ONLY the job titles, one per line, no bullets, "
                            "no explanations, no numbering. Include seniority level where appropriate.\n\n"
                            f"RESUME:\n{extracted_text[:3000]}"
                        ),
                    }],
                )
                # Store in session state and also directly set the text area value
                st.session_state["_suggested_roles"] = _msg.content[0].text.strip()
                st.session_state["_roles_text_area"] = st.session_state["_suggested_roles"]
            except Exception as e:
                st.warning(f"Could not suggest roles: {e}")

    # Use a stable session key for the text area value — avoids pop() destroying it on rerun
    if "_suggested_roles" in st.session_state:
        role_value = st.session_state.pop("_suggested_roles")
        st.session_state["_roles_text_area"] = role_value
    else:
        # Fall back to saved roles; empty string when session was cleared
        role_value = st.session_state.get("_roles_text_area") or default_roles

    roles_input = st.text_area(
        "Target roles",
        value=role_value,
        height=180,
        placeholder="Paste your resume above first, then click Suggest — or type roles manually.\nOne role per line.",
        label_visibility="collapsed",
    )

    if st.button("Save & Go to Pipeline →", type="primary", use_container_width=True):
        if not extracted_text or len(extracted_text.strip()) < 100:
            st.error("Resume looks too short or empty — upload a file or paste your resume text.")
        else:
            clean_text = extracted_text.strip()
            roles = [r.strip() for r in roles_input.splitlines() if r.strip()]
            st.session_state["resume_text"] = clean_text
            st.session_state["target_roles"] = roles
            st.session_state["min_salary"] = salary_map[selected_salary]

            # Persist to Supabase — use auth user_id as key so resume is tied to account
            uid = _USER_ID or st.session_state.get("session_uid") or new_uid()
            try:
                save_session(uid, clean_text, roles)
                st.session_state["session_uid"] = uid
                if not _USER_ID:
                    st.query_params["uid"] = uid
                st.success(
                    f"✓ Resume saved. Bookmark this page — your resume will reload automatically. "
                    f"Click **Run Pipeline** to start."
                )
            except Exception as e:
                # DB write failed — session still works in memory this tab
                st.success("✓ Resume saved for this session. Click **Run Pipeline** to start.")
                st.caption(f"(Persistence unavailable: {e})")

    if st.session_state.get("resume_text"):
        st.markdown('<div class="section-label" style="margin-top:28px">Currently Loaded Resume</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="cover-letter" style="max-height:200px;overflow-y:auto">{st.session_state["resume_text"][:800]}{"..." if len(st.session_state["resume_text"]) > 800 else ""}</div>',
            unsafe_allow_html=True,
        )
        st.caption("To update, upload a new file or paste new text and hit Save again.")


elif page == "Dashboard":
    page_header("Job Pal · Techturi", "Your <em>pipeline.</em>")

    apps = safe_get_apps()
    if not apps:
        st.info("No applications tracked yet. Run the pipeline to get started.")
        st.stop()

    df = pd.DataFrame(apps)
    status_counts = df["status"].value_counts().to_dict()

    col1, col2, col3, col4, col5 = st.columns(5)
    metric(col1, "Total Tracked",  len(df))
    metric(col2, "Applied",        status_counts.get("applied", 0))
    metric(col3, "Interviews",     status_counts.get("interview", 0), accent=True)
    metric(col4, "In Queue",       status_counts.get("new", 0), "awaiting review")
    avg = df['score'].dropna().mean()
    metric(col5, "Avg AI Score",   f"{avg:.1f}" if not df['score'].dropna().empty else "—", "out of 10")

    st.markdown('<div class="section-label" style="margin-top:28px">Analytics</div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Score Distribution**")
        score_df = df["score"].dropna().value_counts().sort_index()
        if not score_df.empty:
            st.bar_chart(score_df, color="#D4FF3A")

    with col_b:
        st.markdown("**Status Breakdown**")
        if status_counts:
            st.bar_chart(pd.Series(status_counts), color="#D4FF3A")

    event_counts = get_event_counts(user_id=_USER_ID)
    if event_counts:
        st.markdown('<div class="section-label" style="margin-top:28px">Outcome Signals</div>', unsafe_allow_html=True)
        st.bar_chart(pd.Series(event_counts), color="#D4FF3A")

    st.markdown('<div class="section-label" style="margin-top:28px">Source health</div>', unsafe_allow_html=True)
    st.caption("Per job board: volume, average score, share scoring 7+, and how many are waiting in Review Queue.")
    health_df = pd.DataFrame(get_source_health(apps=apps, review_min_score=8, user_id=_USER_ID))
    if not health_df.empty:
        st.dataframe(health_df, use_container_width=True, hide_index=True)
    else:
        st.info("No source breakdown yet.")

    st.markdown('<div class="section-label" style="margin-top:28px">Top 10 by Score</div>', unsafe_allow_html=True)
    top = df.nlargest(10, "score")[["title", "company", "location", "score", "score_reason", "status"]]
    st.dataframe(top, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# REVIEW QUEUE
# ═══════════════════════════════════════════════════════════════════
elif page == "Review Queue":
    page_header("Review Queue", "Jobs worth <em>applying to.</em>")
    rq_col_info, rq_col_thresh = st.columns([3, 1])
    with rq_col_info:
        st.markdown('<div style="font-family:\'JetBrains Mono\',monospace;font-size:12px;color:#8B8B85;margin-bottom:24px">Status updates save instantly</div>', unsafe_allow_html=True)
    with rq_col_thresh:
        queue_min_score = st.selectbox(
            "Min score",
            [5, 6, 7, 8, 9],
            index=1,  # default 6
            key="rq_min_score",
            help="Lower to see borderline matches. Raise to see only strong fits.",
            label_visibility="collapsed",
        )

    queue = safe_get_queue(min_score=queue_min_score)
    if not queue:
        st.success("Queue is empty — nothing to review.")
        st.stop()

    # ── Queue filters ─────────────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        hide_old = st.toggle(
            "Hide stale listings (>14 days)",
            value=True,
            help="Postings older than 2 weeks are often filled. Toggle off to see all.",
        )
    with col_f2:
        display_limit = st.selectbox(
            "Show top",
            [25, 50, 100, "All"],
            index=0,
            help="Limit visible jobs — sorted by score before the cutoff.",
        )
    with col_f3:
        all_cats = sorted(set(_categorize(j.get("title","")) for j in queue))
        cat_filter = st.multiselect("Category", all_cats, default=all_cats)

    total_in_db = len(queue)
    if hide_old:
        queue = [j for j in queue if (_days_in_queue(j) or 0) <= 14]
    queue = [j for j in queue if _categorize(j.get("title","")) in cat_filter]
    stale_hidden = total_in_db - len(queue)

    personalize = st.toggle(
        "Personalize order from my outcomes",
        value=True,
        help="Re-ranks using companies, sources, and title words from jobs where you logged positive or negative signals.",
    )
    weights = {
        "pos_company": 1.2,
        "neg_company": -0.9,
        "good_source": 0.35,
        "title_token_per_hit": 0.2,
        "title_token_cap": 1.0,
        "title_min_hits": 2,
    }

    if personalize:
        with st.expander("Personalization controls", expanded=False):
            st.caption("Tune how strongly your past outcomes influence queue ordering.")
            c1, c2, c3 = st.columns(3)
            with c1:
                weights["pos_company"] = st.slider("Positive company boost", 0.0, 3.0, float(weights["pos_company"]), 0.05,
                    help="How much to boost jobs from companies where you've had interviews or positive signals. Higher = those companies rank first.")
                weights["neg_company"] = st.slider("Negative company penalty", -3.0, 0.0, float(weights["neg_company"]), 0.05,
                    help="How much to push down jobs from companies where you've been rejected or marked skipped. More negative = stronger suppression.")
            with c2:
                weights["good_source"] = st.slider("Good source boost", 0.0, 2.0, float(weights["good_source"]), 0.05,
                    help="Boost jobs from sources (LinkedIn, Indeed, etc.) that have historically sent you to interviews or strong leads.")
                weights["title_min_hits"] = st.slider("Title overlap min hits", 1, 5, int(weights["title_min_hits"]), 1,
                    help="Minimum number of title keywords that must match your past successful jobs before a title-overlap bonus is applied.")
            with c3:
                weights["title_token_per_hit"] = st.slider("Title overlap per hit", 0.0, 0.6, float(weights["title_token_per_hit"]), 0.01,
                    help="Score bonus added per matching title keyword (e.g. 'senior', 'engineer', 'data'). Stacks up to the cap.")
                weights["title_token_cap"] = st.slider("Title overlap cap", 0.0, 2.0, float(weights["title_token_cap"]), 0.05,
                    help="Maximum total bonus from title keyword matches, no matter how many words align. Prevents title-heavy jobs from dominating.")

            preview_n = st.slider("Preview rows", 5, 25, 10, 1)
            base = sorted(queue, key=lambda j: j.get("score") or 0, reverse=True)
            reranked = [dict(j) for j in queue]
            rank_queue_with_personalization(reranked, weights=weights, user_id=_USER_ID)

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Before (AI score only)**")
                if base:
                    base_top = pd.DataFrame(base[:preview_n])[["title", "company", "score", "source"]]
                    st.dataframe(base_top, use_container_width=True, hide_index=True)
                else:
                    st.info("No jobs in queue.")
            with col_b:
                st.markdown("**After (personalized)**")
                if reranked:
                    new_top = pd.DataFrame(reranked[:preview_n])[["title", "company", "score", "_effective_score", "_personal_bonus", "source"]]
                    st.dataframe(new_top, use_container_width=True, hide_index=True)
                else:
                    st.info("No jobs in queue.")

            if st.button("Reset personalization defaults"):
                st.rerun()

        rank_queue_with_personalization(queue, weights=weights, user_id=_USER_ID)
    else:
        queue.sort(key=lambda j: j.get("score") or 0, reverse=True)

    display_queue = queue if display_limit == "All" else queue[:int(display_limit)]
    cap_hidden = len(queue) - len(display_queue)

    parts = [f"{len(display_queue)} shown"]
    if stale_hidden:
        parts.append(f"{stale_hidden} stale hidden")
    if cap_hidden:
        parts.append(f"{cap_hidden} more below limit")

    summary_col, purge_col = st.columns([4, 1])
    with summary_col:
        st.markdown(f'<div class="section-label">{" · ".join(parts)}</div>', unsafe_allow_html=True)
    with purge_col:
        stale_jobs = [j for j in safe_get_queue(min_score=queue_min_score) if (_days_in_queue(j) or 0) > 14]
        if stale_jobs:
            if st.button(f"Dismiss {len(stale_jobs)} stale", type="secondary", help="Mark all jobs older than 14 days as Skipped"):
                for j in stale_jobs:
                    update_status(j["id"], "skipped", user_id=_USER_ID)
                st.success(f"Dismissed {len(stale_jobs)} stale jobs.")
                st.rerun()

    for job in display_queue:
        job_card(job, "rq", ["applied", "skipped", "rejected"])


# ═══════════════════════════════════════════════════════════════════
# APPLIED
# ═══════════════════════════════════════════════════════════════════
elif page == "Applied":
    page_header("Applied", "In their <em>inbox.</em>")
    st.markdown('<div style="font-family:\'JetBrains Mono\',monospace;font-size:12px;color:#8B8B85;margin-bottom:24px">Jobs you\'ve submitted — cover letters, details, and next-step controls</div>', unsafe_allow_html=True)

    apps = safe_get_apps()
    applied = [a for a in apps if a.get("status") == "applied"]

    if not applied:
        st.info("No applications marked 'applied' yet. Move jobs here from the Review Queue.")
        st.stop()

    st.markdown(f'<div class="section-label">{len(applied)} applications sent</div>', unsafe_allow_html=True)

    f1, f2 = st.columns([3, 1])
    with f1:
        search = st.text_input("Search", placeholder="Company or title...")
    with f2:
        cover_letter_only = st.toggle("Cover letter only", value=False)

    if search:
        applied = [a for a in applied if
                   search.lower() in (a.get("title") or "").lower() or
                   search.lower() in (a.get("company") or "").lower()]
    if cover_letter_only:
        applied = [a for a in applied if a.get("cover_letter")]

    for job in sorted(applied, key=lambda x: x.get("score") or 0, reverse=True):
        job_card(job, "ap", ["interview", "rejected", "skipped", "application_closed"])


# ═══════════════════════════════════════════════════════════════════
# INTERVIEWS
# ═══════════════════════════════════════════════════════════════════
elif page == "Interviews":
    page_header("Interviews", "You're in the <em>room.</em>")
    st.markdown('<div style="font-family:\'JetBrains Mono\',monospace;font-size:12px;color:#8B8B85;margin-bottom:24px">Active interview pipeline — review your cover letter, prep, and track outcomes</div>', unsafe_allow_html=True)

    apps = safe_get_apps()
    interviews = [a for a in apps if a.get("status") == "interview"]

    if not interviews:
        st.info("No active interviews. Move jobs here from Applied when you land a screen or interview.")
        st.stop()

    st.markdown(f'<div class="section-label">{len(interviews)} active interview{"s" if len(interviews) != 1 else ""}</div>', unsafe_allow_html=True)

    for job in sorted(interviews, key=lambda x: x.get("score") or 0, reverse=True):
        job_card(job, "iv", ["rejected", "skipped", "application_closed"], expanded=True)


# ═══════════════════════════════════════════════════════════════════
# ALL APPLICATIONS
# ═══════════════════════════════════════════════════════════════════
elif page == "All Applications":
    page_header("All Applications", "Full <em>history.</em>")

    apps = safe_get_apps()
    if not apps:
        st.info("No applications tracked yet.")
        st.stop()

    df = pd.DataFrame(apps)

    df["category"] = df["title"].apply(_categorize)
    categories = sorted(df["category"].unique().tolist())

    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.multiselect(
            "Status", df["status"].unique().tolist(),
            default=df["status"].unique().tolist(),
        )
    with col2:
        category_filter = st.multiselect(
            "Category", categories, default=categories,
        )

    col3, col4 = st.columns(2)
    with col3:
        min_score = st.slider("Min score", 0, 10, 0)
    with col4:
        search = st.text_input("Search title / company")

    filtered = df[
        df["status"].isin(status_filter) &
        df["category"].isin(category_filter) &
        (df["score"].fillna(0) >= min_score)
    ]
    if search:
        mask = (
            filtered["title"].str.contains(search, case=False, na=False) |
            filtered["company"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    st.markdown(f'<div class="section-label">{len(filtered)} results</div>', unsafe_allow_html=True)

    display_cols = ["category", "title", "company", "location", "score", "status", "seniority", "salary_match", "source"]
    available = [c for c in display_cols if c in filtered.columns]
    st.dataframe(filtered[available], use_container_width=True, hide_index=True)

    st.markdown('<div class="section-label" style="margin-top:28px">Quick Status Update</div>', unsafe_allow_html=True)
    job_options = {
        f"{r['title']} @ {r.get('company','?')} (score: {r.get('score','?')})": r["id"]
        for _, r in filtered.iterrows()
    }
    if job_options:
        selected_label = st.selectbox("Select job", list(job_options.keys()))
        selected_id = job_options[selected_label]
        new_status = st.selectbox("New status", ["new", "applied", "interview", "rejected", "skipped", "application_closed"])
        if st.button("Update Status", type="primary"):
            update_status(selected_id, new_status, user_id=_USER_ID)
            st.success(f"Updated → {new_status}")
            st.rerun()


# ═══════════════════════════════════════════════════════════════════
# RUN PIPELINE
# ═══════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════
# EVENTS
# ═══════════════════════════════════════════════════════════════════
elif page == "Events":
    page_header("Networking", "Events near <em>you.</em>")

    from agent import score_events

    # ── Controls ──────────────────────────────────────────────────
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 1, 1])
    with ctrl_col1:
        city_input = st.text_input(
            "City",
            value="Houston",
            placeholder="Houston, Austin, New York…",
            label_visibility="collapsed",
            help="City to search for events in",
        )
    with ctrl_col2:
        ev_min_score = st.selectbox(
            "Min relevance",
            [1, 3, 5, 7],
            index=1,
            label_visibility="collapsed",
            help="Minimum relevance score to show",
        )
    with ctrl_col3:
        refresh_btn = st.button("Refresh Events", type="primary", use_container_width=True)

    if refresh_btn:
        resume_text = st.session_state.get("resume_text")
        with st.spinner(f"Scraping events in {city_input}..."):
            from scrapers.events import scrape_events
            raw = scrape_events(city=city_input.strip())

        st.info(f"Found {len(raw)} events — scoring against your resume...")
        scored = score_events(raw, resume_text=resume_text)

        with st.spinner("Saving to your account..."):
            try:
                upsert_events(scored, user_id=_USER_ID)
            except Exception as e:
                st.error(
                    "Could not save events — run the CREATE TABLE SQL in the ShutterMuse "
                    "Supabase SQL Editor first (supabase.com/dashboard/project/"
                    "muuykfzvrvfktysqlqbc/sql), then try again."
                )
                st.stop()

        st.success(f"✓ {len(scored)} events loaded. Showing {ev_min_score}+ relevance below.")
        st.rerun()

    # ── Load saved events ─────────────────────────────────────────
    try:
        events = get_events(user_id=_USER_ID, min_score=ev_min_score,
                            status_filter=["new", "interested", "attending"])
    except RuntimeError:
        st.warning(
            "Events database not configured yet. "
            "Add `EVENTS_SUPABASE_URL` and `EVENTS_SUPABASE_KEY` to your "
            "Streamlit Cloud secrets (Settings → Secrets), then reboot the app."
        )
        st.stop()

    if not events:
        st.markdown("""
        <div class="pipeline-card" style="text-align:center;padding:40px">
          <h4>No events loaded yet</h4>
          <p>Enter your city above and click <b>Refresh Events</b> to scrape local networking events
          scored against your resume.</p>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    # ── Filters ───────────────────────────────────────────────────
    all_sources = sorted(set(e.get("source","") for e in events))
    f1, f2 = st.columns([2, 2])
    with f1:
        src_filter = st.multiselect("Source", all_sources, default=all_sources, key="ev_src")
    with f2:
        ev_search = st.text_input("Search", placeholder="AI, data, Python…", key="ev_search",
                                  label_visibility="collapsed")

    if src_filter:
        events = [e for e in events if e.get("source") in src_filter]
    if ev_search:
        q = ev_search.lower()
        events = [e for e in events if q in (e.get("title","") + e.get("description","") +
                                              e.get("organizer","")).lower()]

    st.markdown(f'<div class="section-label">{len(events)} events · sorted by relevance</div>',
                unsafe_allow_html=True)

    # ── Event cards ───────────────────────────────────────────────
    STATUS_COLORS = {"new": "#4A4A45", "interested": "#f5c518", "attending": "#D4FF3A"}

    for ev in events:
        score = ev.get("relevance_score") or 0
        icon = "🟢" if score >= 7 else "🟡" if score >= 4 else "🔴"
        status = ev.get("status", "new")
        status_dot = f'<span style="color:{STATUS_COLORS.get(status,"#4A4A45")};font-size:10px">● {status.upper()}</span>'

        # Parse date for display
        raw_date = ev.get("start_date", "")
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            date_str = dt.strftime("%a %b %-d · %-I:%M %p")
        except Exception:
            date_str = raw_date[:16] if raw_date else "Date TBD"

        with st.expander(
            f"{icon}  {score}/10  —  {ev.get('title','')[:60]}",
            expanded=False,
        ):
            top_col, btn_col = st.columns([3, 1])

            with top_col:
                st.markdown(
                    f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:11px;'
                    f'color:#8B8B85;margin-bottom:8px">'
                    f'📅 {date_str} &nbsp;·&nbsp; '
                    f'📍 {ev.get("location","")[:40]} &nbsp;·&nbsp; '
                    f'👥 {ev.get("organizer","")[:35]}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if ev.get("relevance_reason"):
                    st.caption(f"Relevance: {ev['relevance_reason']}")
                if ev.get("description"):
                    st.markdown(
                        f'<div class="cover-letter" style="max-height:140px;overflow-y:auto;'
                        f'font-size:11px">{ev["description"][:600]}</div>',
                        unsafe_allow_html=True,
                    )
                if ev.get("url"):
                    st.markdown(f"[View event ↗]({ev['url']})")

            with btn_col:
                eid = ev["id"]
                st.markdown(
                    f'<div style="margin-bottom:8px">{status_dot}</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Interested", key=f"ev_int_{eid}", use_container_width=True):
                    update_event_status(eid, "interested", user_id=_USER_ID)
                    st.rerun()
                if st.button("Attending", key=f"ev_att_{eid}", use_container_width=True,
                             type="primary"):
                    update_event_status(eid, "attending", user_id=_USER_ID)
                    st.rerun()
                if st.button("Skip", key=f"ev_skip_{eid}", use_container_width=True):
                    update_event_status(eid, "skipped", user_id=_USER_ID)
                    st.rerun()


elif page == "Run Pipeline":
    page_header("Pipeline", "Scrape. Score. <em>Apply.</em>")

    # ── Resume gate ──────────────────────────────────────────────
    resume_text = st.session_state.get("resume_text")
    if not resume_text:
        st.warning("No resume loaded. Go to **Setup** and paste your resume first — the pipeline uses it to score job fit.")
        st.stop()

    min_salary = st.session_state.get("min_salary", 0)
    salary_label = f"${min_salary:,}+" if min_salary else "no minimum"
    st.markdown(f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:11px;color:#4A4A45;margin-bottom:20px">Beta limit: {BETA_JOB_LIMIT} jobs per run · Resume loaded ✓ · Salary filter: {salary_label}</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="pipeline-card"><h4>Full Pipeline</h4><p>Scrape all sources → AI scores every job for fit → generates a custom cover letter for every match scoring 7+</p></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        run_label = st.text_input(
            "Run label",
            value="",
            placeholder="e.g. cheap-baseline-may06",
            help="Optional name to compare this run with others.",
        )
        run_note = st.text_area(
            "Run note",
            value="",
            height=80,
            placeholder="Optional notes (query changes, expectations, observations).",
        )
        scoring_mode = st.selectbox(
            "Scoring mode",
            ["cheap", "hybrid", "claude"],
            index=0,
            help="cheap = no LLM cost, hybrid = cheap pre-filter + Claude, claude = best quality/highest cost",
        )
        hybrid_min = st.slider(
            "Hybrid Claude threshold",
            min_value=1,
            max_value=10,
            value=6,
            disabled=(scoring_mode != "hybrid"),
            help="In hybrid mode, jobs at or above this cheap-score are escalated to Claude.",
        )
        enable_letters = st.checkbox(
            "Generate cover letters",
            value=(scoring_mode != "cheap"),
            help="Turn off to avoid extra model calls during testing.",
        )
        if st.button("▶ Run Full Pipeline", type="primary", use_container_width=True):
            with st.spinner("Scraping jobs..."):
                from scrapers import scrape_all
                jobs = scrape_all(
                    target_roles=st.session_state.get("target_roles") or None,
                    min_salary=st.session_state.get("min_salary", 0),
                )

            st.info(f"Scraped {len(jobs)} jobs total")

            from tracker import get_seen_ids
            seen = get_seen_ids(user_id=_USER_ID)
            new_jobs = [j for j in jobs if _scope_id(j["id"], _USER_ID) not in seen]

            # Beta cap: sort by cheap score first so the best 50 are selected
            if len(new_jobs) > BETA_JOB_LIMIT:
                st.info(f"Beta limit: pre-ranking {len(new_jobs)} new jobs, keeping top {BETA_JOB_LIMIT}...")
                from agent import score_job_cheap
                _resume = st.session_state.get("resume_text")
                _roles  = st.session_state.get("target_roles")
                _sal    = st.session_state.get("min_salary", 0)
                for j in new_jobs:
                    score_job_cheap(j, resume_text=_resume, target_roles=_roles, min_salary=_sal)
                new_jobs = sorted(new_jobs, key=lambda j: j.get("score") or 0, reverse=True)[:BETA_JOB_LIMIT]
                # Reset scores so Pass 2 re-scores cleanly
                for j in new_jobs:
                    j["score"] = None
            else:
                st.info(f"{len(new_jobs)} new (unseen) jobs to score")

            if not new_jobs:
                st.success("Nothing new to score. Queue is up to date.")
            else:
                st.info(f"Scoring {len(new_jobs)} jobs — this takes 1–3 minutes. Don't close the tab.")
                progress = st.progress(0, text="Starting AI scoring...")

                progress.progress(10, text=f"Analyzing {len(new_jobs)} jobs against your resume...")
                from agent import process_jobs
                all_scored, qualified = process_jobs(
                    new_jobs,
                    verbose=False,
                    resume_text=resume_text,
                    scoring_backend=scoring_mode,
                    enable_cover_letters=enable_letters,
                    hybrid_claude_min_score=hybrid_min,
                    min_salary=st.session_state.get("min_salary", 0),
                    target_roles=st.session_state.get("target_roles") or [],
                )

                progress.progress(80, text=f"Writing cover letters for {len(qualified)} qualified jobs...")
                from tracker import upsert_jobs
                upsert_jobs(all_scored, user_id=_USER_ID)

                log_experiment_run(
                    run_label=run_label.strip(),
                    scoring_mode=scoring_mode,
                    hybrid_threshold=hybrid_min,
                    cover_letters_enabled=enable_letters,
                    jobs_scraped=len(jobs),
                    jobs_new=len(new_jobs),
                    jobs_qualified=len(qualified),
                    note=run_note.strip(),
                    user_id=_USER_ID,
                )

                progress.progress(100, text="Done.")
                st.success(f"✓ Pipeline complete — {len(qualified)} jobs scored {REVIEW_MIN_SCORE}+ added to Review Queue.")

                if qualified:
                    st.markdown('<div class="section-label" style="margin-top:20px">Qualified Jobs</div>', unsafe_allow_html=True)
                    q_df = pd.DataFrame(qualified)[["title", "company", "score", "score_reason", "seniority"]]
                    st.dataframe(q_df, use_container_width=True, hide_index=True)

    with col2:
        st.markdown('<div class="pipeline-card"><h4>Scrape Only</h4><p>Fetch raw job listings from all sources without scoring — no API calls, no cost</p></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("▶ Scrape Only", use_container_width=True):
            with st.spinner("Scraping..."):
                from scrapers import scrape_all
                jobs = scrape_all(
                    target_roles=st.session_state.get("target_roles") or None,
                    min_salary=st.session_state.get("min_salary", 0),
                )
            st.success(f"Scraped {len(jobs)} jobs")
            preview = pd.DataFrame(jobs[:20])[["title", "company", "location", "source"]]
            st.dataframe(preview, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-label" style="margin-top:36px">Current Stats</div>', unsafe_allow_html=True)
    try:
        apps = safe_get_apps()
        if apps:
            df = pd.DataFrame(apps)
            c1, c2, c3 = st.columns(3)
            metric(c1, "Total Tracked", len(df))
            metric(c2, "In Queue",      len(df[df["status"] == "new"]), "awaiting review")
            metric(c3, "Applied",       len(df[df["status"] == "applied"]), accent=True)
        else:
            st.info("No data yet — run the pipeline to get started.")
    except Exception as e:
        st.warning(f"Could not load stats — check Supabase connection. ({e})")

    recent_runs = get_recent_runs(limit=8, user_id=_USER_ID)
    if recent_runs:
        st.markdown('<div class="section-label" style="margin-top:24px">Recent Experiment Runs</div>', unsafe_allow_html=True)
        run_df = enrich_experiment_runs_df(pd.DataFrame(recent_runs))
        keep_cols = [
            "created_at", "run_label", "cost_mode", "scoring_mode", "hybrid_threshold",
            "cover_letters_enabled", "jobs_scraped", "jobs_new", "jobs_qualified",
            "qualified_pct", "note",
        ]
        cols = [c for c in keep_cols if c in run_df.columns]
        display_df = run_df[cols].copy()
        if "qualified_pct" in display_df.columns:
            display_df["qualified_pct"] = display_df["qualified_pct"].apply(
                lambda x: f"{x}%" if x is not None and pd.notna(x) else "—"
            )
        with_sub = run_df[run_df["jobs_new"].fillna(0) > 0]
        if not with_sub.empty and with_sub["qualified_pct"].notna().any():
            best = with_sub.loc[with_sub["qualified_pct"].idxmax()]
            lbl = best.get("run_label") or "(no label)"
            st.caption(
                f"Best qualified rate in this list: **{lbl}** — "
                f"{best['qualified_pct']}% qualified "
                f"({int(best.get('jobs_qualified') or 0)}/{int(best.get('jobs_new') or 0)} new jobs)"
            )
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        csv_buf = io.StringIO()
        run_df.to_csv(csv_buf, index=False)
        st.download_button(
            "Download recent runs (CSV)",
            csv_buf.getvalue(),
            file_name="pipeline_runs_recent.csv",
            mime="text/csv",
            key="download_pipeline_runs_csv",
        )

    # ── Clear queue (pipeline-only reset, keeps resume) ───────────
    st.markdown('<div class="section-label" style="margin-top:36px"></div>', unsafe_allow_html=True)
    cq_col, _ = st.columns([1, 3])
    with cq_col:
        if st.button("Clear Review Queue", key="btn_clear_queue", use_container_width=True,
                     help="Deletes all unreviewed jobs so you can run a fresh pipeline. Keeps applied/interview history."):
            if st.session_state.get("_confirm_clear_queue"):
                clear_queue(user_id=_USER_ID)
                st.session_state.pop("_confirm_clear_queue", None)
                st.success("✓ Review queue cleared. Run Pipeline to refill it.")
                st.rerun()
            else:
                st.session_state["_confirm_clear_queue"] = True
                st.warning("Clears all unreviewed jobs. Click again to confirm.")
