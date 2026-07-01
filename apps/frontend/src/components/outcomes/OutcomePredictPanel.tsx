/**
 * OutcomePredictPanel — shows HirePredict™ accuracy report + per-candidate
 * hire probability badges for the current shortlist.
 *
 * Before 10 outcomes: onboarding state with collection progress bar.
 * After training:     sortable table with probability + label.
 */
import { useState, useEffect } from "react";
import { useAppSelector } from "../../store/hooks";
import { fetchHirePredictAccuracy, predictHireOutcomes } from "../../lib/api";
import { HireOutcomeForm } from "./HireOutcomeForm";

interface AccuracyReport {
  total_outcomes:      number;
  model_trained:       boolean;
  min_samples_required: number;
  ready:               boolean;
  note:                string;
}

interface EnrichedCandidate {
  candidate_id:      string;
  name?:             string;
  current_title?:    string;
  score:             number;
  trust_score:       number;
  hire_probability?: number;
  hire_predict_label?: "high" | "medium" | "low";
  [key: string]: unknown;
}

const LABEL_STYLE: Record<string, string> = {
  high:   "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  medium: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  low:    "bg-red-500/20 text-red-400 border-red-500/30",
};

export function OutcomePredictPanel() {
  const candidates = useAppSelector((s) => s.shortlist.candidates);
  const lastJdId   = useAppSelector((s) => s.pipeline.lastJdId);

  const [accuracy, setAccuracy]         = useState<AccuracyReport | null>(null);
  const [enriched, setEnriched]         = useState<EnrichedCandidate[]>([]);
  const [feedbackId, setFeedbackId]     = useState<string | null>(null);
  const [loading, setLoading]           = useState(false);

  function reload() {
    setLoading(true);
    Promise.all([
      fetchHirePredictAccuracy(),
      candidates.length > 0
        ? predictHireOutcomes({ candidates: candidates as unknown as Record<string, unknown>[], jd_id: lastJdId ?? undefined })
        : Promise.resolve({ candidates: [] }),
    ])
      .then(([acc, preds]) => {
        setAccuracy(acc as AccuracyReport);
        const predList = (preds as { candidates: EnrichedCandidate[] }).candidates ?? [];
        setEnriched(predList.length > 0 ? predList : candidates as unknown as EnrichedCandidate[]);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }

  useEffect(() => { reload(); }, [candidates.length, lastJdId]); // eslint-disable-line react-hooks/exhaustive-deps

  const feedbackCandidate = feedbackId ? candidates.find((c) => c.candidate_id === feedbackId) : null;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <h2 className="text-base font-semibold text-primary">HirePredict™ Outcomes</h2>
        <p className="text-[11px] text-primary/40 mt-0.5">
          Closed feedback loop — the model learns from every hire decision you record
        </p>
      </div>

      {/* Accuracy / collection state */}
      {accuracy && (
        <div className={`rounded-xl border px-4 py-3 ${accuracy.ready ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5"}`}>
          <div className="flex items-center justify-between">
            <span className={`text-xs font-semibold ${accuracy.ready ? "text-emerald-400" : "text-amber-400"}`}>
              {accuracy.ready ? "🎯 Model Active" : "📊 Collecting Data"}
            </span>
            <span className="font-mono text-[11px] text-primary/40">
              {accuracy.total_outcomes} / {accuracy.min_samples_required} outcomes
            </span>
          </div>
          {/* Progress bar */}
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-gridline/30">
            <div
              className={`h-full rounded-full transition-all ${accuracy.ready ? "bg-emerald-400" : "bg-amber-400"}`}
              style={{ width: `${Math.min(100, (accuracy.total_outcomes / accuracy.min_samples_required) * 100)}%` }}
            />
          </div>
          <p className="mt-1.5 text-[11px] text-primary/40">{accuracy.note}</p>
        </div>
      )}

      {/* Candidate table with predictions */}
      {candidates.length === 0 ? (
        <div className="flex items-center justify-center py-12">
          <p className="text-sm text-primary/30">Run the pipeline first.</p>
        </div>
      ) : (
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gridline/40 text-left text-[11px] font-mono uppercase tracking-wider text-primary/40">
                <th className="px-3 py-2">Candidate</th>
                <th className="w-20 px-3 py-2">Fit</th>
                <th className="w-28 px-3 py-2">Hire Prob.</th>
                <th className="w-20 px-3 py-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {enriched.map((c) => (
                <tr
                  key={c.candidate_id}
                  className="border-b border-gridline/20 hover:bg-surface-2/50 transition"
                >
                  <td className="px-3 py-2.5">
                    <div className="text-sm font-medium text-primary">{c.name ?? c.candidate_id}</div>
                    <div className="text-[11px] text-primary/40">{c.current_title ?? "—"}</div>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-xs text-primary/60">
                    {Math.round(c.score * 100)}
                  </td>
                  <td className="px-3 py-2.5">
                    {c.hire_probability !== undefined ? (
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-14 overflow-hidden rounded-full bg-gridline/30">
                          <div
                            className={`h-full rounded-full ${
                              c.hire_probability >= 0.70 ? "bg-emerald-400" :
                              c.hire_probability >= 0.45 ? "bg-amber-400" : "bg-red-400"
                            }`}
                            style={{ width: `${c.hire_probability * 100}%` }}
                          />
                        </div>
                        <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${LABEL_STYLE[c.hire_predict_label ?? "low"]}`}>
                          {Math.round((c.hire_probability ?? 0) * 100)}%
                        </span>
                      </div>
                    ) : (
                      <span className="text-[11px] text-primary/20 italic">
                        {loading ? "…" : "—"}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <button
                      onClick={() => setFeedbackId(feedbackId === c.candidate_id ? null : c.candidate_id)}
                      className="rounded-md border border-gridline/30 px-2 py-1 text-[10px] text-primary/50 hover:text-primary/80 hover:border-starlight/40 transition"
                    >
                      {feedbackId === c.candidate_id ? "Close" : "Record"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Inline feedback form */}
      {feedbackCandidate && lastJdId && (
        <div className="mt-2">
          <HireOutcomeForm
            candidate={feedbackCandidate}
            jdId={lastJdId}
            onSaved={() => {
              setFeedbackId(null);
              setTimeout(reload, 500);
            }}
          />
        </div>
      )}
    </div>
  );
}
