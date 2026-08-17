#!/usr/bin/env python3
"""
Job Bot — CLI entry point
Usage:
  python main.py scrape                      # Pull new jobs, score with Claude (default)
  python main.py scrape --backend hybrid     # Keyword pre-filter + Claude (faster, ~60% cost)
  python main.py scrape --backend cheap      # Heuristic only, no LLM (dev/testing)
  python main.py review          # Review queue in terminal
  python main.py apply           # Auto-fill & submit queued applications (review-first)
  python main.py linkedin-login  # One-time LinkedIn login (saves session cookies)
  python main.py status          # Show application stats
  python main.py setup-db        # Create Supabase table
"""
import sys
from scrapers import scrape_all
from agent import process_jobs
from tracker import upsert_jobs, get_all_applications, get_seen_ids, get_actioned_fingerprints, get_stale_listings, mark_closed


def cmd_scrape():
    import time
    from tracker import log_experiment_run
    from config import ENABLE_COVER_LETTERS

    # Parse --backend flag; default to claude
    args = sys.argv[2:]
    backend = "claude"
    if "--backend" in args:
        idx = args.index("--backend")
        if idx + 1 < len(args):
            backend = args[idx + 1]
    valid = {"hybrid", "claude", "cheap"}
    if backend not in valid:
        print(f"Unknown backend '{backend}'. Choose from: {', '.join(sorted(valid))}")
        return

    t_total = time.perf_counter()
    timings: dict[str, float] = {}

    print(f"🚀 Starting job pipeline... (backend={backend})\n")

    # ── Closed-listing sweep before scraping ──────────────────────
    stale = get_stale_listings(user_id=None, min_days=5, max_score=6)
    if stale:
        from fetcher import check_closed_listings
        closed_ids = check_closed_listings(stale)
        if closed_ids:
            n_closed = mark_closed(closed_ids, user_id=None)
            print(f"  🚫 Marked {n_closed} stale listing(s) as closed\n")

    from config import TARGET_ROLES, MIN_SALARY

    t = time.perf_counter()
    jobs = scrape_all(target_roles=TARGET_ROLES, min_salary=MIN_SALARY)
    timings["scrape_s"] = round(time.perf_counter() - t, 1)

    if not jobs:
        print("No jobs found.")
        return

    # CLI mode: no user_id — seen IDs are raw (unscoped) 16-char hashes
    seen = get_seen_ids(user_id=None)
    actioned = get_actioned_fingerprints(user_id=None)
    new_jobs = [j for j in jobs if j["id"] not in seen]

    # Cross-source dedup: skip any job whose (title, company) already has a
    # non-new status so skipped/applied jobs don't resurface from a new source.
    new_jobs = [
        j for j in new_jobs
        if ((j.get("title") or "").lower().strip(),
            (j.get("company") or "").lower().strip()) not in actioned
    ]

    # Collapse duplicates by (normalized title, normalized company)
    _seen_tc: dict[tuple, dict] = {}
    for j in new_jobs:
        key = (j.get("title", "").strip().lower(), j.get("company", "").strip().lower())
        existing = _seen_tc.get(key)
        if existing is None or len(j.get("description") or "") > len(existing.get("description") or ""):
            _seen_tc[key] = j
    deduped_jobs = list(_seen_tc.values())

    print(f"  {len(jobs)} scraped · {len(seen)} already seen · {len(new_jobs)} new · {len(new_jobs)-len(deduped_jobs)} title+company dupes removed\n")

    if not deduped_jobs:
        print("Nothing new to score.")
        return

    # Enrich LinkedIn jobs with full descriptions before scoring
    li_count = sum(1 for j in deduped_jobs if "linkedin.com" in (j.get("url") or "") and not j.get("description"))
    if li_count:
        print(f"\n🌐 Enriching {li_count} LinkedIn jobs with full descriptions...")
        from fetcher import enrich_jobs
        t = time.perf_counter()
        enrich_jobs(deduped_jobs)
        timings["enrich_prefetch_s"] = round(time.perf_counter() - t, 1)

    from config import RESUME_TEXT, TARGET_ROLES, MIN_SALARY
    all_scored, qualified, stage_timings = process_jobs(
        deduped_jobs,
        resume_text=RESUME_TEXT,
        target_roles=TARGET_ROLES,
        min_salary=MIN_SALARY,
        scoring_backend=backend,
    )
    timings.update(stage_timings)

    t = time.perf_counter()
    upsert_jobs(all_scored, user_id=None)
    timings["save_s"] = round(time.perf_counter() - t, 1)

    timings["total_s"] = round(time.perf_counter() - t_total, 1)

    # ── Timing summary ────────────────────────────────────────────
    print("\n⏱️  Pipeline timing breakdown:")
    labels = {
        "scrape_s":          "Scraping (all sources)",
        "enrich_prefetch_s": "LinkedIn pre-fetch",
        "pass1_s":           "Pass 1 pre-filter",
        "enrich_s":          "LinkedIn enrich (Pass 2)",
        "pass2_s":           "Pass 2 scoring",
        "cover_letters_s":   "Cover letters",
        "save_s":            "Supabase save",
        "total_s":           "TOTAL",
    }
    for key, label in labels.items():
        if key in timings:
            sep = "─" * 36 if key == "total_s" else " "
            print(f"  {label:<28} {timings[key]:>6.1f}s")
    print(f"  {'─'*36}")
    print(f"  {'TOTAL':<28} {timings['total_s']:>6.1f}s")

    log_experiment_run(
        run_label=f"cli/{backend}",
        scoring_mode=backend,
        hybrid_threshold=6,
        cover_letters_enabled=ENABLE_COVER_LETTERS,
        jobs_scraped=len(jobs),
        jobs_new=len(deduped_jobs),
        jobs_qualified=len(qualified),
        total_seconds=timings["total_s"],
        timing_json=timings,
    )

    print(f"\n🎯 Done. {len(qualified)} jobs scored 7+ queued for review.")
    print("   Run: python main.py review")


