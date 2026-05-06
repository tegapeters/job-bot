# CLAUDE.md — Job Pal Agent Onboarding

Re-read this file at the start of every session in this directory. It is the authoritative guide for any Claude Code agent contributing to this project.

---

## What this project is

**Job Pal** — an AI-powered job search pipeline. It scrapes job boards, scores every listing against a user's resume using Claude, generates tailored cover letters for strong matches, and surfaces them in a Streamlit dashboard for review and tracking.

**Owner:** Tega Eshareturi (`tegapeters11@gmail.com`)
**Repo:** `github.com/tegapeters/job-bot`
**Local path:** `/Users/techturi/Documents/job-bot`
**Running instance:** `http://localhost:8503/?uid=cb187c6971384138`

---

## Project layout

```
job-bot/
├── ui_v2.py              — Streamlit UI (ACTIVE — always edit this, not ui.py)
├── agent.py              — Claude scoring + cover letter generation
├── config.py             — All thresholds, resume, applicant info, API keys
├── tracker.py            — Supabase read/write (job status, queue, dedup)
├── fetcher.py            — Enriches qualifying jobs with full descriptions from LinkedIn
├── main.py               — CLI entry point (scrape / review / status / setup-db)
├── scrapers/
│   ├── linkedin.py       — LinkedIn HTML scraper (session-cookie-free, public search)
│   ├── indeed.py         — Indeed RSS scraper
│   ├── remotive.py       — Remotive API (remote jobs)
│   ├── jobicy.py         — Jobicy API
│   └── weworkremotely.py — We Work Remotely RSS
├── sessions.py           — LinkedIn session cookie management
├── submitter.py          — Playwright auto-apply (review-first, not autonomous)
├── mcp_server.py         — MCP server so Claude can orchestrate via natural language
├── review.py             — Terminal review queue
├── requirements.txt
├── PRODUCT_BRIEF.md      — SaaS roadmap (V1 → V3 planning document)
└── BACKLOG.md            — Scoped backlog items with build triggers
```

**Never edit `ui.py`** — it is the old version. All UI work goes in `ui_v2.py`.

---

## Architecture

```
scrapers/* → main.py cmd_scrape()
                │
                ▼
         agent.process_jobs()
           ├── score_job()         → claude-sonnet-4-6  (scoring)
           └── generate_cover_letter() → claude-sonnet-4-6  (8+ only)
                │
                ▼
         tracker.upsert_jobs()    → Supabase (on_conflict="id")
                │
                ▼
         ui_v2.py                 → Streamlit dashboard
```

### Key thresholds (config.py)
| Constant | Value | Meaning |
|---|---|---|
| `REVIEW_MIN_SCORE` | 7 | Jobs scoring 7+ appear in review queue |
| `COVER_LETTER_MIN_SCORE` | 8 | Cover letters only generated for 8+ |
| `AUTO_APPLY_MIN_SCORE` | 11 | Effectively disabled (11 > max score of 10) |

---

## Models

| Task | Model | Why |
|---|---|---|
| Job scoring | `claude-sonnet-4-6` | Better at reasoning about transferable skills than Haiku |
| Cover letters | `claude-sonnet-4-6` | Quality matters for what the employer reads |

---

## Database — Supabase

**Table:** `job_applications`

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PK | MD5 hash of normalized job URL |
| `source` | TEXT | linkedin / indeed / remotive / jobicy / weworkremotely |
| `title` | TEXT | |
| `company` | TEXT | |
| `location` | TEXT | |
| `url` | TEXT | |
| `description` | TEXT | Max 5000 chars |
| `status` | TEXT | `new` → `applied` → `interview` → `rejected` / `skipped` / `application_closed` |
| `score` | INTEGER | 1–10 from Claude |
| `score_reason` | TEXT | One-sentence Claude explanation |
| `seniority` | TEXT | Junior / Mid / Senior / Director |
| `salary_match` | TEXT | Yes / No / Unknown |
| `cover_letter` | TEXT | Only present for 8+ scored jobs |
| `created_at` | TIMESTAMPTZ | Auto |

**Deduplication strategy:**
- `id` is `MD5(normalized_url)[:16]` — same job from same source always gets the same ID
- Indeed uses `jk=` param from URL as the key (not full URL) to survive location-query variation
- Supabase upsert with `on_conflict="id"` prevents re-scoring
- `tracker.get_review_queue()` applies a secondary title+company dedup in Python to collapse cross-source duplicates

---

## Application status lifecycle

```
new → applied → interview → rejected
              ↘ skipped
              ↘ application_closed
```

`application_closed` = role was posted then closed before you applied (orange badge in UI).

