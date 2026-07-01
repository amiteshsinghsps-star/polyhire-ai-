/**
 * ShortlistTable — ranked candidate list with inline explanations.
 */
import { useAppSelector, useAppDispatch } from "../../store/hooks";
import { selectNode } from "../../store/slices/galaxySlice";
import { setTab } from "../../store/slices/uiSlice";
import { BharatBadge } from "./BharatBadge";
import type { RankedCandidate } from "@polyhire/shared-types";

export function ShortlistTable() {
  const candidates = useAppSelector((s) => s.shortlist.candidates);
  const selectedId = useAppSelector((s) => s.shortlist.selectedCandidateId);
  const dispatch = useAppDispatch();

  if (candidates.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-sm text-primary/30">No candidates ranked yet.</p>
      </div>
    );
  }

  return (
    <div className="starfield-scrollbar overflow-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gridline/40 text-left text-[11px] font-mono uppercase tracking-wider text-primary/40">
            <th className="w-12 px-3 py-2">#</th>
            <th className="px-3 py-2">Candidate</th>
            <th className="w-20 px-3 py-2">Score</th>
            <th className="w-20 px-3 py-2">Trust</th>
            <th className="w-16 px-3 py-2">Skills</th>
            <th className="px-3 py-2">Why this rank?</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => (
            <CandidateRow
              key={c.candidate_id}
              candidate={c}
              isSelected={c.candidate_id === selectedId}
              onSelect={() => {
                dispatch(selectNode(c.candidate_id));
                dispatch(setTab("galaxy"));
              }}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CandidateRow({
  candidate: c,
  isSelected,
  onSelect,
}: {
  candidate: RankedCandidate;
  isSelected: boolean;
  onSelect: () => void;
}) {
  return (
    <tr
      onClick={onSelect}
      className={`cursor-pointer border-b border-gridline/20 transition hover:bg-surface-2/60 ${
        isSelected ? "bg-starlight/8" : ""
      }`}
    >
      <td className="px-3 py-2.5 font-mono">
        <span
          className={`inline-flex h-6 w-6 items-center justify-center rounded-md text-[11px] font-bold ${
            c.rank <= 3
              ? "bg-starlight/20 text-starlight"
              : c.rank <= 10
                ? "bg-trust/15 text-trust"
                : "bg-gridline/30 text-primary/50"
          }`}
        >
          {c.rank}
        </span>
      </td>
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-full bg-gridline/40" />
          <div>
            <div className="text-sm font-medium text-primary">
              {c.name ?? c.candidate_id}
            </div>
            <div className="flex items-center gap-1">
              <BharatBadge adjustment={c.bharat_adjustment} />
            </div>
            <div className="text-[11px] text-primary/40">
              {c.current_title ?? "—"}
            </div>
          </div>
        </div>
      </td>
      <td className="px-3 py-2.5">
        <ScoreBar score={c.score} />
      </td>
      <td className="px-3 py-2.5">
        <TrustBadge score={c.trust_score} />
      </td>
      <td className="px-3 py-2.5">
        <SkillCount count={c.skills?.length ?? 0} />
      </td>
      <td className="max-w-xs px-3 py-2.5 text-[11px] leading-relaxed text-primary/50">
        {c.explanation}
      </td>
    </tr>
  );
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 80 ? "bg-starlight" : pct >= 50 ? "bg-trust" : "bg-primary/40";
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-xs text-primary/60">{pct}</span>
      <div className="h-1 w-10 overflow-hidden rounded-full bg-gridline/40">
        <div
          className={`h-full rounded-full ${color} transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function TrustBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const level =
    pct >= 95 ? "high" : pct >= 70 ? "medium" : "low";
  return (
    <span
      className={`badge ${
        level === "high"
          ? "badge-trust"
          : level === "medium"
            ? "badge-neutral"
            : "badge-alert"
      }`}
    >
      {pct}%
    </span>
  );
}

function SkillCount({ count }: { count: number }) {
  return (
    <span className="font-mono text-xs text-primary/40">{count}</span>
  );
}
