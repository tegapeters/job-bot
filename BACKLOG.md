# Job Pal — Backlog

Items below are scoped, ready to build, and deprioritized until revenue justifies the cost or complexity.

---

## Scraper Upgrades

### LinkedIn → Jsearch API replacement
- **Why:** LinkedIn session-cookie scraper breaks frequently as LinkedIn rotates anti-scrape measures. Jsearch (RapidAPI) provides real LinkedIn + Indeed results via a stable API.
- **Cost:** ~$10/mo (RapidAPI basic tier)
- **Effort:** 1–2 hours — swap `scrapers/linkedin.py` for a Jsearch API client
- **Trigger:** When LinkedIn scraper breaks again OR first paying client

### USAJobs API
- **Why:** Federal analytics/data roles — strong match for profiles with defense/gov background (BAE Systems, Lockheed). Well-structured data, updated daily.
- **Cost:** Free (API key required at usajobs.gov/Help/APIaccess)
- **Effort:** 2–3 hours
- **Blocker:** API access was unavailable at time of writing — check back. Endpoint: data.usajobs.gov/api/Search
- **Trigger:** When API access is restored

### Greenhouse / Lever ATS scraper
- **Why:** Many top tech companies (Stripe, Notion, Linear, etc.) post exclusively on their ATS. Greenhouse has a public job board API per-company.
- **Cost:** Free
- **Effort:** 3–4 hours — build a company watchlist + poll each ATS API
- **Trigger:** When user can specify target companies in Setup page

---

## Product

### Auth + per-user data isolation
- Supabase Auth (email + Google OAuth)
- `user_id` column on `job_applications` + Row Level Security
- Resume stored per-user in Supabase Storage (not session state)
- **Trigger:** 5+ active beta users confirmed using weekly

### Stripe payments
- Free tier: 1 run/week, 25 jobs, 3 cover letters
- Seeker ($12/mo): daily runs, 100 jobs, 15 cover letters
- Pro ($25/mo): unlimited runs, 200 jobs, unlimited cover letters
- **Trigger:** After auth is live and demand is validated

### Target company watchlist
- User specifies companies (e.g. Zillow, Stripe, Anthropic)
- Daily check against Greenhouse/Lever ATS APIs
- Instant notification when a matching role posts
- **Trigger:** After auth is live

---

## Infrastructure

### Daily scrape cron (cloud)
- Replace macOS LaunchAgent with a scheduled Supabase Edge Function or GitHub Actions cron
- Scrape runs automatically, results waiting in dashboard each morning
- **Trigger:** After deploy to Streamlit Cloud is stable
