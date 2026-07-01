import { useAppSelector } from "../../store/hooks";

export function VoiceInputButton() {
  const capabilities = useAppSelector((s) => s.pipeline.capabilities);
  const canVoice = capabilities?.voice_input ?? false;

  if (!canVoice) return null;

  return (
    <button
      type="button"
      className="flex items-center gap-1.5 rounded-lg border border-gridline/60 bg-surface/50 px-3 py-1.5 text-xs text-primary/60 transition hover:border-starlight/40 hover:text-starlight"
      title="Speak your JD (voice input via faster-whisper)"
    >
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="23" />
        <line x1="8" y1="23" x2="16" y2="23" />
      </svg>
      Voice
    </button>
  );
}
