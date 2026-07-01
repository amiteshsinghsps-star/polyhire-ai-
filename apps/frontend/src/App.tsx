import { useEffect, useRef } from "react";
import { useAppSelector, useAppDispatch } from "./store/hooks";
import { useSocket } from "./hooks/useSocket";
import { fetchHealth } from "./lib/api";
import { Layout } from "./components/shared/Layout";
import { JDTextInput } from "./components/jd-input/JDTextInput";
import { VoiceInputButton } from "./components/jd-input/VoiceInputButton";
import { CandidateGalaxy } from "./components/galaxy/CandidateGalaxy";
import { ShortlistTable } from "./components/dashboard/ShortlistTable";
import { BiasFlagPanel } from "./components/dashboard/BiasFlagPanel";
import { SkillGapPanel } from "./components/dashboard/SkillGapPanel";
import { WeightSliders } from "./components/dashboard/WeightSliders";
import { MetricsPanel } from "./components/dashboard/MetricsPanel";
import { PortfolioOptimizerView } from "./components/dashboard/PortfolioOptimizerView";
import { AuditTrailViewer } from "./components/dashboard/AuditTrailViewer";
import { DiversityToggle } from "./components/dashboard/DiversityToggle";
import { PassiveMatchesPanel } from "./components/dashboard/PassiveMatchesPanel";
import { InterviewQuestionPanel } from "./components/dashboard/InterviewQuestionPanel";
import { DriftMonitorDashboard } from "./components/dashboard/DriftMonitorDashboard";
import { CounterfactualPanel } from "./components/dashboard/CounterfactualPanel";
import { BharatContextPanel } from "./components/dashboard/BharatContextPanel";
import { InstitutionLookup } from "./components/dashboard/InstitutionLookup";
// v2.0 Feature Expansion
import { IntentMatrix } from "./components/intent/IntentMatrix";
import { OutcomePredictPanel } from "./components/outcomes/OutcomePredictPanel";
// v3.0 Feature Expansion
import { ResumeShieldPanel } from "./components/shield/ResumeShieldPanel";
import { DiverseHirePanel } from "./components/diversity/DiverseHirePanel";
import { DpdpCompliancePanel } from "./components/diversity/DpdpCompliancePanel";
import {
  setCapabilities,
  setMlHealth,
} from "./store/slices/pipelineSlice";
import { setTab, toggleSidebar, setSidebarOpen, setShowBiasPanel, type TabId } from "./store/slices/uiSlice";
import { setVisible } from "./store/slices/galaxySlice";

const TABS: { id: TabId; label: string }[] = [
  { id: "galaxy", label: "🌌 Galaxy" },
  { id: "shortlist", label: "📋 Shortlist" },
  { id: "skill-gaps", label: "⚡ Skill Gaps" },
  { id: "intent", label: "🎯 Intent" },
  { id: "outcomes", label: "🔮 Outcomes" },
  { id: "shield", label: "🛡️ Shield" },
  { id: "diversity", label: "🌈 Diversity" },
  { id: "dpdp", label: "📜 DPDP" },
  { id: "enterprise", label: "🛰️ Enterprise" },
  { id: "metrics", label: "📊 Metrics" },
];

