/**
 * §23.5 — Diversity Toggle.
 *
 * Opt-in diversity-aware re-ranking. Defaults OFF. When enabled, runs an MMR
 * re-ranking pass and shows the change percentage transparently.
 */
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import { diversifyShortlist } from "../../lib/api";
import { toggleDiversity, setDiversityReport, setError } from "../../store/slices/enterpriseSlice";
import type { DiversifyResponse } from "@polyhire/shared-types";

export function DiversityToggle({ candidateIds, scores }: { candidateIds: string[]; scores: number[] }) {
  const dispatch = useAppDispatch();
  const { diversityActive, diversityReport } = useAppSelector((s) => s.enterprise);

  async function handleToggle() {
    const next = !diversityActive;
    dispatch(toggleDiversity(next));
    if (next && candidateIds.length > 0) {
      try {
        const res = (await diversifyShortlist({
          candidate_ids: candidateIds,
          relevance_scores: scores,
          lambda_param: 0.7,
          top_k: Math.min(20, candidateIds.length),
        })) as DiversifyResponse;
        dispatch(setDiversityReport(diversityReport ?? null));
        dispatch(
          setDiversityReport({
            candidates_reordered_pct: res.diversity_report.candidates_reordered_pct,
            top_5_unchanged: res.diversity_report.top_5_unchanged,
          }),
        );
      } catch (err) {
        dispatch(setError(err instanceof Error ? err.message : "Diversify failed"));
      }
    } else {
      dispatch(setDiversityReport(null));
    }
  }

  return (
    <div className="panel space-y-2 p-4">
      <label className="flex cursor-pointer items-center justify-between">
        <span className="text-sm">Diversity-aware re-ranking</span>
        <input
          type="checkbox"
          checked={diversityActive}
          onChange={handleToggle}
          className="h-4 w-4 accent-starlight"
        />
      </label>
      <p className="text-xs text-primary/50">
        Off by default. Pure relevance ranking unless explicitly enabled.
      </p>
      {diversityReport && (
        <p className="font-mono text-xs text-trust">
          {diversityReport.candidates_reordered_pct}% reordered
          {diversityReport.top_5_unchanged ? " — top 5 unchanged" : " — top 5 affected"}
        </p>
      )}
    </div>
  );
}
