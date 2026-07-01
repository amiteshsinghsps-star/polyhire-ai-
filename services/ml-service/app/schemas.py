"""
Pydantic models mirroring packages/shared-types — the wire contract
between this Python service, the Node gateway, and the React frontend.

Kept in sync manually; the TS package is the source of truth for field
names so JSON payloads round-trip identically across the stack.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


Seniority = Literal["junior", "mid", "senior", "staff", "principal"]


class StructuredJD(BaseModel):
    role_title: str
    seniority: Seniority = "mid"
    must_have_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    domain: str = ""
    min_years_experience: float = 0.0
    soft_requirements: list[str] = Field(default_factory=list)
    implicit_requirements: list[str] = Field(default_factory=list)


class BiasFlag(BaseModel):
    sentence: str
    confidence: float
    category: Optional[str] = None


class CandidateMetadata(BaseModel):
    years_experience: float = 0.0
    num_jobs: int = 0
    avg_tenure_months: float = 0.0
    title_jump_velocity: float = 0.0
    claimed_skill_count: int = 0
    profile_completeness: float = 1.0
    last_activity_days_ago: int = 0
    career_trajectory_slope: float = 0.0
    engagement_score: float = 0.5


class EducationEntry(BaseModel):
    institution: Optional[str] = None
    college: Optional[str] = None
    school: Optional[str] = None
    degree: Optional[str] = None


class CandidateProfile(BaseModel):
    id: str
    name: Optional[str] = None
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    current_title: Optional[str] = None
    profile_text: str = ""
    metadata: CandidateMetadata = Field(default_factory=CandidateMetadata)
    trust_score: Optional[float] = None
    city: Optional[str] = None
    location: Optional[str] = None
    institution: Optional[str] = None
    degree: Optional[str] = None
    education: list[EducationEntry] = Field(default_factory=list)


# Fusion ranker features (order MUST match FUSION_FEATURES in shared-types)
FUSION_FEATURES: list[str] = [
    "embedding_similarity",
    "rerank_score",
    "years_experience_match",
    "skill_overlap_ratio",
    "recency_of_activity",
    "career_trajectory_slope",
    "engagement_score",
    "trust_score",
    "institution_tier_score",
    "informal_sector_score",
]


class BharatContextSummary(BaseModel):
    total_candidates: int = 0
    tier_1_count: int = 0
    tier_2_count: int = 0
    tier_3_count: int = 0
    tier_adjusted_count: int = 0
    nirf_matched_count: int = 0
    code_switch_detected_count: int = 0
    informal_sector_count: int = 0
    avg_engagement_delta: float = 0.0
    processing_ms: float = 0.0


class CandidateBharatAdjustment(BaseModel):
    tier_adjusted: bool = False
    bharat_tier: str = "tier_2"
    engagement_delta: float = 0.0
    institution_score: float = 0.5
    institution_matched: bool = False
    code_switch_detected: bool = False
    skills_added_by_bil3: list[str] = Field(default_factory=list)
    informal_sector_score: float = 0.0
    informal_explanation: str = ""
    skills_added_by_bil4: list[str] = Field(default_factory=list)


class RankedCandidate(BaseModel):
    rank: int
    candidate_id: str
    name: Optional[str] = None
    score: float
    explanation: str = ""
    trust_score: float = 1.0
    feature_contributions: Optional[dict[str, float]] = None
    skills: list[str] = Field(default_factory=list)
    current_title: Optional[str] = None
    bharat_adjustment: Optional[CandidateBharatAdjustment] = None


class SkillGapReport(BaseModel):
    candidate_id: str
    name: Optional[str] = None
    report: str
    missing_skills: list[str] = Field(default_factory=list)


class GalaxyNode(BaseModel):
    candidateId: str
    x: float
    y: float
    z: float
    rank: int
    score: float
    cluster: str
    isNearMiss: bool = False


class GalaxyPayload(BaseModel):
    jdId: str
    jdCore: dict[str, float]
    nodes: list[GalaxyNode]
    weights: dict[str, float]


class PipelineInput(BaseModel):
    text: Optional[str] = None
    audio_path: Optional[str] = None
    language: str = "en"
    dataset_path: Optional[str] = None
    top_k: Optional[int] = None


class PipelineMetrics(BaseModel):
    retrieval_count: int = 0
    rerank_count: int = 0
    latency_ms: int = 0


class PipelineResult(BaseModel):
    jdId: str
    structured_jd: StructuredJD
    bias_flags: list[BiasFlag] = Field(default_factory=list)
    ranked_shortlist: list[RankedCandidate] = Field(default_factory=list)
    near_miss_skill_gaps: list[SkillGapReport] = Field(default_factory=list)
    galaxy: Optional[GalaxyPayload] = None
    metrics: Optional[PipelineMetrics] = None
    bharat_context: Optional[BharatContextSummary] = None
    bharat_adjustments: dict[str, CandidateBharatAdjustment] = Field(default_factory=dict)


# ---- Submission output file format -----------------------------------------

class SubmissionEntry(BaseModel):
    rank: int
    candidate_id: str
    relevance_score: float
    justification: str


class SubmissionOutput(BaseModel):
    generated_at: str
    job_description: StructuredJD
    shortlist: list[SubmissionEntry]


# ---- Redrob Hackathon Submission Schemas -----------------------------------

class RedrobSkill(BaseModel):
    name: str
    proficiency: Optional[str] = None
    endorsements: Optional[int] = 0
    duration_months: Optional[int] = 0


class RedrobCareerEntry(BaseModel):
    title: str
    company: str
    industry: Optional[str] = None
    start_date: str
    end_date: Optional[str] = None
    duration_months: Optional[int] = 0
    description: str


class RedrobEducation(BaseModel):
    institution: str
    degree: str
    end_year: Optional[int] = None
    tier: Optional[str] = "unknown"


class RedrobSignals(BaseModel):
    recruiter_response_rate: Optional[float] = 0.0
    last_active_date: Optional[str] = None
    open_to_work_flag: Optional[bool] = False
    notice_period_days: Optional[int] = 60
    interview_completion_rate: Optional[float] = 0.5
    verified_email: Optional[bool] = False
    verified_phone: Optional[bool] = False
    saved_by_recruiters_30d: Optional[int] = 0


class RedrobProfile(BaseModel):
    current_title: str
    current_company: Optional[str] = None
    location: str
    country: str
    summary: str
    years_of_experience: float


class RedrobCandidate(BaseModel):
    candidate_id: str
    profile: RedrobProfile
    skills: list[RedrobSkill] = Field(default_factory=list)
    career_history: list[RedrobCareerEntry] = Field(default_factory=list)
    education: list[RedrobEducation] = Field(default_factory=list)
    redrob_signals: RedrobSignals


class SubmissionCSVRow(BaseModel):
    candidate_id: str
    rank: int
    score: float
    reasoning: str
