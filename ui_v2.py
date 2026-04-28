"""
Job Pal — Streamlit UI v2 (Techturi branded)
Run: streamlit run ui_v2.py
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tracker import (
    get_all_applications, get_review_queue,
    update_status, get_seen_ids,
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
  .tag-new       { background: #1a1f0a; color: #D4FF3A; border: 1px solid #2a3510; }
  .tag-applied   { background: #0a1a1f; color: #3ad4ff; border: 1px solid #102a35; }
  .tag-interview { background: #1a0f1a; color: #d43aff; border: 1px solid #2a1035; }
  .tag-rejected  { background: #1f0a0a; color: #ff3a3a; border: 1px solid #350f0f; }
  .tag-skipped   { background: #1a1a1a; color: #666; border: 1px solid #333; }

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

  /* ── Primary buttons — toned down ── */
  [data-testid="baseButton-primary"] {
    background: #1a2a00 !important;
    color: #D4FF3A !important;
    border: 1px solid #D4FF3A !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    letter-spacing: 0.1em !important;
  }
  [data-testid="baseButton-primary"]:hover {
    background: #243800 !important;
    border-color: #D4FF3A !important;
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
    cls = f"tag tag-{status}" if status in ("new","applied","interview","rejected","skipped") else "tag"
    return f'<span class="{cls}">{status}</span>'

def safe_get_apps():
    """Fetch all applications, showing a clean error if Supabase is unreachable."""
    try:
        return get_all_applications()
    except Exception as e:
        st.error(f"Cannot connect to database. Check Supabase secrets in Streamlit Cloud settings. Error: `{e}`")
        st.stop()

def safe_get_queue(min_score=7):
    try:
        return get_review_queue(min_score=min_score)
    except Exception as e:
        st.error(f"Cannot connect to database. Check Supabase secrets. Error: `{e}`")
        st.stop()

def job_card(job, key_prefix, next_statuses, expanded=False):
    """Render a full job card with details, cover letter, and status controls."""
    score = job.get("score") or 0
    icon = "🟢" if score >= 8 else "🟡" if score >= 6 else "🔴"
    with st.expander(
        f"{icon}  {score}/10  —  {job['title']} @ {job.get('company', '?')}",
        expanded=expanded,
    ):
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown(f"**Location:** {job.get('location', 'Unknown')}")
            st.markdown(f"**Score reason:** {job.get('score_reason', '')}")
            st.markdown(f"**Salary match:** {job.get('salary_match', 'Unknown')}")
            st.markdown(f"**Seniority:** {job.get('seniority', 'Unknown')}")
            st.markdown(f"**Source:** {job.get('source', '')}")
            if job.get("url"):
                st.markdown(f"[Open job posting ↗]({job['url']})")

        with col2:
            new_status = st.selectbox(
                "Move to",
                ["— no change —"] + next_statuses,
                key=f"{key_prefix}_sel_{job['id']}",
            )
            if new_status != "— no change —":
                if st.button("Save", key=f"{key_prefix}_save_{job['id']}", type="primary"):
                    update_status(job["id"], new_status)
                    st.success(f"→ {new_status}")
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
        "Senior Business Analyst",
        "Data Engineer",
        "AI Engineer",
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

    st.markdown('<div class="section-label" style="margin-top:28px">Top 10 by Score</div>', unsafe_allow_html=True)
    top = df.nlargest(10, "score")[["title", "company", "location", "score", "score_reason", "status"]]
    st.dataframe(top, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# REVIEW QUEUE
# ═══════════════════════════════════════════════════════════════════
elif page == "Review Queue":
    page_header("Review Queue", "Jobs worth <em>applying to.</em>")
    st.markdown('<div style="font-family:\'JetBrains Mono\',monospace;font-size:12px;color:#8B8B85;margin-bottom:24px">AI fit score 7+ · Status updates save instantly</div>', unsafe_allow_html=True)

    queue = safe_get_queue(min_score=7)
    if not queue:
        st.success("Queue is empty — nothing to review.")
        st.stop()

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
        job_card(job, "ap", ["interview", "rejected", "skipped"])


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
        job_card(job, "iv", ["rejected", "skipped"], expanded=True)


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
        new_status = st.selectbox("New status", ["new", "applied", "interview", "rejected", "skipped"])
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
        if st.button("▶ Run Full Pipeline", type="primary", use_container_width=True):
            with st.spinner("Scraping jobs..."):
                from scrapers import scrape_all
                jobs = scrape_all()

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
                all_scored, qualified = process_jobs(new_jobs, verbose=False, resume_text=resume_text)

                progress.progress(80, text=f"Writing cover letters for {len(qualified)} qualified jobs...")
                from tracker import upsert_jobs
                upsert_jobs(all_scored)

                progress.progress(100, text="Done.")
                st.success(f"✓ Pipeline complete — {len(qualified)} jobs scored 7+ added to Review Queue.")

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
                jobs = scrape_all()
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
