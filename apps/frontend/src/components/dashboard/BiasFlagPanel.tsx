/**
 * BiasFlagPanel — surfaces biased-language flags from the JD.
 */
import { useAppSelector } from "../../store/hooks";

export function BiasFlagPanel() {
  const biasFlags = useAppSelector((s) => s.pipeline.biasFlags);
  const showPanel = useAppSelector((s) => s.ui.showBiasPanel);
  const capabilities = useAppSelector((s) => s.pipeline.capabilities);

  // Hide the panel entirely if bias detection isn't active or no JD submitted.
  const canBias = capabilities?.bias_detection ?? true;
  if (!canBias) return null;

  if (!showPanel || biasFlags.length === 0) {
    return null;
  }

  return (
    <div className="panel animate-fade-in">
      <div className="panel-header flex items-center gap-2">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-alert">
          <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
        <span className="text-xs font-semibold text-alert">Bias Flags Detected</span>
        <span className="badge badge-alert">{biasFlags.length}</span>
      </div>
      <div className="divide-y divide-gridline/30 px-4 py-2">
        {biasFlags.map((flag, i) => (
          <div key={i} className="flex items-start gap-3 py-2">
            <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-alert/15">
              <span className="text-[10px] font-bold text-alert">{i + 1}</span>
            </div>
            <div>
              <p className="text-xs leading-relaxed text-primary/70">
                "{flag.sentence}"
              </p>
              <p className="mt-0.5 font-mono text-[10px] text-alert/60">
                confidence: {(flag.confidence * 100).toFixed(0)}%
                {flag.category ? ` · ${flag.category}` : ""}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
