"""
Job Pal — app-level defaults and CLI configuration.
Personal values (resume, applicant info) live in RESUME_TEXT and APPLICANT_INFO
and are only used for CLI scrape runs (main.py). All UI runs use per-user sessions.
"""

# ── Secrets helper (needed before RESUME_TEXT and APPLICANT_INFO) ──
import os
from dotenv import load_dotenv
load_dotenv()


def _secret(*names: str) -> str | None:
    """Read a secret from env vars (local) or st.secrets (Streamlit Cloud)."""
    for name in names:
        val = os.getenv(name)
        if val:
            return val
    try:
        import streamlit as st
        for name in names:
            val = st.secrets.get(name)
            if val:
                return val
    except Exception:
        pass
    return None


# ── Vertical ────────────────────────────────────────────────────────
# Which job market this run targets. Controls source selection (scrapers),
# the scoring rubric (agent.py), and UI labels.
#   "tech"     = the original tech / business job market (default)
#   "academic" = higher-ed faculty / adjunct / lecturer positions
# UI runs pass the per-user choice explicitly; this is the CLI/default.
VERTICAL = os.getenv("VERTICAL", "tech").strip().lower()

# ── Job Preferences ────────────────────────────────────────────────
TARGET_ROLES = [
    "Data Scientist",
    "Generative AI Engineer",
    "Senior Analytics Engineer",
    "Business Intelligence Engineer",
    "Data Engineer",
    "Senior Business Analyst",
    "Senior Systems Analyst",
    "Senior Data Analyst",
]

# Default academic search terms (disciplines + appointment types) used for
# CLI academic runs and as the UI Setup default when the vertical is academic.
ACADEMIC_ROLES = [
    "Adjunct Professor",
    "Lecturer",
    "Assistant Professor",
    "Visiting Professor",
    "Instructor",
]

# Words that flag a posting as a faculty/teaching role. Used to keep the
# role safety-net filter in scrape_all() from dropping legitimate academic
# titles that don't literally contain a target-role phrase.
ACADEMIC_TITLE_KEYWORDS = [
    "professor", "adjunct", "lecturer", "instructor", "faculty",
    "postdoc", "post-doctoral", "postdoctoral", "visiting scholar",
    "teaching", "clinical faculty", "tenure",
]

# Academic-mode exclusions layered on top of EXCLUDE_KEYWORDS. Faculty roles
# are often "entry level" in rank yet still relevant, so the tech exclusions
# ("junior", "entry level", "intern") must NOT apply in academic mode — this
# list replaces them with academic-appropriate noise filters instead.
ACADEMIC_EXCLUDE_KEYWORDS = [
    "work study", "student worker", "graduate assistantship",
    "resident assistant",
]

# Higher-ed job RSS feeds, grouped by source. Each scraper reads its own
# group. Feed URLs are kept here (not hardcoded in the scrapers) so a broken
# or changed endpoint is a one-line config fix, not a code change. Override
# per deployment with the ACADEMIC_FEEDS_* env vars (comma-separated URLs).
def _feed_list(env_name: str, default: list[str]) -> list[str]:
    raw = os.getenv(env_name, "")
    if raw.strip():
        return [u.strip() for u in raw.split(",") if u.strip()]
    return default

# HigherEdJobs publishes standard RSS 2.0 category feeds. catID values below
# map to faculty discipline categories on higheredjobs.com. Verify/adjust the
# active set for production via the ACADEMIC_FEEDS_HIGHEREDJOBS env var.
HIGHEREDJOBS_FEEDS = _feed_list("ACADEMIC_FEEDS_HIGHEREDJOBS", [
    "https://www.higheredjobs.com/rss/categoryFeed.cfm?catID=1",   # Faculty - Agriculture/Natural Resources
    "https://www.higheredjobs.com/rss/categoryFeed.cfm?catID=101", # Faculty - Science/Technology
    "https://www.higheredjobs.com/rss/categoryFeed.cfm?catID=140", # Faculty - Business
    "https://www.higheredjobs.com/rss/categoryFeed.cfm?catID=200", # Faculty - Liberal Arts/Humanities
])

# Inside Higher Ed Careers (Madgex platform) exposes a keyword-searchable RSS
# feed. {query} is URL-encoded and substituted per target role by the scraper.
INSIDEHIGHERED_FEED_TEMPLATE = os.getenv(
    "ACADEMIC_FEED_INSIDEHIGHERED",
    "https://careers.insidehighered.com/jobsrss/?keywords={query}",
)

