/**
 * WeightSliders — recruiter-facing fusion-weight controls.
 *
 * Dragging a slider recalculates the galaxy layout in real time via the
 * Socket.IO reweight channel. Each slider maps to a fusion feature.
 */
import { useCallback } from "react";
import { useAppSelector, useAppDispatch } from "../../store/hooks";
import { setWeight } from "../../store/slices/galaxySlice";
import { useSocket } from "../../hooks/useSocket";

const FEATURE_LABELS: Record<string, { label: string; short: string }> = {
  embedding_similarity: { label: "Semantic Fit", short: "Embed" },
  rerank_score: { label: "Cross-Encoder", short: "Rerank" },
  years_experience_match: { label: "Experience", short: "Exp" },
  skill_overlap_ratio: { label: "Skill Coverage", short: "Skills" },
  recency_of_activity: { label: "Recent Activity", short: "Recent" },
  career_trajectory_slope: { label: "Career Trajectory", short: "Traj" },
  engagement_score: { label: "Engagement", short: "Engage" },
  trust_score: { label: "Trust Score", short: "Trust" },
  institution_tier_score: { label: "NIRF Institution", short: "NIRF" },
  informal_sector_score: { label: "Informal Sector", short: "Informal" },
};

export function WeightSliders() {
  const weights = useAppSelector((s) => s.galaxy.weights);
  const dispatch = useAppDispatch();
  const socketRef = useSocket();

  const handleChange = useCallback(
    (key: string, value: number) => {
      dispatch(setWeight({ key, value }));
      // Debounce the socket reweight — the socket handler coalesces automatically.
      socketRef.current?.emit("galaxy:reweight", {
        jdId: null, // uses the latest run
        weights: { ...weights, [key]: value },
      });
    },
    [dispatch, weights, socketRef],
  );

  return (
    <div className="space-y-2.5">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-mono text-primary/40">Fusion Weights</span>
        <button
          type="button"
          onClick={() => {
            // Reset to defaults
            const defaults = {
              embedding_similarity: 0.22,
              rerank_score: 0.28,
              years_experience_match: 0.11,
              skill_overlap_ratio: 0.15,
              recency_of_activity: 0.05,
              career_trajectory_slope: 0.04,
              engagement_score: 0.04,
              trust_score: 0.05,
              institution_tier_score: 0.04,
              informal_sector_score: 0.02,
            };
            for (const [k, v] of Object.entries(defaults)) {
              dispatch(setWeight({ key: k, value: v }));
            }
          }}
          className="text-[10px] font-mono text-starlight/50 transition hover:text-starlight"
        >
          Reset
        </button>
      </div>
      {Object.entries(weights).map(([key, value]) => {
        const meta = FEATURE_LABELS[key];
        if (!meta) return null;
        return (
          <SliderRow
            key={key}
            featureKey={key}
            label={meta.label}
            short={meta.short}
            value={value}
            onChange={(v) => handleChange(key, v)}
          />
        );
      })}
    </div>
  );
}

function SliderRow({
  featureKey,
  label,
  short,
  value,
  onChange,
}: {
  featureKey: string;
  label: string;
  short: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="group">
      <div className="mb-0.5 flex items-center justify-between">
        <span className="text-[11px] text-primary/50 group-hover:text-primary/70">{label}</span>
        <span className="font-mono text-[10px] text-starlight/60">
          {(value * 100).toFixed(0)}%
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        value={Math.round(value * 100)}
        onChange={(e) => onChange(Number(e.target.value) / 100)}
        className="h-1 w-full cursor-pointer appearance-none rounded-full bg-gridline/50
                   [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:appearance-none
                   [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-starlight
                   [&::-webkit-slider-thumb]:transition [&::-webkit-slider-thumb]:hover:bg-starlight/80"
      />
    </div>
  );
}
