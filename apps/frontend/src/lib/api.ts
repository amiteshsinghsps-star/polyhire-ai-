/**
 * HTTP client to the gateway.
 */
const GATEWAY_URL =
  typeof import.meta !== "undefined" && import.meta.env?.VITE_GATEWAY_URL
    ? String(import.meta.env.VITE_GATEWAY_URL)
    : "http://localhost:4000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${GATEWAY_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(body.error ?? `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

// ---------- Public surface ----------

export interface HealthResponse {
  status: string;
  gateway: { version: string };
  ml: {
    status: string;
    index_ready: boolean;
    candidate_count: number;
    backend: string;
    capabilities: Record<string, boolean>;
    fallbacks_active: Record<string, boolean>;
  };
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export function submitJD(body: {
  text?: string;
  language?: string;
  audio_path?: string;
}): Promise<unknown> {
  return request("/api/jd/submit", { method: "POST", body: JSON.stringify(body) });
}

export function fetchShortlist(jdId: string): Promise<unknown> {
  return request(`/api/shortlist/${jdId}`);
}

export function fetchGalaxy(jdId: string): Promise<unknown> {
  return request(`/api/shortlist/${jdId}/galaxy`);
}

export function fetchCandidate(jdId: string, candidateId: string): Promise<unknown> {
  return request(`/api/shortlist/${jdId}/candidate/${candidateId}`);
}

export function fetchSkillGap(jdId: string, candidateId: string): Promise<unknown> {
  return request(`/api/shortlist/${jdId}/candidate/${candidateId}/skill-gap`);
}

// ---------- Enterprise APIs (§23) ----------

export function fetchUncertainty(
  candidateId: string,
  features: Record<string, number>,
): Promise<unknown> {
  return request(`/api/enterprise/candidate/${candidateId}/uncertainty`, {
    method: "POST",
    body: JSON.stringify(features),
  });
}

export function fetchCounterfactual(
  candidateId: string,
  body: { current_features: Record<string, number>; target_score?: number },
): Promise<unknown> {
  return request(`/api/enterprise/candidate/${candidateId}/counterfactual`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function optimizePortfolio(
  scoreMatrix: Record<string, Record<string, number>>,
  slotsPerRole: Record<string, number>,
): Promise<unknown> {
  return request(`/api/enterprise/portfolio/optimize`, {
    method: "POST",
    body: JSON.stringify({ score_matrix: scoreMatrix, slots_per_role: slotsPerRole }),
  });
}

export function fetchAuditTrail(jdId: string): Promise<unknown> {
  return request(`/api/enterprise/audit/${jdId}`);
}

export function verifyAuditChain(jdId: string): Promise<unknown> {
  return request(`/api/enterprise/audit/${jdId}/verify`);
}

export function diversifyShortlist(body: {
  candidate_ids: string[];
  relevance_scores: number[];
  embeddings?: number[][];
  lambda_param?: number;
  top_k?: number;
}): Promise<unknown> {
  return request(`/api/enterprise/shortlist/diversify`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchPassiveMatches(threshold?: number): Promise<unknown> {
  const q = threshold ? `?threshold=${threshold}` : "";
  return request(`/api/enterprise/talent-pool/passive-matches${q}`);
}

export function fetchInterviewQuestions(body: {
  candidate_id: string;
  role_title: string;
  claimed_skills: string[];
  uncertain_skills?: string[];
}): Promise<unknown> {
  return request(`/api/enterprise/interview-questions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchDriftStatus(): Promise<unknown> {
  return request(`/api/enterprise/drift-status`);
}

// ---------- Bharat Intelligence Layer ----------

export function fetchNirfLookup(name: string): Promise<{ query: string; matches: Array<{ institution: string; score: number }> }> {
  return request(`/api/bharat/nirf-lookup?name=${encodeURIComponent(name)}`);
}

export function tierNormalize(body: {
  engagement_score: number;
  recency_score: number;
  city?: string;
}): Promise<unknown> {
  return request("/api/bharat/tier-normalize", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function institutionScore(body: {
  institution: string;
  degree?: string;
}): Promise<unknown> {
  return request("/api/bharat/institution-score", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function codeSwitchParse(body: {
  text: string;
  existing_skills?: string[];
}): Promise<unknown> {
  return request("/api/bharat/code-switch-parse", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function informalSectorTranslate(body: {
  profile_text: string;
  existing_skills?: string[];
}): Promise<unknown> {
  return request("/api/bharat/informal-sector-translate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ---------- v2.0: CandidateIntent™ ----------

export function scoreIntent(body: {
  candidate: Record<string, unknown>;
  structured_jd?: Record<string, unknown>;
}): Promise<unknown> {
  return request("/api/intent/score", { method: "POST", body: JSON.stringify(body) });
}

export function scoreBatchIntent(body: {
  candidates: Record<string, unknown>[];
  structured_jd?: Record<string, unknown>;
}): Promise<{ candidates: Record<string, unknown>[]; count: number }> {
  return request("/api/intent/score-batch", { method: "POST", body: JSON.stringify(body) });
}

export function buildPriorityMatrix(body: {
  candidates: Record<string, unknown>[];
  structured_jd?: Record<string, unknown>;
}): Promise<Record<string, unknown>> {
  return request("/api/intent/priority-matrix", { method: "POST", body: JSON.stringify(body) });
}

// ---------- v2.0: SkillDecay™ ----------

export function analyzeSkillDecay(body: {
  candidate: Record<string, unknown>;
  structured_jd: Record<string, unknown>;
}): Promise<Record<string, unknown>> {
  return request("/api/skill-decay/analyze", { method: "POST", body: JSON.stringify(body) });
}

export function enrichBatchSkillDecay(body: {
  candidates: Record<string, unknown>[];
  structured_jd: Record<string, unknown>;
}): Promise<{ candidates: Record<string, unknown>[]; count: number }> {
  return request("/api/skill-decay/enrich-batch", { method: "POST", body: JSON.stringify(body) });
}

// ---------- v2.0: HirePredict™ ----------

export function submitHireFeedback(body: {
  jd_id: string;
  candidate_id: string;
  hired: boolean;
  retained_30d?: boolean;
  features?: Record<string, number>;
}): Promise<Record<string, unknown>> {
  return request("/api/hire-predict/feedback", { method: "POST", body: JSON.stringify(body) });
}

export function predictHireOutcomes(body: {
  candidates: Record<string, unknown>[];
  jd_id?: string;
}): Promise<{ candidates: Record<string, unknown>[]; model_trained: boolean }> {
  return request("/api/hire-predict/predict", { method: "POST", body: JSON.stringify(body) });
}

export function fetchHirePredictAccuracy(): Promise<Record<string, unknown>> {
  return request("/api/hire-predict/accuracy");
}

export function fetchHireOutcomes(jdId: string): Promise<Record<string, unknown>> {
  return request(`/api/hire-predict/outcomes/${jdId}`);
}

// ---------- v3.0: ResumeShield™ ----------

export function analyzeFraudBatch(body: {
  candidates: Record<string, unknown>[];
  structured_jd: Record<string, unknown>;
}): Promise<Record<string, unknown>> {
  return request("/api/shield/analyze-batch", { method: "POST", body: JSON.stringify(body) });
}

export function fetchFraudStats(): Promise<Record<string, unknown>> {
  return request("/api/shield/stats");
}

// ---------- v3.0: DiverseHire™ ----------

export function analyzeDiversityFullReport(body: {
  jd_text: string;
  candidates: Record<string, unknown>[];
}): Promise<Record<string, unknown>> {
  return request("/api/diverse-hire/full-report", { method: "POST", body: JSON.stringify(body) });
}

// ---------- v3.0: DPDP Compliance ----------

export function fetchDpdpComplianceSummary(): Promise<Record<string, unknown>> {
  return request("/api/dpdp/compliance-summary");
}

