/**
 * InstitutionLookup — Recruiter utility to check NIRF scores for Indian institutions.
 */
import { useState } from "react";
import { fetchNirfLookup } from "../../lib/api";

interface InstitutionMatch {
  institution: string;
  score: number;
}

export function InstitutionLookup() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<InstitutionMatch[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleSearch() {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await fetchNirfLookup(query);
      setResults((data.matches as InstitutionMatch[]) ?? []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded-lg bg-surface p-4">
      <h3 className="font-display text-sm text-starlight">NIRF Institution Lookup</h3>
      <p className="text-xs text-primary/50">
        Check the NIRF 2025 prestige tier of any Indian institution.
      </p>
      <div className="flex gap-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="e.g. NIT Nagpur, BITS Pilani…"
          className="flex-1 rounded border border-gridline bg-void px-2 py-1 text-xs text-primary placeholder:text-primary/30 focus:border-starlight/50 focus:outline-none"
        />
        <button
          onClick={handleSearch}
          disabled={loading}
          className="rounded bg-starlight/10 px-3 py-1 text-xs text-starlight hover:bg-starlight/20 disabled:opacity-50"
        >
          {loading ? "…" : "Search"}
        </button>
      </div>
      {results.length > 0 && (
        <ul className="space-y-1">
          {results.map((r) => (
            <li key={r.institution} className="flex items-center justify-between text-xs">
              <span className="capitalize text-primary/80">{r.institution}</span>
              <span
                className={`font-mono ${
                  r.score >= 0.85 ? "text-trust" : r.score >= 0.7 ? "text-starlight" : "text-primary/50"
                }`}
              >
                {r.score.toFixed(2)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
