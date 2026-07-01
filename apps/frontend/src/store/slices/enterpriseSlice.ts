/**
 * Enterprise Feature State (§23).
 *
 * Holds results from the 8 enterprise endpoints: uncertainty bands,
 * counterfactuals, portfolio optimization, audit trail, diversity toggle,
 * passive matches, interview questions, and drift status.
 */
import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type {
  UncertaintyBand,
  CounterfactualResult,
  AuditEntry,
  DiversityReport,
  PassiveMatchFlag,
  InterviewQuestion,
  DriftStatus,
} from "@polyhire/shared-types";

interface PortfolioAssignmentView {
  candidateId: string;
  assignedRole: string;
  score: number;
}

interface PortfolioComparisonView {
  naiveTotalScore: number;
  optimizedTotalScore: number;
  naiveUniqueCandidatesUsed: number;
  optimizedUniqueCandidatesUsed: number;
  candidatePoolUtilizationGain: number;
}

export interface EnterpriseState {
  // §23.1
  uncertaintyBands: Record<string, UncertaintyBand>;
  // §23.2
  counterfactuals: Record<string, CounterfactualResult[]>;
  // §23.3
  portfolioAssignments: PortfolioAssignmentView[];
  portfolioComparison: PortfolioComparisonView | null;
  // §23.4
  auditTrail: AuditEntry[];
  auditChainValid: boolean | null;
  // §23.5
  diversityActive: boolean;
  diversityReport: DiversityReport | null;
  // §23.6
  passiveMatches: PassiveMatchFlag[];
  // §23.7
  interviewQuestions: Record<string, InterviewQuestion[]>;
  // §23.8
  driftStatus: DriftStatus | null;
  // Misc
  loading: Record<string, boolean>;
  error: string | null;
}

const initialState: EnterpriseState = {
  uncertaintyBands: {},
  counterfactuals: {},
  portfolioAssignments: [],
  portfolioComparison: null,
  auditTrail: [],
  auditChainValid: null,
  diversityActive: false,
  diversityReport: null,
  passiveMatches: [],
  interviewQuestions: {},
  driftStatus: null,
  loading: {},
  error: null,
};

const enterpriseSlice = createSlice({
  name: "enterprise",
  initialState,
  reducers: {
    // §23.1
    setUncertaintyBand(state, action: PayloadAction<UncertaintyBand>) {
      state.uncertaintyBands[action.payload.candidateId] = action.payload;
    },
    // §23.2
    setCounterfactuals(
      state,
      action: PayloadAction<{ candidateId: string; cfs: CounterfactualResult[] }>,
    ) {
      state.counterfactuals[action.payload.candidateId] = action.payload.cfs;
    },
    // §23.3
    setPortfolioResults(
      state,
      action: PayloadAction<{
        assignments: PortfolioAssignmentView[];
        comparison: PortfolioComparisonView;
      }>,
    ) {
      state.portfolioAssignments = action.payload.assignments;
      state.portfolioComparison = action.payload.comparison;
    },
    // §23.4
    setAuditTrail(state, action: PayloadAction<AuditEntry[]>) {
      state.auditTrail = action.payload;
    },
    setAuditChainValid(state, action: PayloadAction<boolean>) {
      state.auditChainValid = action.payload;
    },
    // §23.5
    toggleDiversity(state, action: PayloadAction<boolean>) {
      state.diversityActive = action.payload;
    },
    setDiversityReport(state, action: PayloadAction<DiversityReport | null>) {
      state.diversityReport = action.payload;
    },
    // §23.6
    setPassiveMatches(state, action: PayloadAction<PassiveMatchFlag[]>) {
      state.passiveMatches = action.payload;
    },
    // §23.7
    setInterviewQuestions(
      state,
      action: PayloadAction<{ candidateId: string; questions: InterviewQuestion[] }>,
    ) {
      state.interviewQuestions[action.payload.candidateId] = action.payload.questions;
    },
    // §23.8
    setDriftStatus(state, action: PayloadAction<DriftStatus>) {
      state.driftStatus = action.payload;
    },
    // Misc
    setLoading(state, action: PayloadAction<{ key: string; value: boolean }>) {
      state.loading[action.payload.key] = action.payload.value;
    },
    setError(state, action: PayloadAction<string | null>) {
      state.error = action.payload;
    },
  },
});

export const {
  setUncertaintyBand,
  setCounterfactuals,
  setPortfolioResults,
  setAuditTrail,
  setAuditChainValid,
  toggleDiversity,
  setDiversityReport,
  setPassiveMatches,
  setInterviewQuestions,
  setDriftStatus,
  setLoading,
  setError,
} = enterpriseSlice.actions;
export default enterpriseSlice.reducer;