---

## Multi-user / session model

The app supports multiple users via a `?uid=` URL parameter:
- Each user gets a UUID stored in Supabase `sessions` table with their `resume_text` and `target_roles`
- The session is loaded on page load via `restore_session()` in `ui_v2.py`
- `resume_text` from `st.session_state["resume_text"]` is **always** passed explicitly to `score_job()` and `generate_cover_letter()` — never falls back to `config.RESUME_TEXT`
- `config.RESUME_TEXT` is Tega's personal resume — used only for CLI runs (`main.py scrape`)

---

## Cover letter rules

- Only generated for jobs scoring **8+**
- Prompt explicitly tells Claude to use the candidate's name **from the provided resume** — do not invent or assume
- If `resume_text` is None or empty, `generate_cover_letter()` returns an error string — no fallback to `config.RESUME_TEXT`

---

## Streamlit UI pages

| Page | What it shows |
|---|---|
| **Setup** | Resume upload/paste, target roles, salary floor. Required before running pipeline. |
| **Dashboard** | Metrics, score distribution chart, top 10 by score |
| **Review Queue** | Jobs scoring 7+ with status `new` — review and move to Applied/Skipped |
| **Applied** | Jobs you've applied to — move to Interview / Rejected / Closed |
| **Interviews** | Active interview pipeline |
| **All Jobs** | Full table with filters by status, search, bulk status update |
| **Run Pipeline** | Triggers `process_jobs()` inline — shows progress, saves to Supabase |

---

## Running locally

```bash
# Install deps
pip install -r requirements.txt

# Set env vars (.env file or export)
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
ANTHROPIC_API_KEY=...

# Start UI
streamlit run ui_v2.py --server.port 8503

# CLI scrape (uses config.py RESUME_TEXT)
python main.py scrape

# Check status
python main.py status
```

---

## Common tasks

### Add a new job source scraper
1. Create `scrapers/your_source.py` with a `scrape_yourname()` function
2. Return a list of dicts matching the schema above (id, source, title, company, location, url, description, posted_at, status, score, cover_letter)
3. Generate IDs with `hashlib.md5(normalized_url.encode()).hexdigest()[:16]`
4. Add to `scrapers/__init__.py` `scrape_all()` function
5. Test with `python main.py scrape`

### Change scoring threshold
Edit `config.py` — `REVIEW_MIN_SCORE` (queue visibility) and `COVER_LETTER_MIN_SCORE` (cover letter generation) are independent.

### Add a new application status
1. Add CSS tag style in `ui_v2.py` (look for `.tag-rejected` as a pattern)
2. Add to `status_tag()` valid list
3. Add to appropriate `next_statuses` lists in the job card calls
4. Add to bulk status selector
5. No DB schema change needed — status is a free-text column

### Debug a scoring issue
```python
from agent import score_job
from config import RESUME_TEXT
job = {"title": "...", "company": "...", "location": "...", "description": "..."}
result = score_job(job, resume_text=RESUME_TEXT)
print(result["score"], result["score_reason"])
```

---

## What NOT to do

- **Do not edit `ui.py`** — dead file, kept for reference only
- **Do not use `config.RESUME_TEXT` as a fallback in multi-user flows** — it's Tega's personal resume
- **Do not auto-apply without user confirmation** — `AUTO_APPLY_MIN_SCORE = 11` is intentional
- **Do not add LinkedIn scraping that requires authenticated sessions at scale** — ToS risk; see BACKLOG.md for the Jsearch API replacement plan
- **Do not push API keys** — they live in `.env` and Streamlit Cloud secrets, never committed

---

## Deployment

- **Local:** `streamlit run ui_v2.py --server.port 8503`
- **Streamlit Cloud:** Auto-deploys from `main` branch of `tegapeters/job-bot` on every push. Secrets (Supabase + Anthropic keys) are set in Streamlit Cloud dashboard — not in the repo.
- After pushing to `main`, the cloud app rebuilds in ~1–2 minutes.

---

## Backlog highlights (check BACKLOG.md for full detail)

| Item | Trigger |
|---|---|
| Replace LinkedIn scraper with Jsearch API | When current scraper breaks again |
| USAJobs API scraper | When API access restored |
| Supabase Auth + per-user data isolation | 5+ active beta users |
| Stripe payments | After auth is live |
| Daily scrape cron (cloud, not LaunchAgent) | After Streamlit Cloud deploy is stable |
| Target company watchlist (Greenhouse/Lever) | After auth is live |

---

## Session start checklist

1. Read this file
2. Check `git log --oneline -5` to see what changed recently
3. Ask the user what they want to work on
4. Never edit `ui.py`