def cmd_review():
    from review import review
    review()


def cmd_apply():
    from submitter import run_auto_apply
    from tracker import get_review_queue
    jobs = get_review_queue(min_score=7)
    if not jobs:
        print("No jobs in review queue. Run: python main.py scrape")
        return
    run_auto_apply(jobs, min_score=7)


def cmd_status():
    apps = get_all_applications()
    if not apps:
        print("No applications tracked yet.")
        return

    from collections import Counter
    statuses = Counter(a.get("status", "new") for a in apps)

    print("\n── Application Status ──")
    print(f"  Total tracked : {len(apps)}")
    for status, count in statuses.most_common():
        print(f"  {status:<12} : {count}")

    # Top scored
    top = sorted(apps, key=lambda x: x.get("score") or 0, reverse=True)[:5]
    print("\n── Top 5 by Score ──")
    for j in top:
        print(f"  {j.get('score',0)}/10  {j['title']} @ {j.get('company','')}")


def cmd_setup_db():
    """Print the SQL to run in Supabase dashboard."""
    sql = """
-- Run this in your Supabase SQL editor:

CREATE TABLE IF NOT EXISTS job_applications (
  id            TEXT PRIMARY KEY,
  user_id       UUID,
  source        TEXT,
  title         TEXT,
  company       TEXT,
  location      TEXT,
  url           TEXT,
  description   TEXT,
  posted_at     TEXT,
  status        TEXT DEFAULT 'new',
  score         INTEGER,
  score_reason  TEXT,
  seniority     TEXT,
  salary_match  TEXT,
  cover_letter  TEXT,
  scored_by     TEXT DEFAULT '',
  created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_applications_score   ON job_applications(score DESC);
CREATE INDEX IF NOT EXISTS idx_job_applications_status  ON job_applications(status);
CREATE INDEX IF NOT EXISTS idx_job_applications_user_id ON job_applications(user_id);

CREATE TABLE IF NOT EXISTS application_events (
  id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id    UUID,
  job_id     TEXT REFERENCES job_applications(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  detail     TEXT DEFAULT '',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_application_events_job_id  ON application_events(job_id);
CREATE INDEX IF NOT EXISTS idx_application_events_type    ON application_events(event_type);
CREATE INDEX IF NOT EXISTS idx_application_events_user_id ON application_events(user_id);

CREATE TABLE IF NOT EXISTS pipeline_runs (
  id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id               UUID,
  run_label             TEXT,
  scoring_mode          TEXT NOT NULL,
  hybrid_threshold      INTEGER DEFAULT 6,
  cover_letters_enabled BOOLEAN DEFAULT FALSE,
  jobs_scraped          INTEGER DEFAULT 0,
  jobs_new              INTEGER DEFAULT 0,
  jobs_qualified        INTEGER DEFAULT 0,
  note                  TEXT DEFAULT '',
  total_seconds         FLOAT,
  timing_json           JSONB,
  created_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created_at ON pipeline_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_user_id    ON pipeline_runs(user_id);

CREATE TABLE IF NOT EXISTS user_sessions (
  id           TEXT PRIMARY KEY,
  resume_text  TEXT,
  target_roles JSONB,
  updated_at   TIMESTAMPTZ DEFAULT NOW()
);
"""
    print(sql)
    print("Copy the above SQL and run it in: https://supabase.com/dashboard/project/mokqyqgdjtxtstrviorr/sql")


