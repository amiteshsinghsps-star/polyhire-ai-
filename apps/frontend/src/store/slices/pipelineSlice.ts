import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { PipelineStage } from "@polyhire/shared-types";

export interface PipelineState {
  isRunning: boolean;
  currentStage: PipelineStage | null;
  progress: number; // 0..1
  stageMessage: string | null;
  error: string | null;
  lastJdId: string | null;
  latencyMs: number | null;
  structuredJd: Record<string, unknown> | null;
  biasFlags: Array<{ sentence: string; confidence: number; category?: string }>;
  capabilities: Record<string, boolean> | null;
  mlHealth: Record<string, unknown> | null;
}

const initialState: PipelineState = {
  isRunning: false,
  currentStage: null,
  progress: 0,
  stageMessage: null,
  error: null,
  lastJdId: null,
  latencyMs: null,
  structuredJd: null,
  biasFlags: [],
  capabilities: null,
  mlHealth: null,
};

const pipelineSlice = createSlice({
  name: "pipeline",
  initialState,
  reducers: {
    pipelineStarted(state, action: PayloadAction<{ jdId?: string } | undefined>) {
      state.isRunning = true;
      state.error = null;
      state.progress = 0;
      state.currentStage = "input_normalization";
      state.stageMessage = null;
    },
    pipelineProgress(
      state,
      action: PayloadAction<{ stage: PipelineStage; message?: string | null; progress?: number | null }>,
    ) {
      state.currentStage = action.payload.stage;
      if (action.payload.message != null) state.stageMessage = action.payload.message;
      if (action.payload.progress != null) state.progress = action.payload.progress;
    },
    pipelineComplete(state, action: PayloadAction<{ jdId: string; latencyMs: number | null; structuredJd: Record<string, unknown>; biasFlags: PipelineState["biasFlags"] }>) {
      state.isRunning = false;
      state.currentStage = "complete";
      state.progress = 1;
      state.lastJdId = action.payload.jdId;
      state.latencyMs = action.payload.latencyMs;
      state.structuredJd = action.payload.structuredJd;
      state.biasFlags = action.payload.biasFlags;
    },
    pipelineError(state, action: PayloadAction<string>) {
      state.isRunning = false;
      state.error = action.payload;
    },
    setCapabilities(state, action: PayloadAction<Record<string, boolean>>) {
      state.capabilities = action.payload;
    },
    setMlHealth(state, action: PayloadAction<Record<string, unknown>>) {
      state.mlHealth = action.payload;
    },
    resetPipeline(state) {
      state.isRunning = false;
      state.currentStage = null;
      state.progress = 0;
      state.stageMessage = null;
      state.error = null;
    },
  },
});

export const {
  pipelineStarted,
  pipelineProgress,
  pipelineComplete,
  pipelineError,
  setCapabilities,
  setMlHealth,
  resetPipeline,
} = pipelineSlice.actions;
export default pipelineSlice.reducer;
