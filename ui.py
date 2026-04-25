"""
Job Bot — Streamlit UI
Run: streamlit run ui.py
"""
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# So imports resolve to job-bot modules
sys.path.insert(0, str(Path(__file__).parent))

from tracker import (
    get_all_applications, get_review_queue,
    update_status, get_seen_ids,
)

# ── Page config ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Bot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Minimal dark theme override ────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stSidebar"] { background: #0f0f10; }
  .metric-card {
    background: #131315;
    border: 1px solid #1f1f22;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 12px;
  }
  .metric-card .label {
    font-family: monospace;
    font-size: 11px;
    color: #4a4a45;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    margin-bottom: 6px;
  }
  .metric-card .value {
    font-size: 32px;
    font-weight: 600;
    color: #f5f4ee;
    line-height: 1;
  }
  .metric-card .sub {
    font-size: 12px;
    color: #8b8b85;
    margin-top: 4px;
  }
  .score-high { color: #d4ff3a; font-weight: 600; }
  .score-mid  { color: #f5c518; font-weight: 600; }
  .score-low  { color: #ff6b6b; font-weight: 600; }
  .tag {
    display: inline-block;
    font-family: monospace;
    font-size: 10px;
    padding: 2px 8px;
    border-radius: 4px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-right: 4px;
  }
  .tag-new       { background: #1a1f0a; color: #d4ff3a; border: 1px solid #2a3510; }
  .tag-applied   { background: #0a1a1f; color: #3ad4ff; border: 1px solid #102a35; }
  .tag-interview { background: #1a0f1a; color: #d43aff; border: 1px solid #2a1035; }
  .tag-rejected  { background: #1f0a0a; color: #ff3a3a; border: 1px solid #350f0f; }
  .tag-skipped   { background: #1a1a1a; color: #666; border: 1px solid #333; }
  .cover-letter {
    background: #131315;
    border: 1px solid #1f1f22;
    border-left: 3px solid #d4ff3a;
    border-radius: 4px;
    padding: 16px 20px;
    font-size: 14px;
    color: #c8c8c0;
    white-space: pre-wrap;
    line-height: 1.7;
    font-family: monospace;
  }
</style>
""", unsafe_allow_html=True)


# ── Sidebar nav ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🤖 Job Bot")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["Dashboard", "Review Queue", "All Applications", "Run Pipeline"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption("techturi.org · Tega Eshareturi")


# ── Helper: score badge ────────────────────────────────────────────
def score_badge(score):
    score = score or 0
    cls = "score-high" if score >= 8 else "score-mid" if score >= 6 else "score-low"
    return f'<span class="{cls}">{score}/10</span>'

def status_tag(status):
    cls = f"tag tag-{status}" if status in ("new","applied","interview","rejected","skipped") else "tag"
    return f'<span class="{cls}">{status}</span>'


# ═══════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════
if page == "Dashboard":
    st.markdown("## Dashboard")

    apps = get_all_applications()
    if not apps:
        st.info("No applications tracked yet. Run the pipeline to get started.")
        st.stop()

    df = pd.DataFrame(apps)

    # ── Stats row ────────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)
    status_counts = df["status"].value_counts().to_dict()

    def metric(col, label, value, sub=""):
        col.markdown(f"""
        <div class="metric-card">
          <div class="label">{label}</div>
          <div class="value">{value}</div>
          {"<div class='sub'>" + sub + "</div>" if sub else ""}
        </div>""", unsafe_allow_html=True)

    metric(col1, "Total Tracked", len(df))
    metric(col2, "Applied",       status_counts.get("applied", 0))
    metric(col3, "Interviews",    status_counts.get("interview", 0))
    metric(col4, "In Queue",      status_counts.get("new", 0), "awaiting review")
    metric(col5, "Avg Score",     f"{df['score'].dropna().mean():.1f}" if not df['score'].dropna().empty else "—")

    st.markdown("---")

    # ── Score distribution ───────────────────────────────────────
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### Score Distribution")
        score_df = df["score"].dropna().value_counts().sort_index()
        if not score_df.empty:
            st.bar_chart(score_df)

    with col_b:
        st.markdown("#### Status Breakdown")
        if status_counts:
            st.bar_chart(pd.Series(status_counts))

    # ── Top 10 by score ─────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Top 10 by Score")
    top = df.nlargest(10, "score")[["title", "company", "location", "score", "score_reason", "status"]]
    st.dataframe(top, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════
# REVIEW QUEUE
# ═══════════════════════════════════════════════════════════════════
elif page == "Review Queue":
    st.markdown("## Review Queue")
    st.caption("Jobs scored 7+ awaiting your decision. Actions update Supabase immediately.")

    queue = get_review_queue(min_score=7)
    if not queue:
        st.success("Queue is empty — nothing to review.")
        st.stop()

    st.markdown(f"**{len(queue)} jobs** in queue")
    st.markdown("---")

    for job in queue:
        score = job.get("score") or 0
        with st.expander(
            f"{'🟢' if score >= 8 else '🟡'} {score}/10 — {job['title']} @ {job.get('company','?')}",
            expanded=False,
        ):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"**Location:** {job.get('location','Unknown')}")
                st.markdown(f"**Score reason:** {job.get('score_reason','')}")
                st.markdown(f"**Salary match:** {job.get('salary_match','Unknown')}")
                st.markdown(f"**Seniority:** {job.get('seniority','Unknown')}")
                st.markdown(f"**Source:** {job.get('source','')}")
                if job.get("url"):
                    st.markdown(f"[Open job posting ↗]({job['url']})")

            with col2:
                new_status = st.selectbox(
                    "Update status",
                    ["— no change —", "applied", "interview", "skipped", "rejected"],
                    key=f"status_{job['id']}",
                )
                if new_status != "— no change —":
                    if st.button("Save", key=f"save_{job['id']}"):
                        update_status(job["id"], new_status)
                        st.success(f"→ {new_status}")
                        st.rerun()

            if job.get("cover_letter"):
                st.markdown("**Cover Letter**")
                st.markdown(
                    f'<div class="cover-letter">{job["cover_letter"]}</div>',
                    unsafe_allow_html=True,
                )


# ═══════════════════════════════════════════════════════════════════
# ALL APPLICATIONS
# ═══════════════════════════════════════════════════════════════════
elif page == "All Applications":
    st.markdown("## All Applications")

    apps = get_all_applications()
    if not apps:
        st.info("No applications tracked yet.")
        st.stop()

    df = pd.DataFrame(apps)

    # ── Filters ─────────────────────────────────────────────────
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

    st.markdown(f"**{len(filtered)}** results")

    display_cols = ["title", "company", "location", "score", "status", "seniority", "salary_match", "source"]
    available = [c for c in display_cols if c in filtered.columns]
    st.dataframe(filtered[available], use_container_width=True, hide_index=True)

    # ── Inline status edit ───────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Quick Status Update")
    job_options = {f"{r['title']} @ {r.get('company','?')} (score: {r.get('score','?')})": r["id"]
                   for _, r in filtered.iterrows()}
    if job_options:
        selected_label = st.selectbox("Select job", list(job_options.keys()))
        selected_id = job_options[selected_label]
        new_status = st.selectbox("New status", ["applied", "interview", "skipped", "rejected", "new"])
        if st.button("Update Status"):
            update_status(selected_id, new_status)
            st.success(f"Updated → {new_status}")
            st.rerun()


# ═══════════════════════════════════════════════════════════════════
# RUN PIPELINE
# ═══════════════════════════════════════════════════════════════════
elif page == "Run Pipeline":
    st.markdown("## Run Pipeline")
    st.caption("Scrape → Score → Save. New jobs only — already-seen jobs are skipped.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Full Pipeline")
        st.markdown("Scrape all sources, score with Haiku, generate cover letters with Sonnet for 7+ jobs.")
        if st.button("▶ Run Full Pipeline", type="primary"):
            with st.spinner("Scraping jobs..."):
                from scrapers import scrape_all
                jobs = scrape_all()

            st.info(f"Scraped {len(jobs)} jobs total")

            from tracker import get_seen_ids
            seen = get_seen_ids()
            new_jobs = [j for j in jobs if j["id"] not in seen]
            st.info(f"{len(new_jobs)} new (unseen) jobs to score")

            if not new_jobs:
                st.success("Nothing new to score. Queue is up to date.")
            else:
                with st.spinner(f"Scoring {len(new_jobs)} jobs with Claude Haiku..."):
                    from agent import process_jobs
                    all_scored, qualified = process_jobs(new_jobs, verbose=False)

                with st.spinner("Saving to Supabase..."):
                    from tracker import upsert_jobs
                    upsert_jobs(all_scored)

                st.success(f"Done — {len(qualified)} jobs scored 7+ added to review queue.")

                if qualified:
                    st.markdown("#### Qualified Jobs")
                    q_df = pd.DataFrame(qualified)[["title", "company", "score", "score_reason", "seniority"]]
                    st.dataframe(q_df, use_container_width=True, hide_index=True)

    with col2:
        st.markdown("#### Scrape Only")
        st.markdown("Just fetch raw jobs — no scoring or API calls.")
        if st.button("▶ Scrape Only"):
            with st.spinner("Scraping..."):
                from scrapers import scrape_all
                jobs = scrape_all()
            st.success(f"Scraped {len(jobs)} jobs")
            preview = pd.DataFrame(jobs[:20])[["title", "company", "location", "source"]]
            st.dataframe(preview, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### Current Stats")
    apps = get_all_applications()
    if apps:
        df = pd.DataFrame(apps)
        seen_count = len(df)
        queue_count = len(df[df["status"] == "new"])
        applied_count = len(df[df["status"] == "applied"])
        st.markdown(f"- **{seen_count}** total jobs tracked  ")
        st.markdown(f"- **{queue_count}** in review queue  ")
        st.markdown(f"- **{applied_count}** applied")
    else:
        st.info("No data yet.")
