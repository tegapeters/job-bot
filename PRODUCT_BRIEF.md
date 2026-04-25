# Job Bot → SaaS Product Brief
**For planning session with Claude**

---

## What exists today (the foundation)

A working personal tool built by Tega Eshareturi:

- **Scrapers** — LinkedIn (session-cookie auth), Indeed, Remotive
- **AI scoring** — Claude Haiku scores each job 1–10 against a resume with seniority, salary match, and a reason
- **AI cover letters** — Claude Sonnet generates role-specific 3-paragraph cover letters for 7+ scored jobs
- **Deduplication** — seen job IDs are cached in Supabase so nothing is scored twice (no wasted API spend)
- **Tracking** — Supabase table with full lifecycle: `new → reviewing → applied → interview → rejected`
- **Streamlit dashboard** — 4 pages: Dashboard, Review Queue, All Applications, Run Pipeline
- **MCP server** — Claude can orchestrate the full pipeline via natural language
- **LaunchAgent** — scheduled daily scraping on macOS

The pipeline works end-to-end. This brief is about what it would take to turn it into a product other people pay for.

---

## The problem it solves (user pain)

Job searching is broken for mid-to-senior tech professionals:

1. **Volume is overwhelming** — hundreds of postings per search, most irrelevant
2. **Screening is manual** — copy/pasting job descriptions to evaluate fit takes 20+ min per job
3. **Cover letters are generic** — most people send the same letter or skip it entirely
4. **Tracking is spreadsheets** — no one actually knows what they applied to, when, or what happened
5. **Premium job boards are expensive** — LinkedIn Premium, Ladders, etc. charge $30–60/month for search, not intelligence

Job Bot collapses steps 1–4 into one automated pipeline. The insight is that **AI fit scoring + auto cover letters** is the actual product — scraping is just the delivery mechanism.

---

## Target users

**Primary:** Mid-to-senior tech professionals actively job searching
- Business Analysts, Data Engineers, PMs, AI/ML Engineers
- 5–15 years experience, $100k–$200k target salary
- Sending 5–20 applications per week
- Already know how to use LinkedIn, not intimidated by tech

**Secondary:** Recruiters / outplacement firms managing candidates at scale
- Could white-label or use an API to score candidates against roles

**Not:** Entry-level, non-tech, or passive job seekers (too low urgency to pay)

---

## Core value proposition

> Upload your resume. Tell us what you're looking for.
> We scrape 500+ jobs a day, score every one against your background,
> write tailored cover letters for the best matches, and put them in your inbox.
> You review, click apply.

**Time saved per week:** ~8–12 hours of manual screening and writing
**Unfair advantage:** Claude AI fit scoring is meaningfully better than keyword matching

---

## Product scope — three versions to plan

### V1 — Waitlist / Indie (1–3 months)
Turn the existing tool into a hosted, multi-user version with a simple onboarding flow.

**Must haves:**
- [ ] User auth (email/password or Google OAuth)
- [ ] Resume upload + parsing (extract structured data from PDF)
- [ ] Job preferences form (roles, locations, salary floor, remote/hybrid/onsite, exclude keywords)
- [ ] Per-user scoring — each user's resume scored against each job
- [ ] Daily email digest (like the IG daily brief, but for jobs) — top 10 matches delivered to inbox
- [ ] Web dashboard — same 4 views as Streamlit but in Next.js
- [ ] Stripe subscription ($15–25/month)

**Cut from V1:**
- Auto-apply (too risky to ship before trust is established)
- LinkedIn scraping (ToS risk at scale — replace with job board APIs)
- Mobile app

**Stack for V1:** Next.js + Supabase (already known) + Anthropic API + Stripe + Resend (email)

---

### V2 — Growth (3–9 months)
**Add the features that drive retention and word-of-mouth:**

- [ ] Browser extension — one-click "score this job" from any job board
- [ ] Application tracker with status email reminders ("You applied 2 weeks ago — any update?")
- [ ] Interview prep — Claude generates likely interview questions based on the job description
- [ ] LinkedIn profile gap analysis — "Your profile is missing X that this job requires"
- [ ] Team plan — for outplacement firms or bootcamp cohorts ($99/month for 10 seats)
- [ ] Job board API integrations (Adzuna, The Muse, Greenhouse, Lever webhooks)

---