def cmd_manual():
    """Show jobs that need manual application — no Easy Apply available."""
    from tracker import get_manual_queue, update_status
    import webbrowser

    jobs = get_manual_queue()
    if not jobs:
        print("No jobs in manual queue.")
        return

    print(f"\n── Manual Apply Queue ({len(jobs)} jobs) ──\n")
    for job in jobs:
        score = job.get("score", "?")
        title = job.get("title", "")
        company = job.get("company", "")
        url = job.get("url", "")

        print(f"{'─'*60}")
        print(f"  {score}/10  {title} @ {company}")
        print(f"  URL : {url}")
        print(f"\n  Cover letter:\n")
        cl = (job.get("cover_letter") or "None generated.")
        for line in cl.split("\n"):
            print(f"    {line}")

        ans = input("\n  [o=open, a=mark applied, s=skip, q=quit] → ").strip().lower()
        if ans == "q":
            break
        if ans == "o":
            webbrowser.open(url)
            ans = input("  Mark as applied? [y/n] → ").strip().lower()
            if ans == "y":
                update_status(job["id"], "applied")
                print("  ✅ Marked as applied")
        elif ans == "a":
            update_status(job["id"], "applied")
            print("  ✅ Marked as applied")
        elif ans == "s":
            update_status(job["id"], "skipped")
            print("  → Skipped")


def cmd_linkedin_login():
    from submitter import linkedin_login
    linkedin_login()


def cmd_scan_rejections():
    """Scan Gmail inbox for rejection emails and mark matched applied jobs."""
    import os, getpass
    from tracker import get_all_applications, update_status
    from rejection_scanner import scan_inbox

    gmail_email = os.getenv("GMAIL_APPLY_EMAIL") or input("Gmail address you apply with: ").strip()
    app_password = os.getenv("GMAIL_APP_PASSWORD") or getpass.getpass("App Password (16-char): ").replace(" ", "")

    apps = get_all_applications(user_id=None)
    applied = [a for a in apps if a.get("status") == "applied"]

    if not applied:
        print("No applied jobs to check against.")
        return

    print(f"\n📬 Scanning inbox for rejections ({len(applied)} applied jobs to check)…")
    try:
        matches = scan_inbox(gmail_email, app_password, applied, lookback_days=90)
    except ConnectionError as e:
        print(f"❌ {e}")
        return

    if not matches:
        print("✅ No rejection emails found. Good news!")
        return

    print(f"\n⚠️  Found {len(matches)} possible rejection(s):\n")
    to_mark = []
    for m in matches:
        j = m["job"]
        conf = int(m["confidence"] * 100)
        print(f"  {'🔴' if conf >= 80 else '🟡'} [{conf}%] {j['title']} @ {j.get('company','')}")
        print(f"      From: {m['email_from']}")
        print(f"      Subj: {m['email_subject']}")
        print(f"      Date: {m['email_date']}")
        print(f"      \"{m['snippet'][:120]}…\"\n")
        ans = input("  Mark as rejected? [y/N] → ").strip().lower()
        if ans == "y":
            to_mark.append(j["id"])

    if to_mark:
        for jid in to_mark:
            update_status(jid, "rejected", user_id=None)
        print(f"\n✅ Marked {len(to_mark)} job(s) as rejected.")
    else:
        print("\nNo changes made.")


COMMANDS = {
    "scrape":            cmd_scrape,
    "review":            cmd_review,
    "apply":             cmd_apply,
    "manual":            cmd_manual,
    "status":            cmd_status,
    "setup-db":          cmd_setup_db,
    "linkedin-login":    cmd_linkedin_login,
    "scan-rejections":   cmd_scan_rejections,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print("Usage: python main.py [scrape|review|status|setup-db]")
