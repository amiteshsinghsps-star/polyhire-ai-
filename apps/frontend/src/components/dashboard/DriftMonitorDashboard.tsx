/**
 * §23.8 — Drift Monitor Dashboard.
 *
 * Surfaces the most recent model drift check result. Shows whether feature
 * distributions have shifted from the training-time reference, with an
 * actionable recommendation.
 */
import { useEffect, useState } from "react";
import { useAppDispatch } from "../../store/hooks";
import { fetchDriftStatus } from "../../lib/api";
import { setDriftStatus, setError } from "../../store/slices/enterpriseSlice";
import type { DriftStatus } from "@polyhire/shared-types";

export function DriftMonitorDashboard() {
  const dispatch = useAppDispatch();
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<DriftStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchDriftStatus()
      .then((res) => {
        if (cancelled) return;
        const data = res as DriftStatus;
        setStatus(data);
        dispatch(setDriftStatus(data));
      })
      .catch((err) => {
        dispatch(setError(err instanceof Error ? err.message : "Drift check failed"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dispatch]);

  if (loading) return <div className="panel p-4 text-xs text-primary/40">Checking drift...</div>;
  if (!status) return null;

  const drift = status.drift_detected;

  return (
    <div
      className={`rounded-lg border p-4 ${
        drift ? "border-alert bg-alert/5" : "border-trust bg-trust/5"
      }`}
    >
      <h3 className="font-display text-sm">
        {drift ? "⚠ Model Drift Detected" : "✓ Model Healthy"}
      </h3>
      <p className="mt-1 text-xs text-primary/70">{status.recommendation}</p>
      {status.drifted_features.length > 0 && (
        <div className="mt-2">
          <p className="mb-1 text-[10px] font-mono text-primary/40">DRIFTED FEATURES</p>
          <div className="flex flex-wrap gap-1">
            {status.drifted_features.map((f) => (
              <span
                key={f}
                className="rounded-full bg-alert/15 px-2 py-0.5 text-[10px] font-mono text-alert"
              >
                {f}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
