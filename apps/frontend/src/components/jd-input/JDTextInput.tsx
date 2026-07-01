import { useCallback, useState, type FormEvent } from "react";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import { submitJD } from "../../lib/api";
import {
  pipelineStarted,
  pipelineError,
  resetPipeline,
} from "../../store/slices/pipelineSlice";
import { resetShortlist } from "../../store/slices/shortlistSlice";
import { resetGalaxy } from "../../store/slices/galaxySlice";
import { setTab } from "../../store/slices/uiSlice";
import { LanguageToggle } from "./LanguageToggle";

const SAMPLE_JD = `Senior Backend Engineer

We are looking for a Senior Backend Engineer to join our distributed systems team. You will design and build high-throughput microservices handling millions of requests per day.

Requirements:
- 5+ years of experience in backend development with Python or Go
- Strong experience with PostgreSQL, Redis, and Kafka
- Hands-on with Kubernetes, Docker, and CI/CD pipelines
- Experience with distributed systems design and event-driven architectures
- Strong communication skills and the ability to mentor junior engineers

Nice to have:
- Experience with GraphQL and gRPC
- Familiarity with observability tools (Prometheus, Grafana, Jaeger)
- Previous experience in fintech or e-commerce domains

We value curiosity, ownership, and a bias for action. You will have the autonomy to drive technical decisions and ship features end-to-end.`;

export function JDTextInput() {
  const dispatch = useAppDispatch();
  const { isRunning, currentStage, progress, stageMessage, error } =
    useAppSelector((s) => s.pipeline);
  const language = useAppSelector((s) => s.ui.jdLanguage);
  const [text, setText] = useState("");

  const handleSubmit = useCallback(
    async (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      if (!text.trim()) return;

      dispatch(resetShortlist());
      dispatch(resetGalaxy());
      dispatch(resetPipeline());
      dispatch(pipelineStarted());
      dispatch(setTab("galaxy"));

      try {
        await submitJD({ text: text.trim(), language });
        // The Socket.IO handler dispatches pipelineComplete — this HTTP call
        // is fire-and-forget; the WebSocket stream updates the UI live.
      } catch (err) {
        dispatch(pipelineError(err instanceof Error ? err.message : String(err)));
      }
    },
    [dispatch, text, language],
  );

  const loadSample = useCallback(() => {
    setText(SAMPLE_JD);
  }, []);

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <label
          htmlFor="jd-text"
          className="font-display text-sm font-semibold text-primary/80"
        >
          Job Description
        </label>
        <div className="flex items-center gap-2">
          <LanguageToggle />
          <button
            type="button"
            onClick={loadSample}
            className="text-[11px] font-mono text-starlight/60 transition hover:text-starlight"
          >
            Load sample JD →
          </button>
        </div>
      </div>

      <textarea
        id="jd-text"
        rows={10}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste a job description here… (or click 'Load sample JD')"
        className="w-full resize-none rounded-xl border border-gridline/60 bg-surface/50 px-4 py-3 text-sm leading-relaxed text-primary placeholder:text-primary/25 focus:border-starlight/50 focus:outline-none focus:ring-1 focus:ring-starlight/30"
        disabled={isRunning}
      />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <SubmitButton isRunning={isRunning} />
          {isRunning && (
            <div className="flex items-center gap-2">
              <StageProgress stage={currentStage} progress={progress} message={stageMessage} />
            </div>
          )}
        </div>
        {error && (
          <span className="max-w-xs truncate text-[11px] text-alert">{error}</span>
        )}
      </div>
    </form>
  );
}

function SubmitButton({ isRunning }: { isRunning: boolean }) {
  return (
    <button
      type="submit"
      disabled={isRunning}
      className="rounded-lg bg-starlight px-5 py-2 text-sm font-semibold text-void transition
                 hover:bg-starlight/90 disabled:cursor-not-allowed disabled:opacity-40"
    >
      {isRunning ? (
        <span className="flex items-center gap-2">
          <Spinner /> Discovering…
        </span>
      ) : (
        "Discover Candidates"
      )}
    </button>
  );
}

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

function StageProgress({
  stage,
  progress,
  message,
}: {
  stage: string | null;
  progress: number;
  message: string | null;
}) {
  return (
    <div className="flex items-center gap-2 text-[11px] font-mono text-primary/50">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-gridline/50">
        <div
          className="h-full rounded-full bg-starlight/70 transition-all duration-500"
          style={{ width: `${Math.round(progress * 100)}%` }}
        />
      </div>
      <span className="w-32 truncate">
        {message ?? stage?.replace(/_/g, " ") ?? "…"}
      </span>
    </div>
  );
}
