/**
 * IntentBadge — compact label for a candidate's outreach readiness.
 * Shows in ShortlistTable rows. Colors match the intent quadrant system.
 */
export type IntentLabel = "hot" | "warm" | "cool" | "dormant";

const BADGE_STYLES: Record<IntentLabel, string> = {
  hot:     "bg-red-500/20 text-red-400 border border-red-500/30",
  warm:    "bg-amber-500/20 text-amber-400 border border-amber-500/30",
  cool:    "bg-sky-500/20 text-sky-400 border border-sky-500/30",
  dormant: "bg-zinc-500/20 text-zinc-400 border border-zinc-500/30",
};

const BADGE_ICONS: Record<IntentLabel, string> = {
  hot:     "🔥",
  warm:    "✨",
  cool:    "🌊",
  dormant: "💤",
};

export function IntentBadge({
  label,
  score,
  advice,
}: {
  label?: IntentLabel;
  score?: number;
  advice?: string;
}) {
  if (!label) return null;

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium ${BADGE_STYLES[label]}`}
      title={advice ?? label}
    >
      <span>{BADGE_ICONS[label]}</span>
      <span className="uppercase tracking-wider">{label}</span>
      {score !== undefined && (
        <span className="opacity-60 font-mono">{Math.round(score * 100)}</span>
      )}
    </span>
  );
}
