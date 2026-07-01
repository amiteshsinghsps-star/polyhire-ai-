import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

export type TabId = "galaxy" | "shortlist" | "skill-gaps" | "metrics" | "enterprise" | "intent" | "outcomes" | "shield" | "diversity" | "dpdp";

export interface UIState {
  activeTab: TabId;
  sidebarOpen: boolean;
  jdLanguage: "en" | "hi";
  showBiasPanel: boolean;
  toastMessage: string | null;
  toastType: "info" | "success" | "error";
}

const initialState: UIState = {
  activeTab: "galaxy",
  sidebarOpen: true,
  jdLanguage: "en",
  showBiasPanel: false,
  toastMessage: null,
  toastType: "info",
};

const uiSlice = createSlice({
  name: "ui",
  initialState,
  reducers: {
    setTab(state, action: PayloadAction<TabId>) {
      state.activeTab = action.payload;
    },
    toggleSidebar(state) {
      state.sidebarOpen = !state.sidebarOpen;
    },
    setSidebarOpen(state, action: PayloadAction<boolean>) {
      state.sidebarOpen = action.payload;
    },
    setJdLanguage(state, action: PayloadAction<"en" | "hi">) {
      state.jdLanguage = action.payload;
    },
    setShowBiasPanel(state, action: PayloadAction<boolean>) {
      state.showBiasPanel = action.payload;
    },
    showToast(state, action: PayloadAction<{ message: string; type?: "info" | "success" | "error" }>) {
      state.toastMessage = action.payload.message;
      state.toastType = action.payload.type ?? "info";
    },
    clearToast(state) {
      state.toastMessage = null;
    },
  },
});

export const { setTab, toggleSidebar, setSidebarOpen, setJdLanguage, setShowBiasPanel, showToast, clearToast } =
  uiSlice.actions;
export default uiSlice.reducer;
