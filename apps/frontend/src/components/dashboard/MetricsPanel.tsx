/**
 * MetricsPanel — shows structured JD parse result + pipeline latency.
 */
import { useAppSelector } from "../../store/hooks";

export function MetricsPanel() {
  const structuredJd = useAppSelector((s) => s.pipeline.structuredJd);
  const latencyMs = useAppSelector((s) => s.pipeline.latencyMs);
  const metrics = useAppSelector((s) => s.pipeline);
  const lastJdId = useAppSelector((s) => s.pipeline.lastJdId);
  const candidateCount = useAppSelector((s) => s.shortlist.candidates.length);

  if (!structuredJd) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-xs text-primary/25">Pipeline metrics appear after a JD run.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Pipeline stats */}
      <div className="grid grid-cols-3 gap-2">
        <StatBox label="Latency" value={`${latencyMs ?? "?"}ms`} />
        <StatBox label="Candidates" value={String(candidateCount)} />
        <StatBox label="JD ID" value={lastJdId ?? "—"} mono />
      </div>

      {/* Parsed JD */}
      <div className="panel">
        <div className="panel-header">
          <span className="text-[11px] font-mono text-primary/40">Parsed Job Description</span>
        </div>
        <div className="space-y-2.5 px-4 py-3">
          <Field label="Role" value={String(structuredJd.role_title ?? "—")} />
          <Field label="Seniority" value={String(structuredJd.seniority ?? "—")} badge />
          <Field label="Domain" value={String(structuredJd.domain ?? "—")} />
          <Field label="Min Experience" value={`${structuredJd.min_years_experience ?? 0} years`} />
          <SkillList
            label="Must-Have Skills"
            skills={(structuredJd.must_have_skills as string[]) ?? []}
          />
          <SkillList
            label="Nice-to-Have Skills"
            skills={(structuredJd.nice_to_have_skills as string[]) ?? []}
          />
          {Array.isArray(structuredJd.implicit_requirements) &&
            (structuredJd.implicit_requirements as string[]).length > 0 && (
              <SkillList
                label="Implicit (Inferred)"
                skills={structuredJd.implicit_requirements as string[]}
                subtle
              />
            )}
          {Array.isArray(structuredJd.soft_requirements) &&
            (structuredJd.soft_requirements as string[]).length > 0 && (
              <SkillList
                label="Soft Requirements"
                skills={structuredJd.soft_requirements as string[]}
                subtle
              />
            )}
        </div>
      </div>

      {/* Fallback warnings */}
      {metrics.capabilities && (
        <FallbackWarnings capabilities={metrics.capabilities} />
      )}
    </div>
  );
}

function StatBox({
  label,
  value,
  mono,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="panel px-3 py-2 text-center">
      <div className="text-[10px] font-mono text-primary/30">{label}</div>
      <div className={`mt-0.5 text-sm font-semibold text-primary ${mono ? "font-mono text-xs" : ""}`}>
        {value}
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  badge,
}: {
  label: string;
  value: string;
  badge?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[11px] text-primary/40">{label}</span>
      {badge ? (
        <span className="badge badge-neutral">{value}</span>
      ) : (
        <span className="text-sm text-primary">{value}</span>
      )}
    </div>
  );
}

function SkillList({
  label,
  skills,
  subtle,
}: {
  label: string;
  skills: string[];
  subtle?: boolean;
}) {
  if (skills.length === 0) return null;
  return (
    <div>
      <div className="mb-1 text-[11px] text-primary/40">{label}</div>
      <div className="flex flex-wrap gap-1">
        {skills.map((s) => (
          <span
            key={s}
            className={`badge ${subtle ? "badge-neutral" : "badge-trust"}`}
          >
            {s}
          </span>
        ))}
      </div>
    </div>
  );
}

function FallbackWarnings({
  capabilities,
}: {
  capabilities: Record<string, boolean>;
}) {
  const fallbacks: string[] = [];
  if (!capabilities.embedding_model_loaded) fallbacks.push("Embedding (hashing fallback)");
  if (!capabilities.reranker_model_loaded) fallbacks.push("Reranker (token-overlap fallback)");
  if (!capabilities.bias_detection) fallbacks.push("Bias Detection (lexicon fallback)");
  if (!capabilities.llm_explainability) fallbacks.push("LLM Explainability (templated fallback)");
  if (!capabilities.fusion_ranker_trained) fallbacks.push("Fusion Ranker (linear baseline)");

  if (fallbacks.length === 0) return null;

  return (
    <div className="panel border-alert/30 bg-alert/5">
      <div className="px-4 py-2">
        <div className="mb-1 text-[11px] font-semibold text-alert/80">
          ⚠ Running with fallbacks
        </div>
        <ul className="space-y-0.5">
          {fallbacks.map((f) => (
            <li key={f} className="text-[10px] font-mono text-alert/60">
              • {f}
            </li>
          ))}
        </ul>
        <p className="mt-1.5 text-[10px] text-primary/30">
          Run <code className="text-starlight/60">scripts/download_models.sh</code> and{" "}
          <code className="text-starlight/60">scripts/train_fusion_ranker.py</code> for full quality.
        </p>
      </div>
    </div>
  );
}
