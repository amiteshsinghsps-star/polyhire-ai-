import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { BharatContextSummary, CandidateBharatAdjustment } from "@polyhire/shared-types";

export interface BharatState {
  enabled: boolean;
  summary: BharatContextSummary | null;
  candidateAdjustments: Record<string, CandidateBharatAdjustment>;
  panelExpanded: boolean;
}

const initialState: BharatState = {
  enabled: true,
  summary: null,
  candidateAdjustments: {},
  panelExpanded: false,
};

const bharatSlice = createSlice({
  name: "bharat",
  initialState,
  reducers: {
    setBharatSummary(state, action: PayloadAction<BharatContextSummary | null>) {
      state.summary = action.payload;
    },
    setCandidateAdjustments(
      state,
      action: PayloadAction<Record<string, CandidateBharatAdjustment>>,
    ) {
      state.candidateAdjustments = action.payload;
    },
    setBharatEnabled(state, action: PayloadAction<boolean>) {
      state.enabled = action.payload;
    },
    toggleBharatPanel(state) {
      state.panelExpanded = !state.panelExpanded;
    },
    clearBharatState(state) {
      state.summary = null;
      state.candidateAdjustments = {};
    },
  },
});

export const {
  setBharatSummary,
  setCandidateAdjustments,
  setBharatEnabled,
  toggleBharatPanel,
  clearBharatState,
} = bharatSlice.actions;
export default bharatSlice.reducer;