### V3 — Platform (9–18 months)
- [ ] Employer side — post a role, get AI-ranked applicant list (two-sided marketplace)
- [ ] Anonymous salary data from users who got offers (LinkedIn Salary competitor)
- [ ] White-label API for staffing agencies
- [ ] Resume rewrite suggestions per role ("Add 'ETL pipeline' to your experience section — 40 jobs in your queue require it")

---

## The hardest problems to solve

### 1. LinkedIn scraping at scale
The current tool uses session cookies from Tega's personal account. At 1,000 users this gets accounts banned.

**Options to discuss:**
- Pivot to official job board APIs (Adzuna is free, Indeed Publisher API, Greenhouse/Lever webhooks)
- Partner with a job data provider (Jobspikr, Brightdata, Theirstack)
- Build a "paste job URL" flow as a fallback — user finds the job, we score and track it

### 2. Resume parsing
Extracting structured data from a PDF resume is harder than it looks. Need to get: work history, skills, titles, years of experience, salary signals.

**Options:**
- Claude reads the raw PDF text (simplest)
- Affinda or Sovren API (purpose-built resume parsers)
- Ask users to fill in a structured form instead of parsing (slower onboarding but cleaner data)

### 3. Per-user scoring cost
At scale, running Haiku on 500 jobs × 1,000 users = 500,000 API calls/day.
Current Haiku cost: ~$0.0004 per scoring call = ~$200/day at that scale.

**Options:**
- Score jobs once globally, then re-rank per user (cheaper but less accurate)
- Cache job descriptions + embeddings, use vector similarity for pre-filter, only call Haiku on top 50
- Fine-tune a small model on scored data to replace Haiku at scale

### 4. Trust / apply button
Auto-applying without user review creates spam and reputational risk for job seekers.
The right model is probably: AI does the work, human clicks send.

---

## Business model

| Tier | Price | What they get |
|------|-------|---------------|
| Free | $0 | 5 job scores/day, no cover letters |
| Pro | $19/month | Unlimited scoring, cover letters, daily digest, dashboard |
| Power | $39/month | Everything + browser extension, interview prep, priority scraping |
| Team | $99/month | 10 seats, shared job pool, team admin |

**Revenue targets:**
- 100 Pro users = $1,900 MRR (break-even on API costs + hosting)
- 500 Pro users = $9,500 MRR (viable indie business)
- 2,000 Pro users = $38,000 MRR (acqui-hire or Series A territory)

---

## Competitive landscape

| Product | What they do | Gap |
|---------|-------------|-----|
| LinkedIn Premium | Better search filters | No AI fit scoring, no cover letters |
| Teal | Job tracker + resume builder | No scraping, no AI scoring |
| Jobscan | ATS keyword matching | Passive, no automation |
| LazyApply / Simplify | Auto-apply bots | Spray-and-pray, no quality scoring |
| Pave / Levels.fyi | Salary data | No job matching |

**Job Bot's wedge:** The only product that combines real-time job scraping + resume-specific AI scoring + auto-generated tailored cover letters in one loop.

---

## Questions to answer in planning session

Bring this document and ask Claude:

1. **Architecture:** Design the multi-user backend. How do we isolate per-user job queues in Supabase? What's the schema?

2. **Scraping strategy:** Given LinkedIn ToS risk, what's the safest combination of job data sources for a V1 with 100 users?

3. **Scoring efficiency:** Design a hybrid scoring system — embeddings for pre-filter, Haiku for final scoring — that cuts API costs by 80% without hurting quality.

4. **Onboarding flow:** Design the resume upload → preferences → first results flow. What's the minimum data needed to produce a useful first score?

5. **Pricing validation:** How do we test willingness to pay before building? (Landing page, waitlist, manual concierge tier)

6. **Build vs buy:** Which pieces should we build vs use existing APIs for (resume parsing, job data, email delivery, auth)?

7. **Roadmap:** Given a solo founder with ~10 hrs/week, what's the realistic V1 scope and timeline?

---

## Existing assets to leverage

- Working pipeline code (Python) — scrapers, scorer, cover letter generator, Supabase schema
- Streamlit dashboard (can be replaced with Next.js)
- MCP server (reusable as internal API)
- techturi.org (landing page / brand)
- Supabase project already set up
- Anthropic API key with working prompts
- 180+ real scored jobs as test data (from today's run)

---

## How to use this brief

Paste this entire document into a new Claude conversation and say:

> "I'm planning to turn this personal job search automation tool into a SaaS product.
> I have a working V0. Help me plan V1 architecture, the build roadmap, and the
> go-to-market strategy. Start with the architecture question."

Then work through the **Questions to answer** section one at a time.
