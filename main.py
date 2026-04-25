#!/usr/bin/env python3
"""
Job Bot — CLI entry point
Usage:
  python main.py scrape          # Pull new jobs, score them, save to Supabase
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
    print("🚀 Starting job pipeline...\n")
    jobs = scrape_all()
    if not jobs:
        print("No jobs found.")
        return

    # Skip jobs already scored — prevents re-charging on every run
    seen = get_seen_ids()
    new_jobs = [j for j in jobs if j["id"] not in seen]
    print(f"  {len(jobs)} scraped · {len(seen)} already seen · {len(new_jobs)} new\n")

    if not new_jobs:
        print("Nothing new to score.")
        return

    all_scored, qualified = process_jobs(new_jobs)
    upsert_jobs(all_scored)   # save everything so low scorers are never re-scored
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
  created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_applications_score ON job_applications(score DESC);
CREATE INDEX IF NOT EXISTS idx_job_applications_status ON job_applications(status);
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
