# Job Pal — Build Plan & ML Roadmap

**Last updated:** 2026-08-01  
**Owner:** Tega Eshareturi  
**Status:** Phase 2 unblocked (1,759 jobs ✅) — Phase 3 also unblocked (517 signals ✅)

---

## Where We Are Right Now

| Metric | Value |
|---|---|
| Jobs in DB | 1,759 ✅ Phase 2 trigger hit |
| Users | 1 (Tega) |
| Apply/skip signals | 517 ✅ Phase 3 trigger hit (500+) |
| Applied | 104 tracked applications |
| Interviews | 1 active |
| Active sources | 6: LinkedIn (80%), RemoteOK (10%), Adzuna (5%), USAJobs (4%), Remotive (2%), Jobicy (<1%) |
| Last pipeline run | 2026-08-01 |
| Scoring backend | `hybrid` (heuristic pre-filter + Claude Sonnet for 5+ band) |
| Cover letters | Claude Sonnet (8+ score only) |

---

## 3-Pass Scoring Architecture (Current)

```
Raw listing
    │
    ▼
Pass 1 — Heuristic pre-filter (agent.py · score_job_cheap)
    Free. Fast. Catches clear mismatches — wrong role, excluded keywords,
    too junior. Score <5 → dropped. No further processing.
    │
    ▼
Pass 2 — Embedding scorer (embedder.py · score_job_embed)
    TF-IDF cosine similarity (resume vs description) + skill overlap ratio
    + role title match + salary filter. No API calls. ~2ms per job.
    Score ≤4  → reject (no Sonnet call)
    Score 5–7 → uncertain band → escalate to Pass 3
    Score 8+  → confident match → skip score confirmation, go to cover letter
    │
    ▼
Pass 3 — Claude Sonnet (agent.py · score_job_claude)
    Only called for uncertain-band jobs (5–7 from embedding).
    Returns authoritative 1-10 score + reasoning.
    │
    ▼
Cover letter — Claude Sonnet (agent.py · generate_cover_letter)
    Generated for jobs with final score ≥8.
    Resume cached in system prompt via prompt caching (~70% token savings).
```

**Cost vs quality vs current hybrid:**
- Hybrid: all jobs scoring ≥5 on keyword heuristic → Claude (lots of false positives)
- Embed: only genuinely uncertain jobs → Claude (fewer calls, better calibrated)
- Estimated saving: 30-50% fewer Sonnet calls vs hybrid

---

## Data Milestones & Model Upgrades

### Phase 1 — TF-IDF Embedding ✅ Complete
**Trigger:** Default  
**What:** TF-IDF cosine similarity + feature engineering in `embedder.py`  
**Why:** Better than keyword heuristic with zero training data. Generalizes across professions.  
**Limitation:** TF-IDF is lexical, not semantic. "Software Engineer" and "SWE" score differently.

### Phase 2 — XGBoost on Sonnet Labels (NOW — trigger hit ✅)
**Trigger:** 1,000 jobs with Sonnet-confirmed scores in `job_applications` — **reached 2026-07-31**  
**What:** Train `XGBClassifier` on (job_features → sonnet_score) with Sonnet as ground truth  
**Features to use:**
- `_tfidf_sim` (already logged per job)
- `_skill_ratio` (already logged per job)
- title match score, salary match, source, seniority
- description length, job post age  

**What it buys:** Learns which features best predict Sonnet agreement, narrowing the uncertain band. Cuts Claude calls by another 20-30%.  
**File to create:** `ml/train_xgboost.py`, `ml/scorer_v2.pkl`

### Phase 3 — Personalized Ranking Model (~500 apply/skip signals)
**Trigger:** 500+ apply/skip events in `application_events` per user — **517 logged ✅ trigger hit**  
**What:** Logistic regression or lightweight gradient boost on (job_features → user_applied)  
**What it buys:** Personalization layer that learns *your* preferences, not just job fit.  
The `personalization_bonus` in `tracker.py` already does this with simple rules — this replaces it with a trained model.  
**File to create:** `ml/personalization_model.py`, per-user model artifacts

### Phase 4 — Fine-tuned Semantic Model (~5,000 signals)
**Trigger:** 5,000+ apply/skip signals across users  
**What:** Fine-tune DistilBERT or similar on (resume_embedding, job_embedding) → apply probability  
**What it buys:** True semantic understanding. "SWE" = "Software Engineer". Cross-domain transfer.  
**Note:** At this scale you probably have enough users to justify training costs. Consider sentence-transformers `all-MiniLM-L6-v2` as the base — 22MB, CPU-fast.