export default function App() {
  const dispatch = useAppDispatch();
  const activeTab = useAppSelector((s) => s.ui.activeTab);
  const sidebarOpen = useAppSelector((s) => s.ui.sidebarOpen);
  const pipelineRunning = useAppSelector((s) => s.pipeline.isRunning);
  const biasFlags = useAppSelector((s) => s.pipeline.biasFlags);

  const prevTabRef = useRef(activeTab);
  useEffect(() => {
    if (prevTabRef.current !== activeTab) {
      if (activeTab === "galaxy") {
        dispatch(setSidebarOpen(false));
      } else {
        dispatch(setSidebarOpen(true));
      }
      prevTabRef.current = activeTab;
    }
  }, [activeTab, dispatch]);

  useSocket();

  // Fetch ML health + capabilities on mount.
  useEffect(() => {
    fetchHealth()
      .then((res) => {
        dispatch(setCapabilities(res.ml.capabilities));
        dispatch(setMlHealth(res.ml));
      })
      .catch(() => {
        /* ML service may not be running yet */
      });
  }, [dispatch]);

  // Auto-show bias panel when flags appear.
  useEffect(() => {
    if (biasFlags.length > 0) {
      dispatch(setShowBiasPanel(true));
    }
  }, [biasFlags.length, dispatch]);

  const galaxyNodes = useAppSelector((s) => s.galaxy.nodes);
  const candidates = useAppSelector((s) => s.shortlist.candidates);
  const lastJdId = useAppSelector((s) => s.pipeline.lastJdId);
  const bharatSummary = useAppSelector((s) => s.bharat.summary);
  const bharatEnabled = useAppSelector((s) => s.pipeline.capabilities?.bharat_intelligence ?? true);

  // Show galaxy tab when pipeline completes and nodes arrive.
  useEffect(() => {
    if (!pipelineRunning && galaxyNodes.length > 0) {
      dispatch(setVisible(true));
    }
  }, [pipelineRunning, galaxyNodes.length, dispatch]);

  return (
    <Layout>
      <div className="flex flex-1 overflow-hidden relative">
        {/* ---- Sidebar ---- */}
        <aside
          className={`flex w-[360px] shrink-0 flex-col border-r border-gridline/40 transition-all duration-300 ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          } ${
            activeTab === "galaxy"
              ? "absolute z-30 h-full bg-surface/95 backdrop-blur-xl shadow-2xl"
              : "relative bg-void/40"
          }`}
        >
          <div className="flex items-center justify-between border-b border-gridline/30 px-4 py-2">
            <span className="text-[11px] font-mono text-primary/30">INPUT</span>
            <button onClick={() => dispatch(toggleSidebar())} className="text-primary/30 hover:text-primary/60">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="12" x2="21" y2="12" />
                <polyline points="9 5 16 12 9 19" />
              </svg>
            </button>
          </div>

          <div className="space-y-4 p-4">
            <JDTextInput />
            <div className="flex items-center gap-2">
              <VoiceInputButton />
            </div>

            {/* Bias flags */}
            <BiasFlagPanel />

            {/* Bharat Intelligence Layer summary */}
            {bharatEnabled && <BharatContextPanel summary={bharatSummary} />}

            {/* NIRF institution lookup */}
            {bharatEnabled && <InstitutionLookup />}

            {/* Fusion weight sliders */}
            {activeTab === "galaxy" && (
              <div className="panel px-4 py-3">
                <WeightSliders />
              </div>
            )}
          </div>
        </aside>

        {/* ---- Sidebar toggle (when collapsed) ---- */}
        {!sidebarOpen && (
          <button
            onClick={() => dispatch(toggleSidebar())}
            className="absolute left-0 top-14 z-40 rounded-r-lg border border-l-0 border-gridline/40 bg-surface/80 px-1 py-3 backdrop-blur-md transition hover:bg-surface"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-primary/40">
              <polyline points="15 5 8 12 15 19" />
            </svg>
          </button>
        )}

        {/* ---- Main content ---- */}
        <div className="flex flex-1 flex-col overflow-hidden relative">
          {/* Tab bar */}
          <nav className={`flex items-center gap-1 px-4 py-1 transition-all z-20 ${
            activeTab === "galaxy"
              ? "absolute top-0 left-0 right-0 bg-void/30 backdrop-blur-md border-b border-gridline/30"
              : "relative border-b border-gridline/30"
          }`}>
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => dispatch(setTab(tab.id))}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  activeTab === tab.id
                    ? "bg-starlight/15 text-starlight"
                    : "text-primary/40 hover:bg-surface hover:text-primary/60"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>

          {/* Tab content */}
          <div className="flex-1 overflow-hidden">
            {activeTab === "galaxy" && <CandidateGalaxy />}
            {activeTab === "shortlist" && (
              <div className="h-full overflow-auto p-4">
                <ShortlistTable />
              </div>
            )}
            {activeTab === "skill-gaps" && (
              <div className="h-full overflow-auto p-4">
                <SkillGapPanel />
              </div>
            )}
            {/* v2.0: CandidateIntent™ Tab */}
            {activeTab === "intent" && (
              <div className="h-full overflow-auto p-4">
                <IntentMatrix />
              </div>
            )}
            {/* v2.0: HirePredict™ Outcomes Tab */}
            {activeTab === "outcomes" && (
              <div className="h-full overflow-auto p-4">
                <OutcomePredictPanel />
              </div>
            )}
            {activeTab === "metrics" && (
              <div className="h-full overflow-auto p-4">
                <MetricsPanel />
              </div>
            )}
            {/* v3.0 Tabs */}
            {activeTab === "shield" && (
              <div className="h-full overflow-auto p-4">
                <ResumeShieldPanel />
              </div>
            )}
            {activeTab === "diversity" && (
              <div className="h-full overflow-auto p-4">
                <DiverseHirePanel />
              </div>
            )}
            {activeTab === "dpdp" && (
              <div className="h-full overflow-auto p-4">
                <DpdpCompliancePanel />
              </div>
            )}
            {activeTab === "enterprise" && (
              <div className="h-full space-y-4 overflow-auto p-4">
                {/* §23.8 Drift monitor — always visible at top */}
                <DriftMonitorDashboard />

                {/* §23.1 Confidence + §23.2 Counterfactual — for top-ranked candidate */}
                {candidates[0] && (
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <CounterfactualPanel candidateId={candidates[0].candidate_id} />
                    <InterviewQuestionPanel
                      candidateId={candidates[0].candidate_id}
                      roleTitle="the role"
                      claimedSkills={candidates[0].skills ?? []}
                      uncertainSkills={[]}
                    />
                  </div>
                )}

                {/* §23.3 Portfolio + §23.5 Diversity */}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <PortfolioOptimizerView />
                  <DiversityToggle
                    candidateIds={candidates.map((c) => c.candidate_id)}
                    scores={candidates.map((c) => c.score)}
                  />
                </div>

                {/* §23.6 Passive talent + §23.4 Audit trail */}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <PassiveMatchesPanel />
                  {lastJdId && <AuditTrailViewer jdId={lastJdId} />}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Layout>
  );
}
