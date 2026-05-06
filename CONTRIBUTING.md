# Contributing to Job Pal

This project is optimized for safe, review-first automation. Keep changes small, test end-to-end, and protect multi-user behavior.

## Start Here

- Read `CLAUDE.md` first (authoritative architecture and guardrails).
- Use `ui_v2.py` for all UI work. Do not edit `ui.py` (legacy).
- Check recent changes before editing (`git log --oneline -5`).

## Architecture Invariants (Do Not Break)

- Pipeline order is: scrape -> score -> optional cover letter -> persist to Supabase -> UI review.
- Dedup must remain stable (`id` + upsert conflict behavior).
- Status lifecycle must remain coherent (`new`, `applied`, `interview`, `rejected`, `skipped`, `application_closed`, and `manual_review` where used).
- Multi-user flows must use session `resume_text`, not global fallback values.
- Auto-apply must remain review-first and conservative.

## Safety-Critical Config

Review changes to these values with extra care in `config.py`:

- `REVIEW_MIN_SCORE`
- `COVER_LETTER_MIN_SCORE`
- `AUTO_APPLY_MIN_SCORE`

Current intent:

- `AUTO_APPLY_MIN_SCORE` is intentionally above max score to prevent autonomous auto-apply.

## Safe vs Risky Areas

### Lower Risk (usually safe)

- `scrapers/*` source-specific extraction updates
- UI presentation-only changes in `ui_v2.py` (labels/layout/filters)
- Non-persistence utility refactors

### Medium Risk (requires workflow validation)

- `agent.py` scoring and cover-letter behavior
- `tracker.py` read/write query changes
- `main.py` pipeline orchestration commands
- `sessions.py` session save/restore behavior

### High Risk (double-check before merging)

- `ui_v2.py` session identity and resume plumbing
- Any status transition write logic
- Dedup/upsert identity strategy (`id`, normalized URL handling)
- `submitter.py` apply gating and confirmation behavior

## Required Checks Before Merge

- Run one full pipeline pass locally and confirm data appears in UI.
- Validate score gating still works (review and cover-letter thresholds).
- Confirm session isolation with two different `uid` values.
- Verify status transitions still work in queue and applied/interview views.
- Confirm no path can auto-apply below policy.
- Confirm no secrets are committed.

## Database and Data Hygiene

- Keep `job_applications` schema compatibility unless a migration is intentional.
- Preserve idempotent writes (`upsert` on conflict key).
- Avoid schema drift in free-text statuses unless UI selectors/tags are updated accordingly.

## Secrets and Security

- Never commit API keys, tokens, or personal resume data.
- Use `.env` locally and cloud secrets in Streamlit Cloud.
- Avoid introducing scraping behavior that increases ToS/compliance risk.

## PR Guidance

- Keep PRs focused on one concern.
- Include a short "what changed" and "why" in the PR body.
- Add manual test notes for:
  - pipeline run
  - session isolation
  - status transitions
  - safety gates

## When Adding Features

### New scraper

- Return normalized job payloads that match current schema.
- Generate deterministic IDs consistently.
- Register source in `scrapers/__init__.py`.
- Validate dedup does not regress.

### New status

- Add display tag/style and selector options in `ui_v2.py`.
- Add transition path(s) where relevant.
- Verify filtering/bulk update behavior.

### Threshold changes

- Update `config.py`.
- Re-test queue volume and cover-letter generation behavior.
- Document rationale in commit/PR.