### Phase 5 — Production ML Pipeline (~50,000 signals)
**Trigger:** You have paying users and real scale  
**What:** Full ML platform — online learning, A/B tests between scoring models, feedback loops  
**What it buys:** Compound moat. The model improves as users use the product. Data flywheel.

---

## Current Grades (Honest)

| Area | Grade | Gap to A |
|---|---|---|
| Core AI scoring | A- | Embed mode + Sonnet is strong. XGBoost now unblocked (1k jobs) — will close to A. |
| UX | B+ | Mobile UX and non-tech user flow need work. |
| Stability | B+ | 3 low-severity bugs remaining. No data loss events. |
| Data quality | B+ | Descriptions enriched, salary persisting, real post dates. |
| Events | B | Meetup thin outside major cities. |
| Scraper coverage | B+ | 6 sources: LinkedIn, RemoteOK, Adzuna, USAJobs, Remotive, Jobicy. LinkedIn 80% — still a concentration risk. |
| Multi-user isolation | B | RLS live. Needs real multi-user load testing. |
| Personalization | B | 517 apply/skip signals logged. Phase 3 model trigger hit — XGBoost + personalization model both unblocked. |
| Non-tech user support | C+ | Architecture supports any profession — setup UX not tested. |
| SaaS readiness | C | Auth live. No Stripe, no rate limiting, no usage caps. |

**Overall: B (80/100)**

---

## SaaS Roadmap (what gets us to A across the board)

### Phase S1 — SaaS Foundation (2–3 weeks)
- [ ] Stripe integration — billing page, usage metering, free tier (100 jobs/mo), paid ($12/mo)
- [ ] Rate limiting — scrape runs capped per user per day (free: 1, paid: 5)
- [ ] Error handling — catch Supabase outages gracefully, no stack traces to users
- [ ] Automated daily scraping — cron job for all active users at 7am, with digest email

### Phase S2 — Scraper Resilience (1–2 weeks)
- [x] Add Adzuna scraper — live (50 jobs indexed)
- [x] Add USAJobs scraper — live (36 jobs indexed)
- [ ] Add Indeed scraper (largest volume, HTML scrape)
- [ ] Add Greenhouse/Lever (ATS boards, higher quality senior roles)
- [ ] LinkedIn fallback (Bing Jobs or SerpAPI if HTML structure breaks)
- [ ] Scraper health dashboard — alert if a source returns 0 results

### Phase S3 — User Growth (ongoing)
- [ ] Non-tech user beta — 5 users outside tech, fix every friction point
- [ ] Mobile UX — CSS tweaks for review queue on phone
- [ ] Apply/skip flywheel — encourage rating every job, add reason codes
- [ ] Weekly digest email — top 5 new matches, events, application status

---

## What A Looks Like

- [ ] 10 paying users at $12/mo
- [ ] 5+ job sources, no source >40% of volume
- [ ] Daily automation — zero manual triggers
- [ ] 3 non-tech users complete full flow without help
- [ ] Phase 2 XGBoost model trained and live

---

## How to Check Progress

```bash
# Jobs in DB
python -c "from tracker import get_all_applications; apps = get_all_applications(); print(len(apps), 'jobs')"

# Apply/skip signal count
python -c "
from tracker import get_client
sb = get_client()
res = sb.table('application_events').select('id', count='exact').execute()
print(res.count, 'events')
"

# Distribution of scored_by values
python -c "
from tracker import get_all_applications
from collections import Counter
apps = get_all_applications()
print(Counter(a.get('scored_by','?') for a in apps))
"
```

---

## Files & Ownership

| File | Purpose | Phase |
|---|---|---|
| `embedder.py` | TF-IDF scorer (Pass 2) | Phase 1 ✅ |
| `agent.py` | Heuristic (Pass 1) + Sonnet (Pass 3) + cover letters | All phases |
| `tracker.py` | Supabase reads/writes, personalization | All phases |
| `ml/train_xgboost.py` | Train XGBoost on Sonnet labels | Phase 2 |
| `ml/scorer_v2.pkl` | Trained XGBoost model artifact | Phase 2 |
| `ml/personalization_model.py` | Per-user preference model | Phase 3 |
| `BUILDPLAN.md` | This file — locked-in roadmap | Reference |
