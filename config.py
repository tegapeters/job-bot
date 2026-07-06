"""
Job Bot Configuration — Tega Eshareturi
"""

# ── Job Preferences ────────────────────────────────────────────────
TARGET_ROLES = [
    "Data Engineer",
    "Senior Data Engineer",
    "AI Engineer",
    "GenAI Engineer",
    "Machine Learning Engineer",
    "Analytics Engineer",
    "Senior Analytics Engineer",
    "Senior Data Analyst",
    "Senior Business Intelligence Engineer",
]

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

EXCLUDE_KEYWORDS = [
    "defense", "military", "clearance", "secret clearance", "top secret",
    "government contractor", "dod", "department of defense",
    "junior", "entry level", "entry-level", "associate", "intern",
    # Non-tech PM / construction / civil / physical infrastructure
    "construction", "mechanical", "electrical", "civil", "structural",
    "roofing", "mep", "hvac", "wastewater", "solid waste", "aviation",
    "power generation", "utility locating", "geospatial", "ambient air",
    "data center build", "workspace renovation", "traveling senior",
    # Hardware / embedded / systems (not data/AI)
    "embedded", "firmware", "robotics", "radar", "silicon",
    "compiler", "server manageability", "fpga", "rtos", "kernel",
    "data center site", "data center engineer", "network device",
    "wearable", "hpc support", "devops engineer",
]

# ── Resume / Background ─────────────────────────────────────────────
RESUME_TEXT = """
Tega Eshareturi — Houston, TX
Tegapeters11@gmail.com | 832.660.1325 | github.com/tegapeters/ai-portfolio
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
    "email":            "tegapeters11@gmail.com",          # ← your email
    "phone":            "832-660-1325",              # ← e.g. 713-555-1234
    "linkedin":         "https://www.linkedin.com/in/tega-p-eshareturi-014002142/",  # ← your LinkedIn URL
    "current_company":  "Oracle NetSuite",
    "location":         "Houston, TX",
    "work_auth":        "Yes",                        # authorized to work in US
    "requires_sponsor": "No",
}

# ── Supabase ────────────────────────────────────────────────────────
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


SUPABASE_URL = _secret("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = _secret("SUPABASE_ANON_KEY", "NEXT_PUBLIC_SUPABASE_ANON_KEY", "SUPABASE_KEY")

# ── ShutterMuse DB — networking events ─────────────────────────────
EVENTS_SUPABASE_URL = _secret("EVENTS_SUPABASE_URL")
EVENTS_SUPABASE_KEY = _secret("EVENTS_SUPABASE_KEY")

# ── Anthropic ───────────────────────────────────────────────────────
ANTHROPIC_API_KEY = _secret("ANTHROPIC_API_KEY")

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
