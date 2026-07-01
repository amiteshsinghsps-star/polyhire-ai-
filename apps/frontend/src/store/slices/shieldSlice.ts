import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export interface FraudSummary {
  clean: number;
  suspicious: number;
  high_risk: number;
  blocked: number;
  total: number;
}

export interface CandidateFraud {
  candidate_id: string;
  fraud_risk_score: number;
  fraud_label: "clean" | "suspicious" | "high_risk" | "blocked";
  fraud_flags: string[];
  trust_penalty: number;
  recruiter_action: string;
}

export interface ShieldState {
  fraudSummary: FraudSummary | null;
  perCandidate: Record<string, CandidateFraud>;
  loading: boolean;
  lastAnalyzedJdId: string | null;
}

const initialState: ShieldState = {
  fraudSummary: null,
  perCandidate: {},
  loading: false,
  lastAnalyzedJdId: null,
};

const shieldSlice = createSlice({
  name: "shield",
  initialState,
  reducers: {
    setFraudSummary(state, action: PayloadAction<FraudSummary>) {
      state.fraudSummary = action.payload;
    },
    setPerCandidateFraud(state, action: PayloadAction<CandidateFraud[]>) {
      state.perCandidate = {};
      for (const c of action.payload) {
        state.perCandidate[c.candidate_id] = c;
      }
    },
    setShieldLoading(state, action: PayloadAction<boolean>) {
      state.loading = action.payload;
    },
    setLastAnalyzedJdId(state, action: PayloadAction<string>) {
      state.lastAnalyzedJdId = action.payload;
    },
  },
});

export const {
  setFraudSummary,
  setPerCandidateFraud,
  setShieldLoading,
  setLastAnalyzedJdId,
} = shieldSlice.actions;

export default shieldSlice.reducer;
