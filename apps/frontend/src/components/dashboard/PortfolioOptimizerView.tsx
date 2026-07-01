/**
 * §23.3 — Portfolio Optimizer View.
 *
 * Runs cross-role candidate assignment optimization. In demo mode, runs on a
 * synthetic 3-role score matrix; in production, accepts real role definitions.
 */
import { useState } from "react";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import { optimizePortfolio } from "../../lib/api";
import { setPortfolioResults, setError } from "../../store/slices/enterpriseSlice";
import type { PortfolioOptimizeResponse } from "@polyhire/shared-types";

const DEMO_ROLES = [
  { id: "role_backend", title: "Backend Engineer", slots: 3 },
  { id: "role_frontend", title: "Frontend Engineer", slots: 3 },
  { id: "role_data", title: "Data Scientist", slots: 2 },
];

// Synthetic demo score matrix {candidate_id: {role_id: score}}
function buildDemoMatrix(): Record<string, Record<string, number>> {
  const matrix: Record<string, Record<string, number>> = {};
  const cands = Array.from({ length: 15 }, (_, i) => `cand_${String(i).padStart(4, "0")}`);
  for (const cid of cands) {
    const seed = parseInt(cid.slice(-2), 10) || 1;
    matrix[cid] = {
      role_backend: 0.4 + ((seed * 7) % 60) / 100,
      role_frontend: 0.4 + ((seed * 13) % 60) / 100,
      role_data: 0.4 + ((seed * 19) % 60) / 100,
    };
  }
  return matrix;
}

export function PortfolioOptimizerView() {
  const dispatch = useAppDispatch();
  const [loading, setLoading] = useState(false);
  const assignments = useAppSelector((s) => s.enterprise.portfolioAssignments);
  const comparison = useAppSelector((s) => s.enterprise.portfolioComparison);

  async function runOptimization() {
    setLoading(true);
    try {
      const scoreMatrix = buildDemoMatrix();
      const slots = Object.fromEntries(DEMO_ROLES.map((r) => [r.id, r.slots]));
      const res = (await optimizePortfolio(scoreMatrix, slots)) as PortfolioOptimizeResponse;
      dispatch(
        setPortfolioResults({
          assignments: res.assignments.map((a) => ({
            candidateId: a.candidate_id,
            assignedRole: a.assigned_role,
            score: a.score,
          })),
          comparison: {
            naiveTotalScore: res.comparison.naive_total_score,
            optimizedTotalScore: res.comparison.optimized_total_score,
            naiveUniqueCandidatesUsed: res.comparison.naive_unique_candidates_used,
            optimizedUniqueCandidatesUsed: res.comparison.optimized_unique_candidates_used,
            candidatePoolUtilizationGain: res.comparison.candidate_pool_utilization_gain,
          },
        }),
      );
    } catch (err) {
      dispatch(setError(err instanceof Error ? err.message : "Optimization failed"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel space-y-3 p-4">
      <h3 className="font-display text-sm text-starlight">Cross-Role Portfolio Optimization</h3>
      <p className="text-xs text-primary/60">
        Optimizes candidate-to-role assignment across all {DEMO_ROLES.length} demo roles simultaneously.
      </p>
      <button
        onClick={runOptimization}
        disabled={loading}
        className="rounded bg-starlight px-3 py-1.5 text-xs font-medium text-void"
      >
        {loading ? "Optimizing..." : "Optimize across all roles"}
      </button>

      {comparison && (
        <div className="font-mono text-xs text-trust">
          Candidate pool utilization: {comparison.naiveUniqueCandidatesUsed} →{" "}
          {comparison.optimizedUniqueCandidatesUsed} unique people engaged
          {comparison.candidatePoolUtilizationGain > 0 && (
            <span className="text-starlight"> (+{comparison.candidatePoolUtilizationGain})</span>
          )}
        </div>
      )}

      <ul className="space-y-1">
        {assignments.map((a, i) => (
          <li key={i} className="flex justify-between text-sm">
            <span className="text-primary/80">{a.candidateId}</span>
            <span className="text-primary/60">→ {a.assignedRole}</span>
            <span className="font-mono text-trust">{a.score.toFixed(2)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
