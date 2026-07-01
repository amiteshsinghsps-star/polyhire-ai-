/**
 * §23.4 — Audit Trail Viewer.
 *
 * Fetches and displays the immutable hash-chained audit ledger for a JD,
 * plus a chain-integrity verification badge.
 */
import { useEffect, useState } from "react";
import { fetchAuditTrail, verifyAuditChain } from "../../lib/api";
import { useAppDispatch } from "../../store/hooks";
import { setAuditTrail, setAuditChainValid, setError } from "../../store/slices/enterpriseSlice";
import type { AuditTrailResponse, AuditVerifyResponse } from "@polyhire/shared-types";

export function AuditTrailViewer({ jdId }: { jdId: string }) {
  const dispatch = useAppDispatch();
  const [loading, setLoading] = useState(true);
  const [trail, setTrail] = useState<AuditTrailResponse["entries"]>([]);
  const [valid, setValid] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      fetchAuditTrail(jdId).catch(() => null),
      verifyAuditChain(jdId).catch(() => null),
    ])
      .then(([trailRes, verifyRes]) => {
        if (cancelled) return;
        if (trailRes) {
          const data = trailRes as AuditTrailResponse;
          setTrail(data.entries);
          dispatch(setAuditTrail(data.entries));
        }
        if (verifyRes) {
          const data = verifyRes as AuditVerifyResponse;
          setValid(data.chain_valid);
          dispatch(setAuditChainValid(data.chain_valid));
        }
      })
      .catch((err) => {
        dispatch(setError(err instanceof Error ? err.message : "Audit fetch failed"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [jdId, dispatch]);

  return (
    <div className="panel space-y-2 p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-sm text-starlight">Compliance Audit Trail</h3>
        {valid !== null && (
          <span className={`font-mono text-[10px] ${valid ? "text-trust" : "text-alert"}`}>
            {valid ? "✓ Chain verified" : "⚠ Integrity check failed"}
          </span>
        )}
      </div>
      {loading ? (
        <p className="text-xs text-primary/40">Loading audit trail...</p>
      ) : trail.length === 0 ? (
        <p className="text-xs text-primary/40">No audit entries yet for this JD.</p>
      ) : (
        <table className="w-full text-xs font-mono">
          <thead className="text-primary/50">
            <tr>
              <th className="text-left">Rank</th>
              <th className="text-left">Candidate</th>
              <th className="text-left">Score</th>
              <th className="text-left">Hash</th>
            </tr>
          </thead>
          <tbody>
            {trail.slice(0, 20).map((entry) => (
              <tr key={entry.entry_hash}>
                <td>{entry.rank}</td>
                <td className="truncate">{entry.candidate_id}</td>
                <td>{entry.fusion_score.toFixed(3)}</td>
                <td className="max-w-[80px] truncate">{entry.entry_hash.slice(0, 12)}…</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
