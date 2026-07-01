import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { GalaxyNode } from "@polyhire/shared-types";

export interface GalaxyState {
  nodes: GalaxyNode[];
  weights: Record<string, number>;
  selectedNodeId: string | null;
  isReclustering: boolean;
  isVisible: boolean;
}

const initialState: GalaxyState = {
  nodes: [],
  weights: {
    embedding_similarity: 0.22,
    rerank_score: 0.28,
    years_experience_match: 0.11,
    skill_overlap_ratio: 0.15,
    recency_of_activity: 0.05,
    career_trajectory_slope: 0.04,
    engagement_score: 0.04,
    trust_score: 0.05,
    institution_tier_score: 0.04,
    informal_sector_score: 0.02,
  },
  selectedNodeId: null,
  isReclustering: false,
  isVisible: false,
};

const galaxySlice = createSlice({
  name: "galaxy",
  initialState,
  reducers: {
    setNodes(state, action: PayloadAction<GalaxyNode[]>) {
      state.nodes = action.payload;
      state.isReclustering = false;
    },
    setWeight(state, action: PayloadAction<{ key: string; value: number }>) {
      state.weights[action.payload.key] = action.payload.value;
      state.isReclustering = true;
    },
    setWeights(state, action: PayloadAction<Record<string, number>>) {
      state.weights = action.payload;
    },
    selectNode(state, action: PayloadAction<string | null>) {
      state.selectedNodeId = action.payload;
    },
    setReclustering(state, action: PayloadAction<boolean>) {
      state.isReclustering = action.payload;
    },
    setVisible(state, action: PayloadAction<boolean>) {
      state.isVisible = action.payload;
    },
    resetGalaxy(state) {
      state.nodes = [];
      state.selectedNodeId = null;
      state.isReclustering = false;
      state.isVisible = false;
      state.weights = initialState.weights;
    },
  },
});

export const {
  setNodes,
  setWeight,
  setWeights,
  selectNode,
  setReclustering,
  setVisible,
  resetGalaxy,
} = galaxySlice.actions;
export default galaxySlice.reducer;