LOCATIONS_REMOTE = ["Remote", "United States"]
LOCATIONS_HYBRID = ["Remote", "United States"]
LOCATIONS_ONSITE = [
    "Austin, TX",
    "Houston, TX",
    "Dallas, TX",
    "San Francisco, CA",
    "Seattle, WA",
    "New York, NY",
    "Chicago, IL",
    "Atlanta, GA",
    "Denver, CO",
    "Boston, MA",
    "Washington, DC",
    "Charlotte, NC",
    "Phoenix, AZ",
    "Nashville, TN",
    "Miami, FL",
]

REMOTE_OK = True
HYBRID_OK = True
ONSITE_OK = True  # US-wide for in-person

MIN_SALARY = 140_000  # USD

# Only truly universal exclusions — no profession-specific blocks.
# Individual users should filter irrelevant roles through their target_roles list,
# not through a global deny-list that breaks other professions.
EXCLUDE_KEYWORDS = [
    "junior", "entry level", "entry-level", "intern",
]

# ── Resume / Background ─────────────────────────────────────────────
_cli_email = _secret("CLI_EMAIL", "APPLICANT_EMAIL") or ""
_cli_phone = _secret("CLI_PHONE", "APPLICANT_PHONE") or ""

RESUME_TEXT = f"""
Tega Eshareturi — Houston, TX
{_cli_email} | {_cli_phone} | github.com/tegapeters/ai-portfolio
Salary Target: $140,000+ | Open to: Remote, Hybrid, Onsite (Houston/Austin/major US cities)

PROFESSIONAL SUMMARY
OCI Data Science Professional and AI automation lead with Oracle production experience across GenAI-enabled operational tooling, cloud service improvement, data integration, executive uptime reporting, and Python/SQL analytics. Known for translating operational data into leadership-ready insights and repeatable automation that improves incident response, service visibility, and engineering focus.

EXPERIENCE

Oracle — Senior NES Global Improvement Engineer (GI) | Jan 2021–Present | Austin, TX
- Lead AI and automation initiatives for Oracle Global Improvement, building GenAI-enabled deployment tools that improve ticket quality review, RCA consistency, and event-management triage
- Support AMER Large Scale Events (LSEs) and Cloud Event Response (CER); enforce incident-management discipline and deliver executive communications during critical cloud events
- Partner with NetSuite and OCI Generative AI teams to translate operational pain points into feature requirements, automation patterns, and service-improvement actions
- Own monthly NetSuite HUB data integration with 100% on-time delivery and high data accuracy
- Built Python-based uptime report automation reducing monthly reporting cycle from 3 days to 30 minutes; deployed to production 2026
- Use Oracle Analytics Cloud to surface operational trends and support data-informed decisions
- SME for Cloud Service Improvements: Python data engineering, SQL analysis, Agile/Scrum delivery

OCI/GenAI Services Automation Lead (2026–Present)
- Deployed Python-based CLI automation tools (Codex-integrated) for OCI/GenAI service ops, cutting manual reporting from 3 days to 30 minutes
- Lead OCI/GenAI service-operations automation to reduce manual process load, improve repeatability, and increase engineering bandwidth

OCI/GenAI Ticket Automation Tool
- Built GenAI-powered tool to automate ticket quality assurance, RCA support, and event-report management for Jira-based incidents
- Reduced manual review effort and accelerated critical-incident response by standardizing AI-assisted ticket review

On-Time High Quality
- Led collaborative release-management initiatives using Scrum and technical project-management practices to guide NetSuite internal and customer upgrades

Lockheed Martin — Government Financial Data Analyst | May 2019–Jan 2021 | Marietta, GA
- Led analytics for Aeronautics Sustainment Operations; BI and advanced data visualization
- Delivered BI training that modernized financial-system workflows and improved team adoption of reporting tools
- Drove cross-functional process integration supporting DCS/USG/FMS customers
- 2x NextGen Award: "Reshaping Our Financial Operations" (2020), "Evolving Our Culture" (2019)
- VP of Programs, Lockheed Martin Leadership Association — organized corporate events, mentorship, diversity programs
- President/Chair, NSBE Lockheed Martin Marietta Enterprise — professional development and academic support

BAE Systems — Business Systems Analyst | Jun 2018–Dec 2018 | Austin, TX
- Performed security and vulnerability assessments across 200+ systems, supporting DFARS compliance initiatives
- Automated onboarding and hardware-distribution reporting by consolidating data sources into repeatable workflows

EDUCATION
- M.S. Computer Information Systems, Data Science concentration — University of Houston Clear Lake (Jan 2025)
- B.B.A. Management Information Systems — Texas Southern University (Dec 2018)

CERTIFICATIONS
- Oracle Cloud Infrastructure Data Science Professional (2026)
- Oracle Cloud Infrastructure Generative AI Professional (2025)
- OCI AI Foundations Associate (2025)
- OCI Data Management Foundations Associate (2024)
- OCI Cloud Foundations Associate (2024)
- Professional Scrum Product Owner II & I (2023)
- Professional Scrum Master II & I (2023)
- EXIN Artificial Intelligence Essentials (2023)
- EXIN Cloud Computing Foundations (2022)
- IT Information Library (ITIL) Foundations (2022)

SKILLS
- Programming & ML: Python, SQL, Java, R, machine learning lifecycle, model artifacts, model deployment, PySpark
- Cloud & Data: Oracle Cloud Infrastructure, OCI Data Science, Oracle Analytics Cloud, NetSuite, Supabase, Data Flow
- AI/ML: GenAI, LLMs, OCI Generative AI, RAG concepts, model explainability, MLOps workflows, LLM implementation
- Reporting & BI: ETL data engineering, Power BI, Tableau, ELK, OpenSearch, uptime reporting, Jira analytics
- Platforms: Oracle NetSuite, SAP, Jira, Confluence, MS Office
- Methodologies: Agile, Scrum, ITIL
"""

