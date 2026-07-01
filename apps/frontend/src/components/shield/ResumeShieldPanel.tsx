import React, { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import type { AppDispatch, RootState } from "../../store";
import { analyzeFraudBatch, fetchFraudStats } from "../../lib/api";
import {
  setFraudSummary,
  setPerCandidateFraud,
  setShieldLoading,
  setLastAnalyzedJdId,
} from "../../store/slices/shieldSlice";
import { Shield, ShieldAlert, FileWarning, Search, Info } from "lucide-react";

export function ResumeShieldPanel() {
  const dispatch = useDispatch<AppDispatch>();
  const { currentResult } = useSelector((state: RootState) => state.pipeline);
  const { shortlist } = useSelector((state: RootState) => state.shortlist);
  const shield = useSelector((state: RootState) => state.shield);

  useEffect(() => {
    if (!currentResult?.jdId || !shortlist || shortlist.length === 0) return;
    
    // Only fetch if we haven't already for this JD
    if (shield.lastAnalyzedJdId === currentResult.jdId) return;

    async function loadFraudData() {
      dispatch(setShieldLoading(true));
      try {
        const payload = {
          candidates: shortlist,
          structured_jd: currentResult?.structured_jd || {},
        };
        const res: any = await analyzeFraudBatch(payload);
        
        dispatch(setFraudSummary(res.fraud_summary));
        dispatch(setPerCandidateFraud(res.candidates));
        dispatch(setLastAnalyzedJdId(currentResult!.jdId));
      } catch (err) {
        console.error("Failed to analyze fraud:", err);
      } finally {
        dispatch(setShieldLoading(false));
      }
    }

    loadFraudData();
  }, [currentResult?.jdId, shortlist, dispatch, shield.lastAnalyzedJdId]);

  if (!currentResult || !shortlist) {
    return (
      <div className="flex h-64 flex-col items-center justify-center text-slate-400">
        <Shield className="mb-4 h-12 w-12 opacity-50" />
        <p>Run the discovery pipeline to view ResumeShield™ analysis.</p>
      </div>
    );
  }

  if (shield.loading) {
    return (
      <div className="flex h-64 flex-col items-center justify-center text-slate-400">
        <Search className="mb-4 h-8 w-8 animate-pulse text-indigo-400" />
        <p>Scanning {shortlist.length} profiles across 6 fraud detectors...</p>
      </div>
    );
  }

  const { fraudSummary, perCandidate } = shield;
  const blockedCount = fraudSummary?.blocked || 0;
  const highRiskCount = fraudSummary?.high_risk || 0;
  const suspiciousCount = fraudSummary?.suspicious || 0;
  
  // Sort candidates by fraud risk (highest first)
  const sortedCandidates = Object.values(perCandidate).sort(
    (a, b) => b.fraud_risk_score - a.fraud_risk_score
  );

  return (
    <div className="space-y-6">
      {/* Header & Stats */}
      <div className="flex flex-col gap-2">
        <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
          <ShieldAlert className="h-6 w-6 text-rose-500" />
          ResumeShield™ Analysis
        </h2>
        <p className="text-sm text-slate-400">
          Scanned {fraudSummary?.total || 0} candidates for AI generation, JD mirroring, and timeline impossibilities.
        </p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-4">
          <div className="text-sm font-medium text-rose-400">Blocked</div>
          <div className="mt-1 text-2xl font-semibold text-rose-300">{blockedCount}</div>
          <p className="text-xs text-slate-400 mt-1">Hard flags (timeline, identity)</p>
        </div>
        <div className="rounded-lg border border-orange-500/30 bg-orange-500/10 p-4">
          <div className="text-sm font-medium text-orange-400">High Risk</div>
          <div className="mt-1 text-2xl font-semibold text-orange-300">{highRiskCount}</div>
          <p className="text-xs text-slate-400 mt-1">Severe AI mirroring</p>
        </div>
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
          <div className="text-sm font-medium text-amber-400">Suspicious</div>
          <div className="mt-1 text-2xl font-semibold text-amber-300">{suspiciousCount}</div>
          <p className="text-xs text-slate-400 mt-1">Moderate anomalies</p>
        </div>
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4">
          <div className="text-sm font-medium text-emerald-400">Clean</div>
          <div className="mt-1 text-2xl font-semibold text-emerald-300">{fraudSummary?.clean || 0}</div>
          <p className="text-xs text-slate-400 mt-1">No fraud signals</p>
        </div>
      </div>

      {/* Flagged Candidates List */}
      <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-6 shadow-xl backdrop-blur-md">
        <h3 className="mb-4 text-lg font-semibold text-white">Flagged Profiles</h3>
        
        {sortedCandidates.filter(c => c.fraud_label !== 'clean').length === 0 ? (
          <div className="text-sm text-slate-400 p-4 bg-slate-800/50 rounded-lg">
            No suspicious candidates found in this shortlist.
          </div>
        ) : (
          <div className="space-y-4">
            {sortedCandidates
              .filter(c => c.fraud_label !== 'clean')
              .map((c) => (
              <div key={c.candidate_id} className="rounded-lg border border-slate-700 bg-slate-800 p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-white">{c.candidate_id}</span>
                      <span className={`rounded px-2 py-0.5 text-xs font-medium ${
                        c.fraud_label === 'blocked' ? 'bg-rose-500/20 text-rose-400' :
                        c.fraud_label === 'high_risk' ? 'bg-orange-500/20 text-orange-400' :
                        'bg-amber-500/20 text-amber-400'
                      }`}>
                        {c.fraud_label.toUpperCase()}
                      </span>
                      <span className="text-xs text-slate-400">
                        Risk Score: {(c.fraud_risk_score * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {c.fraud_flags.map((flag, i) => (
                        <div key={i} className="flex items-center gap-1 rounded bg-slate-900/50 px-2 py-1 text-xs text-slate-300 border border-slate-700">
                          <FileWarning className="h-3 w-3 text-amber-400" />
                          {flag}
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 text-sm text-slate-400 flex items-start gap-1.5">
                      <Info className="h-4 w-4 mt-0.5 text-slate-500 shrink-0" />
                      <span>{c.recruiter_action} (Trust Penalty: -{(c.trust_penalty * 100).toFixed(0)}%)</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
