/**
 * SkillRadar — time-decayed skill relevance bar chart.
 *
 * For a selected candidate in the Shortlist panel, shows each skill
 * as a bar colored by its temporal relevance (0-1 scale).
 * Half-life annotation and "decayed" warning make this immediately
 * actionable for interview preparation.
 */
import { useState, useEffect } from "react";
import { useAppSelector } from "../../store/hooks";
import { analyzeSkillDecay } from "../../lib/api";

interface SkillBar {
  name:         string;
  relevance:    number;
  age_years:    number;
  half_life:    number;
  is_decayed:   boolean;
  had_evidence: boolean;
}

interface DecayAnalysis {
  candidate_id:             string;
  live_skills:              Record<string, number>;
  decayed_skills:           string[];
  strong_skills:            string[];
  temporal_skill_overlap:   number;
  static_skill_overlap:     number;
  overlap_inflation:        number;
  recruiter_warning:        string | null;
  skill_decay_details:      Record<string, { relevance: number; age_years: number; half_life: number; is_decayed: boolean; had_evidence: boolean }>;
}

function relevanceColor(r: number): string {
  if (r >= 0.80) return "bg-emerald-400";
  if (r >= 0.60) return "bg-amber-400";
  if (r >= 0.35) return "bg-orange-400";
  return "bg-red-500";
}

function relevanceLabel(r: number): string {
  if (r >= 0.80) return "Current";
  if (r >= 0.60) return "Fading";
  if (r >= 0.35) return "Stale";
  return "Decayed";
}

export function SkillRadar({
  candidateId,
  skills,
}: {
  candidateId: string;
  skills: string[];
}) {
  const structuredJd = useAppSelector((s) => s.pipeline.structuredJd);
  const [analysis, setAnalysis] = useState<DecayAnalysis | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);

  useEffect(() => {
    if (!candidateId || skills.length === 0 || !structuredJd) return;

    setLoading(true);
    analyzeSkillDecay({
      candidate: { id: candidateId, skills },
      structured_jd: structuredJd as Record<string, unknown>,
    })
      .then((data) => setAnalysis(data as DecayAnalysis))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Error"))
      .finally(() => setLoading(false));
  }, [candidateId, skills, structuredJd]);

  if (skills.length === 0) return null;

  const bars: SkillBar[] = analysis
    ? Object.entries(analysis.skill_decay_details).map(([name, d]) => ({
        name, ...d,
      })).sort((a, b) => b.relevance - a.relevance)
    : skills.map((s) => ({
        name: s, relevance: 0.8, age_years: 0, half_life: 3, is_decayed: false, had_evidence: false,
      }));

  return (
    <div className="space-y-3">
      {/* Header with overlap comparison */}
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-xs font-semibold text-primary">SkillDecay™ Radar</h3>
          <p className="text-[10px] text-primary/40">Time-weighted skill relevance</p>
        </div>
        {analysis && (
          <div className="text-right">
            <div className="text-[10px] text-primary/40">Overlap</div>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-emerald-400 font-mono">
                {Math.round(analysis.temporal_skill_overlap * 100)}%
                <span className="text-primary/30 ml-0.5">temporal</span>
              </span>
              {analysis.overlap_inflation > 0.05 && (
                <span className="text-red-400/70 font-mono text-[10px]">
                  (static {Math.round(analysis.static_skill_overlap * 100)}% — inflated by {Math.round(analysis.overlap_inflation * 100)}pp)
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Recruiter warning */}
      {analysis?.recruiter_warning && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/8 px-3 py-2 text-[11px] text-amber-400">
          ⚠️ {analysis.recruiter_warning}
        </div>
      )}

      {/* Skill bars */}
      <div className="space-y-1.5">
        {loading && (
          <div className="space-y-1.5">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-6 rounded bg-gridline/20 animate-pulse" />
            ))}
          </div>
        )}
        {error && <p className="text-[11px] text-red-400">{error}</p>}
        {!loading && bars.map((bar) => (
          <div key={bar.name} className="group">
            <div className="flex items-center justify-between mb-0.5">
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-primary/70 font-medium">{bar.name}</span>
                {bar.had_evidence && (
                  <span className="text-[9px] text-emerald-400/70 border border-emerald-400/20 rounded px-1">recent proof</span>
                )}
              </div>
              <div className="flex items-center gap-2 text-[10px]">
                <span className="text-primary/30">
                  {bar.age_years > 0 ? `${bar.age_years.toFixed(1)}yr ago` : "recent"}
                  {" · "}t½ {bar.half_life}yr
                </span>
                <span className={`font-mono font-medium ${bar.is_decayed ? "text-red-400" : "text-primary/60"}`}>
                  {Math.round(bar.relevance * 100)}%
                </span>
              </div>
            </div>
            <div className="relative h-2 w-full overflow-hidden rounded-full bg-gridline/30">
              <div
                className={`h-full rounded-full transition-all duration-500 ${relevanceColor(bar.relevance)}`}
                style={{ width: `${bar.relevance * 100}%` }}
              />
            </div>
            <div className="mt-0.5 text-[9px] text-primary/25">{relevanceLabel(bar.relevance)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
