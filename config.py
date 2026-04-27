"""
Job Bot Configuration — Tega Eshareturi
"""

# ── Job Preferences ────────────────────────────────────────────────
TARGET_ROLES = [
    "Senior Business Analyst",
    "Business Systems Analyst",
    "Senior Business Systems Analyst",
    "Technical Project Manager",
    "Senior Technical Program Manager",
    "Senior Data Engineer",
    "Data Engineer",
    "AI Engineer",
    "Senior AI Engineer",
    "Machine Learning Engineer",
    "Senior ML Engineer",
    "GenAI Engineer",
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
]

# ── Resume / Background ─────────────────────────────────────────────
RESUME_TEXT = """
Tega Eshareturi — Houston, TX
Tegapeters11@gmail.com | 832.660.1325 | github.com/tegapeters/ai-portfolio
Salary Target: $140,000+ | Open to: Remote, Hybrid, Onsite (Houston/Austin/major US cities)

EXPERIENCE

Oracle — Senior NES Global Improvement Engineer (GI) | Jan 2021–Present | Austin, TX
- Spearhead AI and automation initiatives for Global Improvement; GenAI-powered deployment tools for ticket QA, RCA, and event management
- Lead execution support for AMER Large Scale Events (LSEs) and Cloud Event Response (CER); coordinate Cloud Service Improvement efforts
- Deliver executive-level communications during critical incidents; enforce incident management discipline
- Facilitate cross-functional collaboration between NetSuite and OCI Generative AI teams for new feature development
- Own monthly NetSuite HUB data integration process — 100% on-time delivery and high data accuracy
- Generate monthly uptime reports for executive leadership across Jira, internal HUB systems, and customer datasets
- Leveraged Oracle Analytics Cloud for data-informed decision making and service enhancements
- SME for Cloud Service Improvements: Python-based data engineering, SQL analysis, Agile/Scrum delivery
- Led Release Management team initiatives using Scrum for NetSuite internal and customer upgrades

OCI/GenAI Services Automation Lead (2026–Present)
- Spearheading automation initiatives to optimize OCI/GenAI service operations, eliminating manual processes

OCI/GenAI Ticket Automation Tool
- Developed GenAI-powered tool to automate QA, RCA, and ticket management for Jira incidents
- Achieved significant reductions in manual workload; accelerated response to critical incidents

Lockheed Martin — Government Financial Data Analyst | May 2019–Jan 2021 | Marietta, GA
- Led analytics for Aeronautics Sustainment Operations; BI and advanced data visualization
- Conducted BI training to modernize financial system processes
- Drove cross-functional process integration supporting DCS/USG/FMS customers
- 2x NextGen Award: "Reshaping Our Financial Operations" (2020), "Evolving Our Culture" (2019)
- VP of Programs, Lockheed Martin Leadership Association — organized corporate events, mentorship, diversity programs
- President/Chair, NSBE Lockheed Martin Marietta Enterprise — professional development and academic support

BAE Systems — Business Systems Analyst | Jun 2018–Dec 2018 | Austin, TX
- Ran security and vulnerability assessments on 200+ systems under DFARS initiatives
- Automated onboarding and hardware distribution reporting

EDUCATION
- M.S. Computer Information Systems, Data Science concentration — University of Houston Clear Lake (Jan 2025)
- B.B.A. Management Information Systems — Texas Southern University (Dec 2018)

CERTIFICATIONS
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
- AI/ML: GenAI, LLMs, OCI Generative AI, supervised/unsupervised learning, NLP, LLM implementation
- Languages: Python, SQL, R, Java
- Cloud: Oracle Cloud Infrastructure (OCI), Oracle Analytics Cloud, Supabase
- Data: ETL data engineering, Power BI, Tableau, ELK, OpenSearch, NetSuite
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

# Support both Next.js-style and plain secret names for Streamlit Cloud
SUPABASE_URL = (
    os.getenv("SUPABASE_URL") or
    os.getenv("NEXT_PUBLIC_SUPABASE_URL")
)
SUPABASE_KEY = (
    os.getenv("SUPABASE_ANON_KEY") or
    os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
)

# ── Anthropic ───────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ── Auto-apply threshold ────────────────────────────────────────────
# Jobs scoring >= this are queued for review; set to 11 to disable auto-apply
AUTO_APPLY_MIN_SCORE = 11   # 11 = review-first mode (recommended)
REVIEW_MIN_SCORE = 7        # Only surface jobs scoring 7+
