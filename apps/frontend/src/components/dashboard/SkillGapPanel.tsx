/**
 * SkillGapPanel — near-miss candidate development reports.
 */
import { useState } from "react";
import { useAppSelector } from "../../store/hooks";
import type { SkillGapReport } from "@polyhire/shared-types";

export function SkillGapPanel() {
  const reports = useAppSelector((s) => s.shortlist.nearMissSkillGaps);

  if (reports.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-sm text-primary/30">
          Skill-gap reports appear for near-miss candidates (rank 21–40) after a JD run.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3 starfield-scrollbar overflow-auto px-1 py-2">
      <p className="px-2 text-xs font-mono text-primary/40">
        {reports.length} near-miss candidates with development recommendations
      </p>
      {reports.map((r) => (
        <SkillGapCard key={r.candidate_id} report={r} />
      ))}
    </div>
  );
}

function SkillGapCard({ report }: { report: SkillGapReport }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      className="panel cursor-pointer transition hover:bg-surface-2/40"
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-starlight/15">
            <span className="text-[10px] font-bold text-starlight">⚡</span>
          </div>
          <div>
            <div className="text-sm font-medium text-primary">
              {report.name ?? report.candidate_id}
            </div>
            <div className="text-[10px] text-primary/40">
              {report.candidate_id}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {report.missing_skills.length > 0 && (
            <div className="flex gap-1">
              {report.missing_skills.slice(0, 3).map((s) => (
                <span key={s} className="badge badge-neutral">{s}</span>
              ))}
              {report.missing_skills.length > 3 && (
                <span className="badge badge-neutral">+{report.missing_skills.length - 3}</span>
              )}
            </div>
          )}
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            className={`text-primary/40 transition-transform ${expanded ? "rotate-180" : ""}`}
          >
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </div>
      </div>
      {expanded && (
        <div className="border-t border-gridline/30 px-4 py-3">
          <div className="whitespace-pre-wrap text-xs leading-relaxed text-primary/60">
            {report.report}
          </div>
        </div>
      )}
    </div>
  );
}
