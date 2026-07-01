import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export interface DiverseHireState {
  jdAnalysis: any | null;
  shortlistAnalysis: any | null;
  loading: boolean;
  lastAnalyzedJdId: string | null;
}

const initialState: DiverseHireState = {
  jdAnalysis: null,
  shortlistAnalysis: null,
  loading: false,
  lastAnalyzedJdId: null,
};

const diverseHireSlice = createSlice({
  name: "diverseHire",
  initialState,
  reducers: {
    setJdAnalysis(state, action: PayloadAction<any>) {
      state.jdAnalysis = action.payload;
    },
    setShortlistAnalysis(state, action: PayloadAction<any>) {
      state.shortlistAnalysis = action.payload;
    },
    setDiverseHireLoading(state, action: PayloadAction<boolean>) {
      state.loading = action.payload;
    },
    setLastAnalyzedJdIdForDiversity(state, action: PayloadAction<string>) {
      state.lastAnalyzedJdId = action.payload;
    },
  },
});

export const {
  setJdAnalysis,
  setShortlistAnalysis,
  setDiverseHireLoading,
  setLastAnalyzedJdIdForDiversity,
} = diverseHireSlice.actions;

export default diverseHireSlice.reducer;
