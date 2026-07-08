#!/usr/bin/env python3
"""
Job Bot — CLI entry point
Usage:
  python main.py scrape                      # Pull new jobs, score with embed (default)
  python main.py scrape --backend claude     # Force Claude for all scoring
  python main.py scrape --backend hybrid     # Keyword pre-filter + Claude
  python main.py scrape --backend cheap      # Heuristic only, no LLM
  python main.py review          # Review queue in terminal
  python main.py apply           # Auto-fill & submit queued applications (review-first)
  python main.py linkedin-login  # One-time LinkedIn login (saves session cookies)
  python main.py status          # Show application stats
  python main.py setup-db        # Create Supabase table
"""
import sys
from scrapers import scrape_all
from agent import process_jobs
from tracker import upsert_jobs, get_all_applications, get_seen_ids


def cmd_scrape():
    # Parse --backend flag; default to embed (cheapest, recommended)
    args = sys.argv[2:]
    backend = "embed"
    if "--backend" in args:
        idx = args.index("--backend")
        if idx + 1 < len(args):
            backend = args[idx + 1]
    valid = {"embed", "hybrid", "claude", "cheap"}
    if backend not in valid:
        print(f"Unknown backend '{backend}'. Choose from: {', '.join(sorted(valid))}")
        return

    print(f"🚀 Starting job pipeline... (backend={backend})\n")
    from config import TARGET_ROLES, MIN_SALARY
    jobs = scrape_all(target_roles=TARGET_ROLES, min_salary=MIN_SALARY)
    if not jobs:
        print("No jobs found.")
        return

    # CLI mode: no user_id — seen IDs are raw (unscoped) 16-char hashes
    seen = get_seen_ids(user_id=None)
    new_jobs = [j for j in jobs if j["id"] not in seen]
    print(f"  {len(jobs)} scraped · {len(seen)} already seen · {len(new_jobs)} new\n")

    if not new_jobs:
        print("Nothing new to score.")
        return

    # Enrich LinkedIn jobs with full descriptions before scoring
    li_count = sum(1 for j in new_jobs if "linkedin.com" in (j.get("url") or "") and not j.get("description"))
    if li_count:
        print(f"\n🌐 Enriching {li_count} LinkedIn jobs with full descriptions...")
        from fetcher import enrich_jobs
        enrich_jobs(new_jobs)

    from config import RESUME_TEXT, TARGET_ROLES, MIN_SALARY
    all_scored, qualified = process_jobs(
        new_jobs,
        resume_text=RESUME_TEXT,
        target_roles=TARGET_ROLES,
        min_salary=MIN_SALARY,
        scoring_backend=backend,
    )
    upsert_jobs(all_scored, user_id=None)   # CLI: no user isolation
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


COMMANDS = {
    "scrape":         cmd_scrape,
    "review":         cmd_review,
    "apply":          cmd_apply,
    "manual":         cmd_manual,
    "status":         cmd_status,
    "setup-db":       cmd_setup_db,
    "linkedin-login": cmd_linkedin_login,
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd in COMMANDS:
        COMMANDS[cmd]()
    else:
        print("Usage: python main.py [scrape|review|status|setup-db]")
