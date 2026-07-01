/**
 * IntentMatrix — 2×2 Fit × Intent priority quadrant grid.
 *
 * Q1 (High Fit, High Intent)  → Contact Now  🔥
 * Q2 (High Fit, Low Intent)   → Nurture       🌱
 * Q3 (Low Fit,  High Intent)  → Future Role   🔭
 * Q4 (Low Fit,  Low Intent)   → Archive       📦
 *
 * Each quadrant shows candidate avatars/IDs and a recommended action.
 */
import { useState, useEffect } from "react";
import { useAppSelector } from "../../store/hooks";
import { buildPriorityMatrix } from "../../lib/api";
import { IntentBadge, type IntentLabel } from "./IntentBadge";
import type { RankedCandidate } from "@polyhire/shared-types";

interface MatrixData {
  Q1_contact_now:  string[];
  Q2_nurture:      string[];
  Q3_future_role:  string[];
  Q4_archive:      string[];
}

const QUADRANTS = [
  {
    key:    "Q1_contact_now" as const,
    label:  "Contact Now",
    intent: "hot" as IntentLabel,
    desc:   "High fit · High intent — reach out in 24h",
    color:  "border-red-500/30 bg-red-500/5",
    header: "bg-red-500/15",
    icon:   "🔥",
  },
  {
    key:    "Q2_nurture" as const,
    label:  "Nurture",
    intent: "warm" as IntentLabel,
    desc:   "High fit · Waiting for their window",
    color:  "border-amber-500/30 bg-amber-500/5",
    header: "bg-amber-500/15",
    icon:   "🌱",
  },
  {
    key:    "Q3_future_role" as const,
    label:  "Future Role",
    intent: "cool" as IntentLabel,
    desc:   "Moving soon · Different level needed",
    color:  "border-sky-500/30 bg-sky-500/5",
    header: "bg-sky-500/15",
    icon:   "🔭",
  },
  {
    key:    "Q4_archive" as const,
    label:  "Archive",
    intent: "dormant" as IntentLabel,
    desc:   "Low fit · Low intent — revisit in 90 days",
    color:  "border-zinc-500/30 bg-zinc-500/5",
    header: "bg-zinc-500/15",
    icon:   "📦",
  },
];

function candidateLabel(id: string, candidates: RankedCandidate[]): string {
  const c = candidates.find((x) => x.candidate_id === id);
  return c?.name ?? id.slice(0, 12);
}

export function IntentMatrix() {
  const candidates = useAppSelector((s) => s.shortlist.candidates);
  const structuredJd = useAppSelector((s) => s.pipeline.structuredJd);

  const [matrix, setMatrix]   = useState<MatrixData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState<string | null>(null);

  useEffect(() => {
    if (candidates.length === 0) return;

    setLoading(true);
    setError(null);

    const payload = {
      candidates: candidates.map((c) => ({
        ...c,
        id: c.candidate_id,
        fusion_score: c.score,
      })),
      structured_jd: structuredJd ?? undefined,
    };

    buildPriorityMatrix(payload)
      .then((data) => setMatrix(data as MatrixData))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [candidates, structuredJd]);

  if (candidates.length === 0) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-sm text-primary/30">Run the pipeline to populate the intent matrix.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-primary">
            CandidateIntent™ Priority Matrix
          </h2>
          <p className="text-[11px] text-primary/40 mt-0.5">
            2×2 grid: Fit Score × Mobility Intent — tells you who to call TODAY
          </p>
        </div>
        {loading && (
          <span className="text-[11px] font-mono text-primary/30 animate-pulse">
            Scoring intent…
          </span>
        )}
        {error && (
          <span className="text-[11px] text-red-400">{error}</span>
        )}
      </div>

      {/* Axis labels */}
      <div className="relative">
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 text-[10px] text-primary/30 uppercase tracking-widest">
          HIGH INTENT →
        </div>
        <div className="absolute left-0 top-1/2 -translate-y-1/2 -rotate-90 text-[10px] text-primary/30 uppercase tracking-widest">
          HIGH FIT ↑
        </div>
      </div>

      {/* 2×2 Grid */}
      <div className="grid grid-cols-2 gap-3 pt-4 pl-4">
        {QUADRANTS.map((q) => {
          const ids: string[] = matrix?.[q.key] ?? [];
          return (
            <div key={q.key} className={`rounded-xl border ${q.color} overflow-hidden`}>
              <div className={`flex items-center gap-2 px-3 py-2 ${q.header}`}>
                <span className="text-base">{q.icon}</span>
                <div>
                  <div className="text-xs font-semibold text-primary">{q.label}</div>
                  <div className="text-[10px] text-primary/40">{q.desc}</div>
                </div>
                <span className="ml-auto font-mono text-sm font-bold text-primary/60">
                  {ids.length}
                </span>
              </div>

              <div className="p-3 space-y-1.5 min-h-[72px]">
                {loading && (
                  <div className="flex gap-1">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="h-5 w-16 rounded bg-gridline/20 animate-pulse" />
                    ))}
                  </div>
                )}
                {!loading && ids.length === 0 && (
                  <p className="text-[11px] text-primary/20 italic">No candidates here</p>
                )}
                {!loading && ids.map((id) => (
                  <div key={id} className="flex items-center gap-1.5">
                    <div className="h-5 w-5 rounded-full bg-gridline/40 flex-shrink-0" />
                    <span className="text-xs text-primary/70 truncate">
                      {candidateLabel(id, candidates)}
                    </span>
                    <IntentBadge label={q.intent} />
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="rounded-lg border border-gridline/20 bg-surface/40 px-4 py-3 text-[11px] text-primary/40">
        <span className="font-semibold text-primary/60">How to act: </span>
        Q1 → call now · Q2 → nurture sequence · Q3 → future pipeline · Q4 → set a 90-day reminder
      </div>
    </div>
  );
}
