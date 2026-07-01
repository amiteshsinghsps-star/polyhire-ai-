/**
 * PolyHire AI — Shared Type Contract
 * ------------------------------------------------------------------
 * Single source of truth for shapes flowing through the system:
 *   ML service (Python) → Gateway (Node) → Frontend (React)
 *
 * The Python ML service emits JSON matching these shapes; the gateway
 * passes them through; the frontend consumes them via Redux Toolkit.
 */

// ---------------------------------------------------------------------------
// Job Description
// ---------------------------------------------------------------------------

export type SeniorityLevel = "junior" | "mid" | "senior" | "staff" | "principal";

export interface StructuredJD {
  role_title: string;
  seniority: SeniorityLevel;
  must_have_skills: string[];
  nice_to_have_skills: string[];
  domain: string;
  min_years_experience: number;
  soft_requirements: string[];
  implicit_requirements: string[];
}

// ---------------------------------------------------------------------------
// Bias detection
// ---------------------------------------------------------------------------

export interface BiasFlag {
  sentence: string;
  confidence: number;
  category?: string;
}

// ---------------------------------------------------------------------------
// Candidate
// ---------------------------------------------------------------------------

export interface CandidateMetadata {
  years_experience: number;
  num_jobs: number;
  avg_tenure_months: number;
  title_jump_velocity: number;
  claimed_skill_count: number;
  profile_completeness: number;
  last_activity_days_ago: number;
  career_trajectory_slope: number;
  engagement_score: number;
}

export interface CandidateProfile {
  id: string;
  name?: string;
  summary: string;
  skills: string[];
  current_title?: string;
  profile_text: string;
  metadata: CandidateMetadata;
  trust_score?: number;
}

// ---------------------------------------------------------------------------
// Fusion ranker features & contributions
// ---------------------------------------------------------------------------

export type FusionFeature =
  | "embedding_similarity"
  | "rerank_score"
  | "years_experience_match"
  | "skill_overlap_ratio"
  | "recency_of_activity"
  | "career_trajectory_slope"
  | "engagement_score"
  | "trust_score"
  | "institution_tier_score"
  | "informal_sector_score";

export const FUSION_FEATURES: FusionFeature[] = [
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
];

export type FeatureContributions = Record<FusionFeature | "base_value", number>;

// ---------------------------------------------------------------------------
// Ranked shortlist entries
// ---------------------------------------------------------------------------

export interface RankedCandidate {
  rank: number;
  candidate_id: string;
  name?: string;
  score: number;
  explanation: string;
  trust_score: number;
  feature_contributions?: FeatureContributions;
  skills?: string[];
  current_title?: string;
  bharat_adjustment?: CandidateBharatAdjustment;
}

export interface BharatContextSummary {
  total_candidates: number;
  tier_1_count: number;
  tier_2_count: number;
  tier_3_count: number;
  tier_adjusted_count: number;
  nirf_matched_count: number;
  code_switch_detected_count: number;
  informal_sector_count: number;
  avg_engagement_delta: number;
  processing_ms: number;
}

export interface CandidateBharatAdjustment {
  tier_adjusted: boolean;
  bharat_tier: string;
  engagement_delta: number;
  institution_score: number;
  institution_matched: boolean;
  code_switch_detected: boolean;
  skills_added_by_bil3: string[];
  informal_sector_score: number;
  informal_explanation: string;
  skills_added_by_bil4: string[];
}

export interface SkillGapReport {
  candidate_id: string;
  name?: string;
  report: string;
  missing_skills: string[];
}

// ---------------------------------------------------------------------------
// 3D Galaxy
// ---------------------------------------------------------------------------

export type GalaxyCluster = string;

export interface GalaxyNode {
  candidateId: string;
  x: number;
  y: number;
  z: number;
  rank: number;
  score: number;
  cluster: GalaxyCluster;
  isNearMiss?: boolean;
}

export interface GalaxyPayload {
  jdId: string;
  jdCore: { x: number; y: number; z: number };
  nodes: GalaxyNode[];
  weights: Record<string, number>;
}

// ---------------------------------------------------------------------------
// Pipeline I/O
// ---------------------------------------------------------------------------

export interface PipelineInput {
  text?: string;
  audio_path?: string;
  language?: string; // ISO code: "en" | "hi" | ... ; "hi" triggers IndicTrans2
  dataset_path?: string; // optional override for candidate pool
  top_k?: number;
}

export interface PipelineResult {
  jdId: string;
  structured_jd: StructuredJD;
  bias_flags: BiasFlag[];
  ranked_shortlist: RankedCandidate[];
  near_miss_skill_gaps: SkillGapReport[];
  galaxy: GalaxyPayload;
  metrics?: {
    retrieval_count: number;
    rerank_count: number;
    latency_ms: number;
  };
  bharat_context?: BharatContextSummary;
  bharat_adjustments?: Record<string, CandidateBharatAdjustment>;
}

