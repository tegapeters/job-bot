# Changelog

All notable changes to **Job Pal** (`job-bot`) are documented here.

Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [2026-05-06]

### Added

- **Scoring modes** (`cheap`, `hybrid`, `claude`): local heuristic scoring, optional hybrid escalation to Claude, and UI controls on **Run Pipeline** (`agent.py`, `config.py`, `ui_v2.py`).
- **Cover letter gating**: optional “Generate cover letters” in the UI; `ENABLE_COVER_LETTERS` env flag (`config.py`, `agent.py`).
- **Pipeline experiment runs**: `pipeline_runs` table (see `python main.py setup-db`), run label + notes, recent runs table with `qualified_pct`, `cost_mode`, best-run hint, CSV export (`tracker.py`, `ui_v2.py`, `main.py`).
- **Outcome tracking**: `application_events` table, status-change logging, outcome signals on job cards, dashboard chart (`tracker.py`, `ui_v2.py`, `main.py`).
- **Queue personalization**: optional rerank of **Review Queue** from outcome history (company, source, title overlap) (`tracker.py`, `ui_v2.py`).
- **Source health** on **Dashboard**: per-source totals, average score, 7+ qualified counts and share, jobs currently in review band (`tracker.py`, `ui_v2.py`).
- **CONTRIBUTING.md**: contributor safety checklist and high-risk file map.

### Changed

- **Cheap scorer** tuned for role-in-title weight, skills, location fit vs `config` prefs, salary hints when posted, stronger junior/exclusion penalties (`agent.py`).

### Repository

- **`.gitignore`**: `CVs/`, `.local_logs/`.

---

### Upgrade notes

1. Run `python main.py setup-db` and apply any **new** SQL in Supabase (especially `application_events`, `pipeline_runs` if not already created).
2. If using **RLS**, add policies for new tables (`application_events`, `pipeline_runs`) consistent with your existing `job_applications` / `user_sessions` policies.
3. Restart Streamlit after pulling: `streamlit run ui_v2.py --server.port 8503`.
