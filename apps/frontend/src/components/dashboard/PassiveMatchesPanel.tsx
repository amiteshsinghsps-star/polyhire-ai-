/**
 * §23.6 — Passive Talent Matches Panel.
 *
 * Displays candidates flagged as strong latent matches for recurring role
 * archetypes, even before a matching role is posted.
 */
import { useEffect, useState } from "react";
import { fetchPassiveMatches } from "../../lib/api";
import { useAppDispatch } from "../../store/hooks";
import { setPassiveMatches, setError } from "../../store/slices/enterpriseSlice";
import type { PassiveMatchesResponse } from "@polyhire/shared-types";

export function PassiveMatchesPanel() {
  const dispatch = useAppDispatch();
  const [loading, setLoading] = useState(false);
  const [matches, setMatches] = useState<PassiveMatchesResponse["flags"]>([]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchPassiveMatches()
      .then((res) => {
        if (cancelled) return;
        const data = res as PassiveMatchesResponse;
        setMatches(data.flags);
        dispatch(setPassiveMatches(data.flags));
      })
      .catch((err) => {
        dispatch(setError(err instanceof Error ? err.message : "Passive matches failed"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dispatch]);

  return (
    <div className="panel space-y-3 p-4">
      <h3 className="font-display text-sm text-starlight">Passive Talent Pool</h3>
      <p className="text-xs text-primary/50">
        Candidates matching recurring role archetypes — proactive outreach candidates.
      </p>
      {loading ? (
        <p className="text-xs text-primary/40">Scanning pool...</p>
      ) : matches.length === 0 ? (
        <p className="text-xs text-primary/40">
          No passive matches yet. Run a pipeline first to seed role archetypes.
        </p>
      ) : (
        <ul className="space-y-2">
          {matches.slice(0, 10).map((m, i) => (
            <li
              key={i}
              className="flex flex-col gap-1 border-l-2 border-trust/40 pl-3 text-xs"
            >
              <div className="flex justify-between">
                <span className="font-mono text-primary/80">{m.candidate_id}</span>
                <span className="font-mono text-trust">{m.similarity.toFixed(3)}</span>
              </div>
              <span className="text-primary/60">{m.matched_archetype}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
