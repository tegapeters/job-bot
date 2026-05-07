"""
Job Pal — Streamlit UI v2 (Techturi branded)
Run: streamlit run ui_v2.py
"""
import io
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
)
from sessions import save_session, load_session, new_uid

# ── Page config ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Pal · techturi",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
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

  /* ── Primary buttons ── */
  [data-testid="baseButton-primary"] {
    background: #8faa28 !important;
    color: #0e0e0e !important;
    border: 1px solid #8faa28 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    letter-spacing: 0.1em !important;
  }
  [data-testid="baseButton-primary"]:hover {
    background: #a0c030 !important;
    border-color: #a0c030 !important;
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
</style>
""", unsafe_allow_html=True)


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

    # Show resume status in sidebar
    if st.session_state.get("resume_text"):
        st.markdown('<div style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#D4FF3A;letter-spacing:0.15em;padding:0 20px 12px">✓ RESUME LOADED</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-family:\'JetBrains Mono\',monospace;font-size:10px;color:#ff6b6b;letter-spacing:0.15em;padding:0 20px 12px">⚠ NO RESUME — START HERE</div>', unsafe_allow_html=True)

    page = st.radio(
        "Navigate",
        ["Setup", "Run Pipeline", "Review Queue", "Applied", "Interviews", "Dashboard", "All Applications"],
        label_visibility="collapsed",
    )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="tt-footer">techturi.org · Tega Eshareturi</div>', unsafe_allow_html=True)


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
    """Fetch all applications, showing a clean error if Supabase is unreachable."""
    try:
        return get_all_applications()
    except Exception as e:
        st.error(f"Cannot connect to database. Check Supabase secrets in Streamlit Cloud settings. Error: `{e}`")
        st.stop()

def safe_get_queue(min_score=8):
    try:
        return get_review_queue(min_score=min_score)
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
                    update_status(job["id"], new_status)
                    auto_event = STATUS_OUTCOME_MAP.get(new_status)
                    if auto_event:
                        log_event(job["id"], auto_event, f"status moved to {new_status}")
                    else:
                        log_event(job["id"], "status_change", f"{job.get('status', 'unknown')} -> {new_status}")
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
                log_event(job["id"], signal, note.strip())
                st.success(f"Logged: {signal}")
                st.rerun()

        if job.get("cover_letter"):
            st.markdown("**Cover Letter**")
            st.markdown(
                f'<div class="cover-letter">{job["cover_letter"]}</div>',
                unsafe_allow_html=True,
            )

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

    # ── Refresh warning ──────────────────────────────────────────
    if st.session_state.get("session_uid"):
        st.success("✓ Your resume is saved. Bookmark this URL — it will reload your resume automatically on return.")
    else:
        st.info("Upload or paste your resume below, then hit **Save**. Job Pal will generate a personal link that reloads your resume on future visits.")

    # ── Resume input: upload or paste ────────────────────────────
    st.markdown('<div class="section-label">Your Resume</div>', unsafe_allow_html=True)
    tab_upload, tab_paste = st.tabs(["Upload File", "Paste Text"])

    extracted_text = None

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
                    extracted_text = "\n".join(page.get_text() for page in doc)
                elif uploaded.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                    from docx import Document
                    doc = Document(uploaded)
                    extracted_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
                else:
                    extracted_text = uploaded.read().decode("utf-8", errors="ignore")

                st.success(f"✓ {uploaded.name} extracted — {len(extracted_text)} characters")
                st.markdown(
                    f'<div class="cover-letter" style="max-height:200px;overflow-y:auto">{extracted_text[:800]}{"..." if len(extracted_text) > 800 else ""}</div>',
                    unsafe_allow_html=True,
                )
            except Exception as e:
                st.error(f"Could not read file: {e}")

    with tab_paste:
        pasted = st.text_area(
            "Paste resume text",
            value=st.session_state.get("resume_text", ""),
            height=280,
            placeholder="Paste your full resume as plain text — work history, skills, education, certifications...",
            label_visibility="collapsed",
        )
        if pasted.strip():
            extracted_text = pasted.strip()

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
    current_min = st.session_state.get("min_salary", 140_000)
    current_label = next((k for k, v in salary_map.items() if v == current_min), "$140,000+")
    selected_salary = st.selectbox(
        "Minimum salary",
        salary_options,
        index=salary_options.index(current_label),
        label_visibility="collapsed",
    )

    # ── Target roles ─────────────────────────────────────────────
    st.markdown('<div class="section-label" style="margin-top:20px">Target Roles — one per line</div>', unsafe_allow_html=True)
    default_roles = "\n".join(st.session_state.get("target_roles", [
        "Senior Data Engineer",
        "Data Engineer",
        "AI Engineer",
        "Senior AI Engineer",
        "GenAI Engineer",
        "Machine Learning Engineer",
        "Senior ML Engineer",
        "Senior Technical Program Manager",
        "Technical Project Manager",
        "Business Systems Analyst",
    ]))
    roles_input = st.text_area(
        "Target roles",
        value=default_roles,
        height=140,
        placeholder="Senior Business Analyst\nData Engineer\nAI Engineer",
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

            # Persist to Supabase so the resume survives page refresh
            uid = st.session_state.get("session_uid") or new_uid()
            try:
                save_session(uid, clean_text, roles)
                st.session_state["session_uid"] = uid
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

    event_counts = get_event_counts()
    if event_counts:
        st.markdown('<div class="section-label" style="margin-top:28px">Outcome Signals</div>', unsafe_allow_html=True)
        st.bar_chart(pd.Series(event_counts), color="#D4FF3A")

    st.markdown('<div class="section-label" style="margin-top:28px">Source health</div>', unsafe_allow_html=True)
    st.caption("Per job board: volume, average score, share scoring 7+, and how many are waiting in Review Queue.")
    health_df = pd.DataFrame(get_source_health(apps=apps, review_min_score=8))
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
    st.markdown('<div style="font-family:\'JetBrains Mono\',monospace;font-size:12px;color:#8B8B85;margin-bottom:24px">AI fit score 8+ · Status updates save instantly</div>', unsafe_allow_html=True)

    queue = safe_get_queue(min_score=8)
    if not queue:
        st.success("Queue is empty — nothing to review.")
        st.stop()

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
            rank_queue_with_personalization(reranked, weights=weights)

            base_top = pd.DataFrame(base[:preview_n])[["title", "company", "score", "source"]]
            new_top = pd.DataFrame(reranked[:preview_n])[["title", "company", "score", "_effective_score", "_personal_bonus", "source"]]

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Before (AI score only)**")
                st.dataframe(base_top, use_container_width=True, hide_index=True)
            with col_b:
                st.markdown("**After (personalized)**")
                st.dataframe(new_top, use_container_width=True, hide_index=True)

            if st.button("Reset personalization defaults"):
                st.rerun()

        rank_queue_with_personalization(queue, weights=weights)
    else:
        queue.sort(key=lambda j: j.get("score") or 0, reverse=True)

    st.markdown(f'<div class="section-label">{len(queue)} jobs in queue</div>', unsafe_allow_html=True)

    for job in queue:
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

    search = st.text_input("Search", placeholder="Company or title...")
    if search:
        applied = [a for a in applied if
                   search.lower() in (a.get("title") or "").lower() or
                   search.lower() in (a.get("company") or "").lower()]

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

    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.multiselect(
            "Status", df["status"].unique().tolist(),
            default=df["status"].unique().tolist(),
        )
    with col2:
        min_score = st.slider("Min score", 0, 10, 0)
    with col3:
        search = st.text_input("Search title / company")

    filtered = df[
        df["status"].isin(status_filter) &
        (df["score"].fillna(0) >= min_score)
    ]
    if search:
        mask = (
            filtered["title"].str.contains(search, case=False, na=False) |
            filtered["company"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]

    st.markdown(f'<div class="section-label">{len(filtered)} results</div>', unsafe_allow_html=True)

    display_cols = ["title", "company", "location", "score", "status", "seniority", "salary_match", "source"]
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
            update_status(selected_id, new_status)
            st.success(f"Updated → {new_status}")
            st.rerun()


# ═══════════════════════════════════════════════════════════════════
# RUN PIPELINE
# ═══════════════════════════════════════════════════════════════════
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
                jobs = scrape_all(target_roles=st.session_state.get("target_roles") or None)

            st.info(f"Scraped {len(jobs)} jobs total")

            from tracker import get_seen_ids
            seen = get_seen_ids()
            new_jobs = [j for j in jobs if j["id"] not in seen]

            # Beta cap
            if len(new_jobs) > BETA_JOB_LIMIT:
                st.info(f"Beta limit: capping at {BETA_JOB_LIMIT} of {len(new_jobs)} new jobs")
                new_jobs = new_jobs[:BETA_JOB_LIMIT]
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
                )

                progress.progress(80, text=f"Writing cover letters for {len(qualified)} qualified jobs...")
                from tracker import upsert_jobs
                upsert_jobs(all_scored)

                log_experiment_run(
                    run_label=run_label.strip(),
                    scoring_mode=scoring_mode,
                    hybrid_threshold=hybrid_min,
                    cover_letters_enabled=enable_letters,
                    jobs_scraped=len(jobs),
                    jobs_new=len(new_jobs),
                    jobs_qualified=len(qualified),
                    note=run_note.strip(),
                )

                progress.progress(100, text="Done.")
                st.success(f"✓ Pipeline complete — {len(qualified)} jobs scored 8+ added to Review Queue.")

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
                jobs = scrape_all(target_roles=st.session_state.get("target_roles") or None)
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

    recent_runs = get_recent_runs(limit=8)
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
