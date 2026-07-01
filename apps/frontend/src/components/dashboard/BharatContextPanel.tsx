/**
 * BharatContextPanel — Shows the Bharat Intelligence Layer's impact
 * on the current ranked shortlist.
 */
import { useState } from "react";
import type { BharatContextSummary } from "@polyhire/shared-types";

export function BharatContextPanel({ summary }: { summary: BharatContextSummary | null }) {
  const [expanded, setExpanded] = useState(false);
  if (!summary) return null;

  const adjustedPct = Math.round((summary.tier_adjusted_count / summary.total_candidates) * 100);
  const codeSwitchPct = Math.round(
    (summary.code_switch_detected_count / summary.total_candidates) * 100,
  );
  const informalPct = Math.round(
    (summary.informal_sector_count / summary.total_candidates) * 100,
  );
  const deltaSign = summary.avg_engagement_delta >= 0 ? "+" : "";

  return (
    <div className="overflow-hidden rounded-lg border border-gridline bg-surface">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-gridline/30"
      >
        <div className="flex items-center gap-2">
          <span className="text-lg text-starlight">🇮🇳</span>
          <span className="font-display text-sm text-starlight">Bharat Intelligence Layer</span>
        </div>
        <span className="font-mono text-xs text-primary/40">{expanded ? "▲" : "▼"}</span>
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-gridline px-4 pb-4">
          <p className="pt-3 text-xs text-primary/60">
            Context-aware normalization applied to all {summary.total_candidates} candidates.
          </p>

          <div className="space-y-1">
            <p className="text-xs uppercase tracking-wide text-primary/50">Candidate Geography</p>
            <div className="flex gap-2 font-mono text-xs">
              <span className="text-trust">T1: {summary.tier_1_count}</span>
              <span className="text-starlight">T2: {summary.tier_2_count}</span>
              <span className="text-alert/80">T3: {summary.tier_3_count}</span>
            </div>
            <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-gridline">
              <div
                className="h-full bg-trust"
                style={{ width: `${(summary.tier_1_count / summary.total_candidates) * 100}%` }}
              />
              <div
                className="h-full bg-starlight"
                style={{ width: `${(summary.tier_2_count / summary.total_candidates) * 100}%` }}
              />
              <div
                className="h-full bg-alert/80"
                style={{ width: `${(summary.tier_3_count / summary.total_candidates) * 100}%` }}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <BILMetric
              label="Engagement adjusted"
              value={`${adjustedPct}%`}
              subtitle={`avg delta ${deltaSign}${summary.avg_engagement_delta.toFixed(3)}`}
              color="text-starlight"
              module="BIL-1"
            />
            <BILMetric
              label="NIRF institutions matched"
              value={`${summary.nirf_matched_count}`}
              subtitle="of candidates"
              color="text-trust"
              module="BIL-2"
            />
            <BILMetric
              label="Code-switch detected"
              value={`${codeSwitchPct}%`}
              subtitle="of candidate resumes"
              color="text-purple-400"
              module="BIL-3"
            />
            <BILMetric
              label="Informal exp. translated"
              value={`${informalPct}%`}
              subtitle="of candidates"
              color="text-orange-400"
              module="BIL-4"
            />
          </div>

          <p className="pt-1 font-mono text-xs text-primary/30">
            Processed in {summary.processing_ms.toFixed(0)}ms
          </p>
        </div>
      )}
    </div>
  );
}

function BILMetric({
  label,
  value,
  subtitle,
  color,
  module,
}: {
  label: string;
  value: string;
  subtitle: string;
  color: string;
  module: string;
}) {
  return (
    <div className="rounded border border-gridline/50 bg-void p-2">
      <div className="mb-0.5 flex items-center justify-between">
        <span className="font-mono text-[10px] text-primary/40">{module}</span>
      </div>
      <p className={`font-mono text-base font-bold ${color}`}>{value}</p>
      <p className="text-[10px] text-primary/50">{label}</p>
      <p className="text-[10px] text-primary/30">{subtitle}</p>
    </div>
  );
}
