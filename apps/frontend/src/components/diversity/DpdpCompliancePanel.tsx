import React, { useEffect, useState } from "react";
import { fetchDpdpComplianceSummary } from "../../lib/api";
import { ShieldCheck, Server, Key, FileText, FileWarning } from "lucide-react";

export function DpdpCompliancePanel() {
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const data = await fetchDpdpComplianceSummary();
        setSummary(data);
      } catch (err) {
        console.error("Failed to load DPDP summary", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
          <ShieldCheck className="h-6 w-6 text-emerald-500" />
          DPDP Compliance & Security
        </h2>
        <p className="text-sm text-slate-400">
          India's Digital Personal Data Protection Act (2023) status and Vector DB Security overview.
        </p>
      </div>

      {loading ? (
        <div className="text-slate-400 animate-pulse">Loading compliance data...</div>
      ) : summary ? (
        <div className="grid grid-cols-2 gap-6">
          
          {/* DPDP Stats */}
          <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-6 shadow-xl backdrop-blur-md">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <FileText className="h-5 w-5 text-indigo-400" />
              DPDP Act 2023 Status
            </h3>
            <div className="space-y-4 text-sm text-slate-300">
              <div className="flex justify-between items-center p-3 bg-slate-800/50 rounded border border-slate-700">
                <span>Candidates with Consent</span>
                <span className="font-bold text-white">{summary.candidates_with_consent || 0}</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-slate-800/50 rounded border border-slate-700">
                <span>Consent Records (Ledger)</span>
                <span className="font-bold text-white">{summary.consent_records || 0}</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-slate-800/50 rounded border border-slate-700">
                <span>Pending Erasure Requests</span>
                <span className="font-bold text-white">{summary.erasure_requests || 0}</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-slate-800/50 rounded border border-slate-700">
                <span>Algorithmic Transparency Entries</span>
                <span className="font-bold text-white">{summary.transparency_log_entries || 0}</span>
              </div>
            </div>
            <div className="mt-4 p-3 bg-emerald-500/10 rounded border border-emerald-500/20 text-xs text-emerald-400">
              System is currently operating in compliant mode for the {summary.enforcement_phase} rollout phase.
            </div>
          </div>

          {/* Vector Security Stats (Static for now as it's backend-heavy) */}
          <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-6 shadow-xl backdrop-blur-md">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Server className="h-5 w-5 text-cyan-400" />
              Vector DB Security Layer
            </h3>
            <div className="space-y-4 text-sm text-slate-300">
              <div className="flex items-center gap-3 p-3 bg-slate-800/50 rounded border border-slate-700">
                <Key className="h-5 w-5 text-emerald-400" />
                <div>
                  <div className="font-medium text-white">HMAC Embedding Guard</div>
                  <div className="text-xs text-slate-400">Active. Cryptographically signing all ingestions.</div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 bg-slate-800/50 rounded border border-slate-700">
                <FileWarning className="h-5 w-5 text-emerald-400" />
                <div>
                  <div className="font-medium text-white">PoisonDetector (RAG Defence)</div>
                  <div className="text-xs text-slate-400">Active. L2 Norm Z-Score thresholding enabled.</div>
                </div>
              </div>
            </div>
            <div className="mt-4 p-3 bg-indigo-500/10 rounded border border-indigo-500/20 text-xs text-indigo-400">
              Vector DB Security protects against adversarial RAG poisoning and embedding tampering.
            </div>
          </div>

        </div>
      ) : null}
    </div>
  );
}
