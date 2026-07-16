## 08 Job Pal

**Agentic AI job search engine — scrape, score, apply, track, network**

End-to-end pipeline that sources job listings in parallel across 5 boards, scores each one against an uploaded resume using Claude Sonnet, generates tailored cover letters for qualified matches, and surfaces everything in a branded Streamlit dashboard. Deployed live as a beta SaaS product with multi-user auth.

- **Parallel 5-source scraping:** LinkedIn, Indeed, Remotive, We Work Remotely, Jobicy — deduplicated across all sources, runs concurrently
- **Resume upload:** PDF, DOCX, or TXT — text extracted via PyMuPDF and python-docx; full resume sent via prompt caching for token efficiency
- **Claude Sonnet pipeline:** 1–10 resume-fit scoring (seniority, salary match, one-line reason) + role-specific 3-paragraph cover letters for 8+ matches
- **Gmail rejection scanning:** IMAP-based scan auto-runs on Applied page load — surfaces rejection emails, matches to applied jobs, one-click mark as rejected
- **Networking events:** 3-source event scraper (Meetup RSS, Luma city JSON, AllEvents.in) → 95+ events/city; Interested/Attending tracking with status persistence across re-scrapes
- **Application lifecycle:** Review Queue → Applied → Interviews → Rejected — full tracking with response rate and pipeline timing
- **Pipeline timing:** Per-stage duration tracking; company research via DuckDuckGo enriches job context at scoring time
- Supabase multi-user backend — each user's resume, scores, and pipeline are fully isolated
- MCP server exposes all tools so Claude can orchestrate the full workflow via natural language

**Stack:** Python · Claude Sonnet · Supabase · Streamlit · PyMuPDF · imaplib · ddgs · Playwright · MCP
**Live:** [jobpal.streamlit.app](https://jobpal.streamlit.app) | **[Overview →](https://job-pal-overview.vercel.app)** | **[View repo →](https://github.com/tegapeters/job-bot)**
