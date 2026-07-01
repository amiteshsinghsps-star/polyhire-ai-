/**
 * §23.2 — Counterfactual Panel.
 *
 * Shows minimal feature changes that would improve a candidate's rank.
 * Triggered on demand via a button click.
 */
import { useState } from "react";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import { fetchCounterfactual } from "../../lib/api";
import { setCounterfactuals, setError } from "../../store/slices/enterpriseSlice";
import type { CounterfactualResponse } from "@polyhire/shared-types";

const DEFAULT_FEATURES: Record<string, number> = {
  embedding_similarity: 0.5,
  rerank_score: 0.4,
  years_experience_match: 0.6,
  skill_overlap_ratio: 0.5,
  recency_of_activity: 0.7,
  career_trajectory_slope: 0.3,
  engagement_score: 0.6,
  trust_score: 0.8,
};

export function CounterfactualPanel({ candidateId }: { candidateId: string }) {
  const dispatch = useAppDispatch();
  const [loading, setLoading] = useState(false);
  const cfs = useAppSelector((s) => s.enterprise.counterfactuals[candidateId]);

  async function handleFetch() {
    setLoading(true);
    try {
      const res = (await fetchCounterfactual(candidateId, {
        current_features: DEFAULT_FEATURES,
        target_score: 0.8,
      })) as CounterfactualResponse;
      const mapped = res.human_readable.map((text, i) => ({
        changes: res.counterfactuals[i]?.changes ?? {},
        resultingScore: res.counterfactuals[i]?.resulting_score ?? 0.8,
        humanReadable: text,
      }));
      dispatch(setCounterfactuals({ candidateId, cfs: mapped }));
    } catch (err) {
      dispatch(setError(err instanceof Error ? err.message : "Counterfactual failed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel space-y-2 p-4">
      <h3 className="font-display text-sm text-starlight">What would change this rank?</h3>
      {!cfs && (
        <button
          onClick={handleFetch}
          disabled={loading}
          className="rounded bg-starlight/10 px-3 py-1.5 text-xs text-starlight hover:bg-starlight/20"
        >
          {loading ? "Computing..." : "Show me"}
        </button>
      )}
      {cfs?.map((cf, i) => (
        <p key={i} className="text-sm text-primary/80">
          {cf.humanReadable}
        </p>
      ))}
    </div>
  );
}