// ---------------------------------------------------------------------------
// Pipeline progress (WebSocket)
// ---------------------------------------------------------------------------

export type PipelineStage =
  | "input_normalization"
  | "bias_scan"
  | "jd_parsing"
  | "embedding"
  | "retrieval"
  | "reranking"
  | "bharat_contextualization"
  | "fusion"
  | "explainability"
  | "skill_gap"
  | "galaxy_projection"
  | "complete";

export interface PipelineStartedEvent {
  stage: PipelineStage;
  jdId: string;
  timestamp: number;
}

export interface PipelineProgressEvent {
  stage: PipelineStage;
  jdId: string;
  message?: string;
  progress?: number; // 0..1
  timestamp: number;
}

export interface PipelineErrorEvent {
  jdId: string;
  stage: PipelineStage;
  error: string;
  timestamp: number;
}

export interface GalaxyReweightCommand {
  jdId: string;
  weights: Record<string, number>;
}

export interface GalaxyUpdateEvent {
  jdId: string;
  coordinates: GalaxyNode[];
  weights: Record<string, number>;
}

// ---------------------------------------------------------------------------
// REST request/response envelopes
// ---------------------------------------------------------------------------

export interface SubmitJDResponse extends PipelineResult {}

export interface SubmitJDRequest extends PipelineInput {}

// ---------------------------------------------------------------------------
// Submission artifact format
// ---------------------------------------------------------------------------

export interface SubmissionShortlistEntry {
  rank: number;
  candidate_id: string;
  relevance_score: number;
  justification: string;
}

export interface SubmissionOutput {
  generated_at: string;
  job_description: StructuredJD;
  shortlist: SubmissionShortlistEntry[];
}

// ---------------------------------------------------------------------------
// Enterprise Features (§23)
// ---------------------------------------------------------------------------

// §23.1 — Uncertainty bands
export interface UncertaintyBand {
  candidateId: string;
  pointEstimate: number;
  lowerBound: number;
  upperBound: number;
  confidenceWidth: number;
  isHighConfidence: boolean;
}

export interface UncertaintyResponse {
  candidate_id: string;
  bands: Array<{
    point_estimate: number;
    lower_bound: number;
    upper_bound: number;
    confidence_width: number;
    is_high_confidence: boolean;
  }>;
  warning?: string;
}

// §23.2 — Counterfactuals
export interface CounterfactualChange {
  from: number;
  to: number;
}

export interface CounterfactualResult {
  changes: Record<string, CounterfactualChange>;
  resultingScore: number;
  humanReadable: string;
}

export interface CounterfactualResponse {
  candidate_id: string;
  counterfactuals: Array<{
    changes: Record<string, { from: number; to: number }>;
    resulting_score: number;
  }>;
  human_readable: string[];
}

// §23.3 — Portfolio optimization
export interface PortfolioAssignment {
  candidate_id: string;
  assigned_role: string;
  score: number;
}

export interface PortfolioComparison {
  naive_total_score: number;
  optimized_total_score: number;
  naive_unique_candidates_used: number;
  optimized_unique_candidates_used: number;
  candidate_pool_utilization_gain: number;
}

export interface PortfolioOptimizeResponse {
  assignments: PortfolioAssignment[];
  comparison: PortfolioComparison;
}

// §23.4 — Audit trail
export interface AuditEntry {
  id: number;
  jd_id: string;
  candidate_id: string;
  rank: number;
  feature_snapshot: Record<string, unknown>;
  model_version: string;
  fusion_score: number;
  timestamp: string;
  prev_hash: string;
  entry_hash: string;
}

export interface AuditTrailResponse {
  jd_id: string;
  entries: AuditEntry[];
  count: number;
}

export interface AuditVerifyResponse {
  jd_id: string;
  chain_valid: boolean;
}

// §23.5 — Diversity re-ranking
export interface DiversityResult {
  candidate_id: string;
  relevance_score: number;
  selection_order: number;
}

export interface DiversityReport {
  candidates_reordered_pct: number;
  top_5_unchanged: boolean;
}

export interface DiversifyResponse {
  ranked: DiversityResult[];
  diversity_report: DiversityReport;
}

// §23.6 — Passive talent matches
export interface PassiveMatchFlag {
  candidate_id: string;
  matched_archetype: string;
  similarity: number;
  flagged_at: string;
  recommended_action: string;
}

export interface PassiveMatchesResponse {
  flags: PassiveMatchFlag[];
  count: number;
}

// §23.7 — Interview questions
export interface InterviewQuestion {
  question: string;
  probes_for: string;
  what_a_strong_answer_sounds_like: string;
}

export interface InterviewQuestionsResponse {
  candidate_id: string;
  questions: InterviewQuestion[];
}

// §23.8 — Drift monitoring
export interface DriftStatus {
  drift_detected: boolean;
  drifted_features: string[];
  recommendation: string;
}
