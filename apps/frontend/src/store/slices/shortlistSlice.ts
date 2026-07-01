import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { RankedCandidate, SkillGapReport, SubmissionOutput } from "@polyhire/shared-types";

export interface ShortlistState {
  candidates: RankedCandidate[];
  nearMissSkillGaps: SkillGapReport[];
  selectedCandidateId: string | null;
  submissionOutput: SubmissionOutput | null;
}

const initialState: ShortlistState = {
  candidates: [],
  nearMissSkillGaps: [],
  selectedCandidateId: null,
  submissionOutput: null,
};

const shortlistSlice = createSlice({
  name: "shortlist",
  initialState,
  reducers: {
    setShortlist(state, action: PayloadAction<RankedCandidate[]>) {
      state.candidates = action.payload;
      state.selectedCandidateId = action.payload[0]?.candidate_id ?? null;
    },
    appendShortlist(state, action: PayloadAction<RankedCandidate[]>) {
      // Used when streaming results arrive incrementally.
      state.candidates = action.payload;
    },
    setNearMissSkillGaps(state, action: PayloadAction<SkillGapReport[]>) {
      state.nearMissSkillGaps = action.payload;
    },
    selectCandidate(state, action: PayloadAction<string | null>) {
      state.selectedCandidateId = action.payload;
    },
    setSubmissionOutput(state, action: PayloadAction<SubmissionOutput>) {
      state.submissionOutput = action.payload;
    },
    resetShortlist(state) {
      state.candidates = [];
      state.nearMissSkillGaps = [];
      state.selectedCandidateId = null;
      state.submissionOutput = null;
    },
  },
});

export const {
  setShortlist,
  appendShortlist,
  setNearMissSkillGaps,
  selectCandidate,
  setSubmissionOutput,
  resetShortlist,
} = shortlistSlice.actions;
export default shortlistSlice.reducer;
