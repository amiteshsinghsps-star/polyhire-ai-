import { type ReactNode } from "react";

export function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex flex-1 flex-col overflow-hidden">{children}</main>
      <Footer />
    </div>
  );
}

function Header() {
  return (
    <header className="flex items-center justify-between border-b border-gridline/50 bg-void/60 px-6 py-3 backdrop-blur-md">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-starlight/15">
          <svg width="18" height="18" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="32" cy="32" r="6" fill="#E8A33D" />
            <circle cx="32" cy="32" r="20" stroke="#E8A33D" strokeOpacity="0.4" strokeWidth="2" />
          </svg>
        </div>
        <div>
          <h1 className="font-display text-lg font-semibold tracking-tight text-primary">
            PolyHire AI
          </h1>
          <p className="text-[11px] font-mono text-primary/40">Intelligent Candidate Discovery</p>
        </div>
      </div>
      <StatusIndicator />
    </header>
  );
}

function StatusIndicator() {
  return (
    <div className="flex items-center gap-4">
      <PipelineStatusDot />
      <a
        href="https://github.com/xcution/polyhire-ai"
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs text-primary/50 transition hover:text-starlight"
      >
        GitHub ↗
      </a>
    </div>
  );
}

function PipelineStatusDot() {
  // This reads from Redux — imported inline to keep Layout self-contained.
  // In practice the dot uses useAppSelector to read pipeline.isRunning.
  return (
    <div className="flex items-center gap-2">
      <span className="relative flex h-2.5 w-2.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-trust opacity-40" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-trust" />
      </span>
      <span className="text-[11px] font-mono text-primary/50">Ready</span>
    </div>
  );
}

import { useAppSelector } from "../../store/hooks";

function Footer() {
  const activeTab = useAppSelector((s) => s.ui.activeTab);

  if (activeTab === "galaxy") {
    return (
      <footer className="absolute bottom-2 right-4 z-40 opacity-30 transition-opacity hover:opacity-100 pointer-events-none">
        <p className="text-right text-[10px] font-mono text-primary/60">
          PolyHire AI v1.0 · Track 1 — India Runs by Redrob AI × Hack2Skill
        </p>
      </footer>
    );
  }

  return (
    <footer className="border-t border-gridline/30 px-6 py-2">
      <p className="text-center text-[10px] font-mono text-primary/25">
        PolyHire AI v1.0 · Track 1 — India Runs by Redrob AI × Hack2Skill · Built by Team Xcution
      </p>
    </footer>
  );
}
