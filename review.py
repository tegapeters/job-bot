"""
Review CLI — shows scored jobs, lets Tega approve/skip/open each one
"""
import os
import webbrowser
from tracker import get_review_queue, update_status

STATUSES = {
    "a": "applied",
    "s": "skipped",
    "i": "interview",
    "r": "rejected",
}

COLORS = {
    10: "\033[92m",   # bright green
    9:  "\033[92m",
    8:  "\033[93m",   # yellow
    7:  "\033[93m",
    6:  "\033[91m",   # red
    0:  "\033[91m",
}
RESET = "\033[0m"
BOLD  = "\033[1m"
DIM   = "\033[2m"


def color(score: int) -> str:
    for k in sorted(COLORS.keys(), reverse=True):
        if score >= k:
            return COLORS[k]
    return RESET


def review():
    queue = get_review_queue()
    if not queue:
        print("✅ No jobs in review queue.")
        return

    print(f"\n{BOLD}── Review Queue ({len(queue)} jobs) ──{RESET}\n")

    for i, job in enumerate(queue):
        score = job.get("score", 0) or 0
        c = color(score)

        print(f"{BOLD}[{i+1}/{len(queue)}]{RESET} {c}{BOLD}{job['title']}{RESET}")
        print(f"  Company  : {job.get('company', 'Unknown')}")
        print(f"  Location : {job.get('location', 'Unknown')}")
        print(f"  Score    : {c}{score}/10{RESET} — {job.get('score_reason', '')}")
        print(f"  Salary   : {job.get('salary_match', 'Unknown')}")
        print(f"  URL      : {DIM}{job.get('url', '')}{RESET}")
        print()

        if job.get("cover_letter"):
            show_cl = input("  Show cover letter? [y/N] ").strip().lower()
            if show_cl == "y":
                print(f"\n{DIM}{'─'*60}{RESET}")
                print(job["cover_letter"])
                print(f"{DIM}{'─'*60}{RESET}\n")

        open_url = input("  Open in browser? [y/N] ").strip().lower()
        if open_url == "y":
            webbrowser.open(job.get("url", ""))

        print(f"  Action: {BOLD}[a]{RESET}pplied  {BOLD}[s]{RESET}kip  {BOLD}[r]{RESET}eject  {BOLD}[Enter]{RESET}=skip")
        action = input("  > ").strip().lower()

        new_status = STATUSES.get(action, "new")
        if new_status != "new":
            update_status(job["id"], new_status)
            print(f"  → Marked as {new_status}\n")
        else:
            print(f"  → Skipped\n")

        print(f"{DIM}{'─'*60}{RESET}\n")

    print("✅ Review complete.")


if __name__ == "__main__":
    review()
