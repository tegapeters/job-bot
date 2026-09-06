---
name: academic-vertical
description: Work on Job Pal's higher-ed faculty/adjunct matching vertical — run it locally, verify or fix the academic job feeds (HigherEdJobs, Inside Higher Ed), tune the academic scoring rubric, or extend the academic scrapers. Use whenever the task involves faculty/adjunct/professor/lecturer job matching, the VERTICAL="academic" mode, empty/failing academic feeds, or the files agent.py academic templates, scrapers/higheredjobs.py, scrapers/insidehighered.py, scrapers/_academic.py.
---

# Academic (faculty / adjunct) vertical

Job Pal has an **opt-in `academic` vertical** alongside the default `tech` one. Same
pipeline spine (scrape → Claude score → persist → triage); different sources, scoring
rubric, and labels. Phase 1 = candidate side only (no employer accounts / marketplace).

## How the vertical flag flows

`vertical` ("tech" | "academic") is threaded explicitly, defaulting to "tech" everywhere
so the tech path is untouched:

- **UI** (`ui_v2.py`): Setup toggle → `st.session_state["vertical"]` + `["schedule_pref"]`,
  persisted in the URL (`?vertical`, `?sched`) AND best-effort to Supabase. Passed into
  `scrape_all(..., vertical=)` and `process_jobs(..., vertical=, schedule_pref=)`.
- **Sources** (`scrapers/__init__.py`): `scrape_all(vertical="academic")` runs ONLY the
  academic source group (HigherEdJobs, Inside Higher Ed) and a faculty-aware role filter.
- **Scoring** (`agent.py`): academic templates (`SCORE_SYSTEM_TEMPLATE_ACADEMIC`,
  `COVER_LETTER_SYSTEM_TEMPLATE_ACADEMIC`) + `_parse_score_response(text, vertical)`
  which returns `rank` (stored in the existing `seniority` column) and `degree_match`
  instead of seniority/salary. Academic mode always uses Claude. Rubric scores on:
  degree-in-field gate, discipline/teaching fit, rank, and **teaching-schedule
  availability** (evening/night, early-morning, weekend, online — from `schedule_pref`).
- **Scrapers** (`scrapers/higheredjobs.py`, `scrapers/insidehighered.py`): thin
  `feedparser` RSS readers over `scrapers/_academic.py` helpers (rank + appointment_type
  extraction, HTML strip, institution→`company`).

No `job_applications` migration is needed (rank rides in `seniority`). The optional
`user_sessions.vertical` / `.schedule_pref` columns only add cross-device persistence:
```sql
alter table user_sessions add column if not exists vertical text default 'tech';
alter table user_sessions add column if not exists schedule_pref text;
```

## Feed URLs (the #1 thing that breaks)

Feed URLs live in `config.py` and are env-overridable — a bad endpoint is a config fix,
not a code change. If a live run shows `→ HigherEdJobs: 0 jobs`, the URL or its category
IDs are wrong.

**HigherEdJobs** — real RSS endpoint is `https://www.higheredjobs.com/search/rss.cfm?JobCat=<id>`
(NOT `/rss/categoryFeed.cfm?catID=`). Verified JobCat IDs relevant to a Data Science / CS
teacher: **102** Computer Science, **144** Information Systems & Technology, **242**
Computer and Information Technology, **74** Other Technical and Career Faculty, **68**
Higher Education, **63** Curriculum and Instruction. Full list: https://www.higheredjobs.com/rss/

**Inside Higher Ed** — keyword-searchable RSS template in `INSIDEHIGHERED_FEED_TEMPLATE`
(`{query}` is URL-encoded per role). This endpoint is UNVERIFIED — treat HigherEdJobs as
the reliable source and confirm IHE against a live run; if it 0s, find the correct
Madgex RSS path or replace it.

Override without touching code:
```bash
export ACADEMIC_FEEDS_HIGHEREDJOBS="https://www.higheredjobs.com/search/rss.cfm?JobCat=102,https://www.higheredjobs.com/search/rss.cfm?JobCat=144"
export ACADEMIC_FEED_INSIDEHIGHERED="https://careers.insidehighered.com/jobsrss/?keywords={query}"
```

## Run & verify locally (the key workflow)

```bash
# 1. Quick feed check — does the corrected feed actually return items?
python - <<'PY'
import feedparser
ua = "Mozilla/5.0 (compatible; JobPalBot/1.0)"
for cid in (102, 144, 242, 74):
    u = f"https://www.higheredjobs.com/search/rss.cfm?JobCat={cid}"
    f = feedparser.parse(u, agent=ua)
    print(cid, "->", len(f.entries), "entries", "| first:", (f.entries[0].title if f.entries else "—"))
PY

# 2. Full scraper in academic mode
python - <<'PY'
from scrapers import scrape_all
jobs = scrape_all(target_roles=["Adjunct Professor","Lecturer","Instructor"], vertical="academic")
print(len(jobs), "jobs"); [print(j["source"], "|", j["rank"], "|", j["title"], "@", j["company"]) for j in jobs[:10]]
PY

# 3. Score one posting against a resume (needs ANTHROPIC_API_KEY in .env)
python - <<'PY'
from agent import score_job
job = {"title":"Adjunct Instructor, Data Science","company":"Houston CC","location":"Houston, TX",
       "description":"<paste a real posting>","rank":"Adjunct","appointment_type":"Adjunct"}
r = score_job(job, resume_text=open("resume.txt").read(), vertical="academic",
              schedule_pref="Evening / night classes, Weekend classes")
print(r["score"], "|", r["seniority"], "|", r["score_reason"])
PY

# 4. Full app
streamlit run ui_v2.py --server.port 8503
#   Setup → toggle "🎓 Faculty & Adjunct" → set teachable roles
#   (Adjunct Professor Data Science, Lecturer Computer Science, Instructor Statistics)
#   → pick schedule → Save → Run Pipeline. Watch terminal for "→ HigherEdJobs: N jobs".
```

## Diagnosing an empty run

1. **`→ HigherEdJobs: 0 jobs`** → feed URL/IDs wrong, or the site blocked the request.
   Run step 1 above. If entries print there but scrape_all gives 0, the `matches_roles`
   filter (`scrapers/_academic.py`) or `is_excluded` is dropping them — check the titles.
2. **feedparser returns 0 with `bozo`/HTTP error** → try a different User-Agent, or the
   endpoint changed; find the current one at https://www.higheredjobs.com/rss/.
3. **"no NEW jobs to score"** (but jobs scraped) → they're already in the DB from a prior
   run; that's dedup working, not a bug.
4. Never disable a test to get CI green. `config.py`'s `EXCLUDE_KEYWORDS` must stay
   profession-neutral (CI check 3 enforces this) — academic noise terms live in the
   separate `ACADEMIC_EXCLUDE_TERMS`.

## Constraints

- Don't pollute the global `EXCLUDE_KEYWORDS` with academic terms (use `ACADEMIC_EXCLUDE_TERMS`).
- Keep every `vertical` parameter defaulting to `"tech"` so the tech path never changes.
- Deploy: merge to `main` → Streamlit Cloud rebuilds `jobpal.streamlit.app` in ~1–2 min.
