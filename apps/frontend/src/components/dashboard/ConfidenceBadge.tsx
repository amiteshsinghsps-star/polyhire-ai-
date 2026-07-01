/**
 * §23.1 — Confidence Badge.
 *
 * Displays calibrated confidence interval per candidate. Shows "Borderline — review"
 * for wide-bands and a confidence tag for tight ones.
 */
import { useEffect, useState } from "react";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import { fetchUncertainty } from "../../lib/api";
import { setUncertaintyBand, setLoading } from "../../store/slices/enterpriseSlice";
import type { UncertaintyResponse } from "@polyhire/shared-types";

export function ConfidenceBadge({
  candidateId,
  features,
}: {
  candidateId: string;
  features?: Record<string, number>;
}) {
  const dispatch = useAppDispatch();
  const band = useAppSelector((s) => s.enterprise.uncertaintyBands[candidateId]);
  const [loading, setLocalLoading] = useState(false);

  useEffect(() => {
    if (band || !features) return;
    setLocalLoading(true);
    dispatch(setLoading({ key: `uncertainty-${candidateId}`, value: true }));
    fetchUncertainty(candidateId, features)
      .then((res) => {
        const data = res as UncertaintyResponse;
        if (data.bands && data.bands.length > 0) {
          const b = data.bands[0];
          dispatch(
            setUncertaintyBand({
              candidateId,
              pointEstimate: b.point_estimate,
              lowerBound: b.lower_bound,
              upperBound: b.upper_bound,
              confidenceWidth: b.confidence_width,
              isHighConfidence: b.is_high_confidence,
            }),
          );
        }
      })
      .catch(() => {
        /* feature may be unavailable */
      })
      .finally(() => {
        setLocalLoading(false);
        dispatch(setLoading({ key: `uncertainty-${candidateId}`, value: false }));
      });
  }, [band, candidateId, features, dispatch]);

  if (loading) return <span className="text-[10px] font-mono text-primary/30">…</span>;
  if (!band) return null;

  return band.isHighConfidence ? (
    <span className="rounded-full bg-trust/20 px-2 py-0.5 text-[10px] font-mono text-trust">
      ±{(band.upperBound - band.lowerBound).toFixed(2)} confident
    </span>
  ) : (
    <span
      className="cursor-help rounded-full bg-alert/20 px-2 py-0.5 text-[10px] font-mono text-alert"
      title={`Score range: ${band.lowerBound.toFixed(2)} – ${band.upperBound.toFixed(2)}. Recommend manual review.`}
    >
      ⚠ Borderline — review
    </span>
  );
}
