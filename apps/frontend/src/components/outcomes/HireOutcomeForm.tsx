/**
 * HireOutcomeForm — recruiter feedback form for the closed-loop system.
 *
 * Lets recruiters record:
 *   1. Was this candidate hired?
 *   2. Are they still at the company after 30 days?
 *
 * Submitted data trains HirePredict™ incrementally.
 */
import { useState } from "react";
import { submitHireFeedback } from "../../lib/api";
import type { RankedCandidate } from "@polyhire/shared-types";

type Status = "idle" | "saving" | "saved" | "error";

export function HireOutcomeForm({
  candidate,
  jdId,
  onSaved,
}: {
  candidate: RankedCandidate;
  jdId: string;
  onSaved?: () => void;
}) {
  const [hired, setHired]           = useState<boolean | null>(null);
  const [retained, setRetained]     = useState<boolean | null>(null);
  const [status, setStatus]         = useState<Status>("idle");
  const [retrained, setRetrained]   = useState(false);

  async function handleSubmit() {
    if (hired === null) return;
    setStatus("saving");
    try {
      const result = await submitHireFeedback({
        jd_id:        jdId,
        candidate_id: candidate.candidate_id,
        hired,
        retained_30d: retained ?? undefined,
        features: {
          embedding_similarity:    candidate.score ?? 0.5,
          rerank_score:            (candidate as Record<string, number>).rerank_score ?? 0.5,
          years_experience_match:  (candidate as Record<string, number>).years_experience_match ?? 0.5,
          skill_overlap_ratio:     (candidate as Record<string, number>).skill_overlap_ratio ?? 0.5,
          recency_of_activity:     (candidate as Record<string, number>).recency_of_activity ?? 0.5,
          career_trajectory_slope: (candidate as Record<string, number>).career_trajectory_slope ?? 0.5,
          engagement_score:        (candidate as Record<string, number>).engagement_score ?? 0.5,
          trust_score:             candidate.trust_score ?? 1.0,
          intent_score:            (candidate as Record<string, number>).intent_score ?? 0.5,
        },
      });
      setStatus("saved");
      if ((result as Record<string, unknown>).retrain_triggered) setRetrained(true);
      onSaved?.();
    } catch {
      setStatus("error");
    }
  }

  if (status === "saved") {
    return (
      <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/8 px-4 py-3 text-sm text-emerald-400">
        ✅ Outcome saved{retrained ? " — model retrained with new data!" : "."}
        <span className="ml-1 text-emerald-400/50 text-[11px]">HirePredict™ is learning.</span>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gridline/30 bg-surface/60 p-4 space-y-4">
      {/* Candidate header */}
      <div className="flex items-center gap-2">
        <div className="h-8 w-8 rounded-full bg-gridline/40" />
        <div>
          <div className="text-sm font-medium text-primary">{candidate.name ?? candidate.candidate_id}</div>
          <div className="text-[11px] text-primary/40">{candidate.current_title ?? "—"}</div>
        </div>
        <div className="ml-auto font-mono text-lg font-bold text-starlight/70">
          {Math.round(candidate.score * 100)}
        </div>
      </div>

      {/* Hired? */}
      <div>
        <label className="text-[11px] font-mono uppercase tracking-wider text-primary/40">
          Was this candidate hired?
        </label>
        <div className="mt-1.5 flex gap-2">
          {[true, false].map((val) => (
            <button
              key={String(val)}
              onClick={() => setHired(val)}
              className={`rounded-lg px-4 py-1.5 text-xs font-medium transition ${
                hired === val
                  ? val
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                    : "bg-red-500/20 text-red-400 border border-red-500/40"
                  : "bg-surface border border-gridline/30 text-primary/40 hover:text-primary/60"
              }`}
            >
              {val ? "✅ Hired" : "❌ Not Hired"}
            </button>
          ))}
        </div>
      </div>

      {/* 30-day retention (only if hired) */}
      {hired === true && (
        <div>
          <label className="text-[11px] font-mono uppercase tracking-wider text-primary/40">
            Still at company after 30 days?
          </label>
          <div className="mt-1.5 flex gap-2">
            {[true, false, null].map((val) => (
              <button
                key={String(val)}
                onClick={() => setRetained(val)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  retained === val
                    ? "bg-starlight/15 text-starlight border border-starlight/30"
                    : "bg-surface border border-gridline/30 text-primary/40 hover:text-primary/60"
                }`}
              >
                {val === true ? "Yes" : val === false ? "No" : "Unknown"}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={hired === null || status === "saving"}
        className={`w-full rounded-lg py-2 text-xs font-semibold transition ${
          hired !== null
            ? "bg-starlight/20 text-starlight hover:bg-starlight/30 border border-starlight/30"
            : "bg-gridline/20 text-primary/20 cursor-not-allowed"
        }`}
      >
        {status === "saving" ? "Saving…" : "Submit Outcome to HirePredict™"}
      </button>

      {status === "error" && (
        <p className="text-[11px] text-red-400">Failed to save. ML service may be offline.</p>
      )}
    </div>
  );
}