# ── Applicant Info (used for form auto-fill) ────────────────────────
RESUME_PATH = "/Users/techturi/Documents/Resume/TEGA_ESHARETURI_RESUME_2026.pdf"

APPLICANT_INFO = {
    "first_name":       "Tega",
    "last_name":        "Eshareturi",
    "email":            _secret("CLI_EMAIL", "APPLICANT_EMAIL") or "",
    "phone":            _secret("CLI_PHONE", "APPLICANT_PHONE") or "",
    "linkedin":         _secret("CLI_LINKEDIN") or "https://www.linkedin.com/in/tega-p-eshareturi-014002142/",
    "current_company":  "Oracle NetSuite",
    "location":         "Houston, TX",
    "work_auth":        "Yes",
    "requires_sponsor": "No",
}

# ── Supabase ────────────────────────────────────────────────────────
SUPABASE_URL = _secret("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = _secret("SUPABASE_ANON_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY", "SUPABASE_KEY")

# ── ShutterMuse DB — networking events ─────────────────────────────
EVENTS_SUPABASE_URL = _secret("EVENTS_SUPABASE_URL")
EVENTS_SUPABASE_KEY = _secret("EVENTS_SUPABASE_KEY")

# ── Eventbrite ─────────────────────────────────────────────────────
EVENTBRITE_API_KEY = _secret("EVENTBRITE_API_KEY")

# ── Anthropic ───────────────────────────────────────────────────────
ANTHROPIC_API_KEY = _secret("ANTHROPIC_API_KEY")

# ── Adzuna ──────────────────────────────────────────────────────────
# Free tier at https://developer.adzuna.com (250 req/day)
ADZUNA_APP_ID  = _secret("ADZUNA_APP_ID")
ADZUNA_APP_KEY = _secret("ADZUNA_APP_KEY")

# ── USAJobs ─────────────────────────────────────────────────────────
# Free key at https://developer.usajobs.gov/APIRequest/Index
USAJOBS_API_KEY = _secret("USAJOBS_API_KEY")
USAJOBS_EMAIL   = _secret("USAJOBS_EMAIL")

# ── SerpAPI (Google Jobs) ────────────────────────────────────────────
# Free tier: 100 searches/month — https://serpapi.com
SERPAPI_KEY = _secret("SERPAPI_KEY")

# ── Handshake ────────────────────────────────────────────────────────
# Opt-in: paste your token from browser DevTools → Application → Cookies
# (remember_user_token on app.joinhandshake.com) into .env
HANDSHAKE_TOKEN = _secret("HANDSHAKE_TOKEN")

# ── Scoring backend strategy ────────────────────────────────────────
# claude = current behavior (best quality, highest cost)
# cheap  = heuristic-only local scoring (lowest cost)
# hybrid = cheap pre-filter + Claude for stronger candidates
SCORING_BACKEND = os.getenv("SCORING_BACKEND", "claude").strip().lower()
HYBRID_CLAUDE_MIN_SCORE = int(os.getenv("HYBRID_CLAUDE_MIN_SCORE", "6"))
ENABLE_COVER_LETTERS = os.getenv("ENABLE_COVER_LETTERS", "1").strip().lower() in {"1", "true", "yes", "y"}

# ── Auto-apply threshold ────────────────────────────────────────────
# Jobs scoring >= this are queued for review; set to 11 to disable auto-apply
AUTO_APPLY_MIN_SCORE = 11   # 11 = review-first mode (recommended)
REVIEW_MIN_SCORE = 7        # Surface jobs scoring 7+ in review queue
COVER_LETTER_MIN_SCORE = 8  # Only generate cover letters for 8+ (strong leads)
