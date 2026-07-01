import { configureStore } from "@reduxjs/toolkit";
import pipelineReducer from "./slices/pipelineSlice";
import shortlistReducer from "./slices/shortlistSlice";
import galaxyReducer from "./slices/galaxySlice";
import uiReducer from "./slices/uiSlice";
import enterpriseReducer from "./slices/enterpriseSlice";
import bharatReducer from "./slices/bharatSlice";
// v3.0 Slices
import shieldReducer from "./slices/shieldSlice";
import diverseHireReducer from "./slices/diverseHireSlice";

export const store = configureStore({
  reducer: {
    pipeline: pipelineReducer,
    shortlist: shortlistReducer,
    galaxy: galaxyReducer,
    ui: uiReducer,
    enterprise: enterpriseReducer,
    bharat: bharatReducer,
    shield: shieldReducer,
    diverseHire: diverseHireReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
