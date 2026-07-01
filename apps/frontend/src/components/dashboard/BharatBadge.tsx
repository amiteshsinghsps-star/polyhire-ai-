/**
 * BharatBadge — Shown next to a candidate when BIL made a meaningful adjustment.
 */
import { useState } from "react";
import type { CandidateBharatAdjustment } from "@polyhire/shared-types";

export function BharatBadge({ adjustment }: { adjustment: CandidateBharatAdjustment | null | undefined }) {
  const [open, setOpen] = useState(false);
  if (!adjustment) return null;

  const hasAdjustment =
    adjustment.tier_adjusted ||
    adjustment.code_switch_detected ||
    adjustment.informal_sector_score > 0.1 ||
    adjustment.skills_added_by_bil3.length > 0 ||
    adjustment.skills_added_by_bil4.length > 0;

  if (!hasAdjustment) return null;

  return (
    <div className="relative inline-block">
      <button
        onClick={(e) => {
          e.stopPropagation();
          setOpen(!open);
        }}
        className="rounded border border-starlight/30 bg-starlight/15 px-1.5 py-0.5 font-mono text-[10px] text-starlight transition-colors hover:bg-starlight/25"
        title="Bharat Intelligence Layer applied"
      >
        🇮🇳 BIL
      </button>

      {open && (
        <div
          className="absolute left-0 top-full z-50 mt-1 w-72 space-y-2 rounded-lg border border-gridline bg-surface p-3 text-xs shadow-xl"
          onClick={(e) => e.stopPropagation()}
        >
          <p className="font-display text-sm text-starlight">Bharat Intelligence Layer</p>
          <p className="text-[10px] text-primary/60">
            This candidate&apos;s signals were context-adjusted for their India-specific background.
          </p>

          {adjustment.tier_adjusted && (
            <BILRow
              module="BIL-1"
              label={`${adjustment.bharat_tier.replace("_", " ").toUpperCase()} city engagement normalized`}
              detail={`Engagement score adjusted ${adjustment.engagement_delta >= 0 ? "+" : ""}${adjustment.engagement_delta.toFixed(3)} to reflect regional platform adoption`}
              color="text-starlight"
            />
          )}

          {adjustment.institution_matched && (
            <BILRow
              module="BIL-2"
              label={`NIRF institution score: ${adjustment.institution_score.toFixed(2)}`}
              detail="Mapped to NIRF 2025 rankings — India-calibrated prestige signal"
              color="text-trust"
            />
          )}

          {adjustment.code_switch_detected && (
            <BILRow
              module="BIL-3"
              label={`Code-switch detected${adjustment.skills_added_by_bil3.length > 0 ? ` · +${adjustment.skills_added_by_bil3.length} skills` : ""}`}
              detail={
                adjustment.skills_added_by_bil3.length > 0
                  ? `Found: ${adjustment.skills_added_by_bil3.slice(0, 3).join(", ")}`
                  : "Bilingual resume text normalized"
              }
              color="text-purple-400"
            />
          )}

          {adjustment.informal_sector_score > 0.1 && (
            <BILRow
              module="BIL-4"
              label={`Informal sector score: ${adjustment.informal_sector_score.toFixed(2)}`}
              detail={adjustment.informal_explanation}
              color="text-orange-400"
            />
          )}

          <button
            onClick={() => setOpen(false)}
            className="pt-1 text-[10px] text-primary/30 hover:text-primary/60"
          >
            Close
          </button>
        </div>
      )}
    </div>
  );
}

function BILRow({
  module,
  label,
  detail,
  color,
}: {
  module: string;
  label: string;
  detail: string;
  color: string;
}) {
  return (
    <div className="space-y-0.5 border-l-2 border-gridline pl-2">
      <div className="flex items-center gap-1">
        <span className={`font-mono text-[10px] ${color}`}>{module}</span>
        <span className="text-[10px] text-primary/80">{label}</span>
      </div>
      <p className="text-[10px] text-primary/40">{detail}</p>
    </div>
  );
}
