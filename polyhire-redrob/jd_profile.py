"""Structured representation of job_description.md for the Senior AI Engineer — Founding Team role."""

MUST_HAVE_CAPABILITY_STATEMENTS = [
    "built and operated a production embeddings-based retrieval system used by real users",
    "operated a vector database or hybrid search infrastructure in production at scale",
    "wrote strong, well-structured production Python code",
    "designed and ran rigorous offline and online evaluation frameworks for a ranking system using NDCG, MRR, MAP, or A/B testing",
]

NICE_TO_HAVE_TERMS = [
    "LoRA", "QLoRA", "PEFT", "fine-tuning", "learning to rank", "XGBoost ranking",
    "recruiting platform", "HR tech", "marketplace", "distributed systems", "inference optimization",
    "open source",
]

ML_AI_TITLE_FAMILY = [
    r"machine learning engineer", r"ml engineer", r"applied scientist", r"research engineer",
    r"ai engineer", r"data scientist", r"search engineer", r"ranking engineer",
    r"recommendation", r"nlp engineer", r"data engineer", r"backend engineer",
    r"software engineer", r"platform engineer",
]

CONSULTING_FIRMS = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini",
    "tata consultancy services", "hcl", "tech mahindra",
}

LEADERSHIP_TITLES = [r"architect", r"tech lead", r"engineering manager", r"director", r"head of"]

PREFERRED_LOCATIONS_TIER1 = {"pune", "noida"}
ACCEPTABLE_LOCATIONS = {
    "hyderabad", "mumbai", "delhi", "gurgaon", "gurugram", "chennai", "bangalore", "bengaluru",
}

EXPERIENCE_BAND = (5, 9)

WEIGHTS = dict(
    skill_match=0.30,
    role_relevance=0.30,
    experience_fit=0.15,
    location_logistics=0.10,
    negative_filter_cap=0.25,
)

NEGATIVE_FILTER_PENALTIES = dict(
    pure_research_career=0.12,
    recent_llm_only_experience=0.10,
    leadership_drift=0.08,
    pure_consulting_career=0.10,
    no_nlp_ir_exposure=0.07,
    no_external_validation=0.03,
)

REFERENCE_DATE = "2026-06-30"
