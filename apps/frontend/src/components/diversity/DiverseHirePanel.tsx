import React, { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import type { AppDispatch, RootState } from "../../store";
import { analyzeDiversityFullReport } from "../../lib/api";
import {
  setJdAnalysis,
  setShortlistAnalysis,
  setDiverseHireLoading,
  setLastAnalyzedJdIdForDiversity,
} from "../../store/slices/diverseHireSlice";
import { Users, AlertTriangle, CheckCircle2, Sparkles, Building2 } from "lucide-react";

export function DiverseHirePanel() {
  const dispatch = useDispatch<AppDispatch>();
  const { currentResult } = useSelector((state: RootState) => state.pipeline);
  const { shortlist } = useSelector((state: RootState) => state.shortlist);
  const diverseHire = useSelector((state: RootState) => state.diverseHire);

  useEffect(() => {
    if (!currentResult?.jdId || !shortlist || shortlist.length === 0) return;
    
    if (diverseHire.lastAnalyzedJdId === currentResult.jdId) return;

    async function loadDiversityData() {
      dispatch(setDiverseHireLoading(true));
      try {
        const payload = {
          jd_text: currentResult?.structured_jd?.raw_text || currentResult?.structured_jd?.role_title || "",
          candidates: shortlist,
        };
        const res: any = await analyzeDiversityFullReport(payload);
        
        dispatch(setJdAnalysis(res.jd_analysis));
        dispatch(setShortlistAnalysis(res.shortlist_analysis));
        dispatch(setLastAnalyzedJdIdForDiversity(currentResult!.jdId));
      } catch (err) {
        console.error("Failed to analyze diversity:", err);
      } finally {
        dispatch(setDiverseHireLoading(false));
      }
    }

    loadDiversityData();
  }, [currentResult?.jdId, shortlist, dispatch, diverseHire.lastAnalyzedJdId]);

  if (!currentResult || !shortlist) {
    return (
      <div className="flex h-64 flex-col items-center justify-center text-slate-400">
        <Users className="mb-4 h-12 w-12 opacity-50" />
        <p>Run the discovery pipeline to view DiverseHire™ analysis.</p>
      </div>
    );
  }

  if (diverseHire.loading) {
    return (
      <div className="flex h-64 flex-col items-center justify-center text-slate-400">
        <Sparkles className="mb-4 h-8 w-8 animate-pulse text-indigo-400" />
        <p>Analyzing JD language and shortlist demographics...</p>
      </div>
    );
  }

  const { jdAnalysis, shortlistAnalysis } = diverseHire;
  const genderLang = jdAnalysis?.gender_language;
  const jdClean = jdAnalysis?.jd_cleaner;
  const instBias = shortlistAnalysis?.institution_bias;
  const divScore = shortlistAnalysis?.diversity_score;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
          <Users className="h-6 w-6 text-fuchsia-500" />
          DiverseHire™ Intelligence
        </h2>
        <p className="text-sm text-slate-400">
          Bias elimination in job descriptions and institution diversity scoring.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* JD Language Analysis */}
        <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-6 shadow-xl backdrop-blur-md">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-lg font-semibold text-white">JD Language Audit</h3>
            {genderLang?.is_biased ? (
              <span className="flex items-center gap-1 rounded bg-rose-500/20 px-2 py-0.5 text-xs text-rose-400">
                <AlertTriangle className="h-3 w-3" />
                {genderLang.bias_direction.toUpperCase()} BIAS
              </span>
            ) : (
              <span className="flex items-center gap-1 rounded bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-400">
                <CheckCircle2 className="h-3 w-3" />
                NEUTRAL
              </span>
            )}
          </div>
          
          <div className="space-y-4">
            <div className="flex justify-between text-sm text-slate-300 bg-slate-800/50 p-3 rounded-lg border border-slate-700">
              <div>
                <div className="font-medium text-slate-200">Masculine-Coded Words</div>
                <div className="text-xl font-bold text-fuchsia-400">{genderLang?.masculine_count || 0}</div>
              </div>
              <div className="text-right">
                <div className="font-medium text-slate-200">Feminine-Coded Words</div>
                <div className="text-xl font-bold text-teal-400">{genderLang?.feminine_count || 0}</div>
              </div>
            </div>

            {genderLang?.suggestions && genderLang.suggestions.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-slate-400 mb-2">Suggested Replacements</h4>
                <div className="space-y-2">
                  {genderLang.suggestions.map((s: any, i: number) => (
                    <div key={i} className="text-xs flex items-center justify-between p-2 bg-slate-800 rounded border border-slate-700">
                      <span className="text-rose-400 font-medium strike-through line-through">{s.word}</span>
                      <span className="text-slate-500">→</span>
                      <span className="text-emerald-400 font-medium">{s.replace_with}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {jdClean?.is_modified && (
              <div className="text-xs text-amber-400 bg-amber-500/10 p-3 rounded border border-amber-500/20">
                <AlertTriangle className="h-4 w-4 inline mr-1 mb-0.5" />
                JD Cleaner removed {jdClean.changes_made} exclusionary phrase(s) (e.g. "males only", "single preferred").
              </div>
            )}
          </div>
        </div>

        {/* Shortlist Diversity */}
        <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-6 shadow-xl backdrop-blur-md">
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-lg font-semibold text-white">Shortlist Diversity</h3>
            <span className={`rounded px-2 py-0.5 text-xs font-medium ${
              divScore?.rating === 'excellent' ? 'bg-emerald-500/20 text-emerald-400' :
              divScore?.rating === 'good' ? 'bg-teal-500/20 text-teal-400' :
              divScore?.rating === 'moderate' ? 'bg-amber-500/20 text-amber-400' :
              'bg-rose-500/20 text-rose-400'
            }`}>
              {divScore?.rating?.toUpperCase() || 'UNKNOWN'}
            </span>
          </div>

          <div className="space-y-4">
            <div className="p-4 bg-slate-800/50 rounded-lg border border-slate-700 text-center">
              <div className="text-sm text-slate-400 mb-1">Shannon Entropy Score</div>
              <div className="text-3xl font-bold text-white">
                {((divScore?.diversity_score || 0) * 100).toFixed(0)}<span className="text-lg text-slate-500">/100</span>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-medium text-slate-400 mb-2 flex items-center gap-1">
                <Building2 className="h-4 w-4" />
                Institution Tier Distribution
              </h4>
              <div className="space-y-2">
                {instBias && ['tier_1', 'tier_2', 'tier_3', 'unknown'].map(tier => (
                  <div key={tier} className="flex items-center justify-between text-sm">
                    <span className="text-slate-300 capitalize">{tier.replace('_', ' ')}</span>
                    <span className="font-medium text-white">{instBias.tier_distribution[tier] || 0}</span>
                  </div>
                ))}
              </div>
            </div>

            {instBias?.institution_bias_detected && (
              <div className="text-xs text-rose-400 bg-rose-500/10 p-3 rounded border border-rose-500/20 mt-4">
                <AlertTriangle className="h-4 w-4 inline mr-1 mb-0.5" />
                <strong>Elite Concentration Bias:</strong> {(instBias.elite_concentration * 100).toFixed(0)}% of candidates are from Tier-1 institutions.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
