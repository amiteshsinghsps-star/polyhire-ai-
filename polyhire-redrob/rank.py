#!/usr/bin/env python3
"""
PolyHire AI — Phase B ranking step.
Command: python rank.py --candidates ./candidates.jsonl --out ./submission.csv

CPU-only, zero network calls, <=16GB RAM, designed for 100K candidates in <5 min.

Security features:
  1. JSONL Streaming Limits   -- per-line byte cap + malformed-line skip with audit log
  2. Audit Trail              -- structured JSONL event log for every security trigger
  3. Embedding Integrity      -- sha256 hash verification before loading .npy artifacts
  4. CSV Formula-Injection    -- already handled in writer.py

Advanced features (opt-in flags):
  --explain        Exact Shapley attribution per candidate (zero approximation)
  --conformal      Split conformal prediction intervals (90% coverage guarantee)
  --robust-rank    Bootstrap-stable top-100 via weight-space aggregation
  --redteam        Run adversarial honeypot red-team suite and write report
  --timeline       Run population-level timeline consistency diagnostics
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

from polyhire.security.audit_logger import AuditLogger
from polyhire.security.prompt_guard import InputSanitizer
from polyhire.security.honeypot_detector import HoneypotDetector, build_company_first_seen
from polyhire.bharat.contextualizer import BharatContextualizer
from polyhire.fusion import FusionRanker
from polyhire.reasoning import generate_reasoning, deduplicate_reasoning
from polyhire.writer import write_submission_csv, write_debug_csv
import jd_profile as jd

# ─────────────────────────────────────────────
# Security constants
# ─────────────────────────────────────────────
_MAX_LINE_BYTES = 512_000          # 512 KB per JSONL line
_MAX_TOTAL_CANDIDATES = 200_000    # guard against pathological files


# ─────────────────────────────────────────────
# Security feature 1 -- JSONL streaming limits
# ─────────────────────────────────────────────

def load_candidates(path: str, audit: AuditLogger) -> list[dict]:
    """Stream-safe JSONL loader with per-line byte cap and total count guard."""
    opener = gzip.open if path.endswith(".gz") else open
    candidates: list[dict] = []
    skipped_bytes = skipped_json = 0

    with opener(path, "rt", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line_bytes = len(raw_line.encode("utf-8"))
            if line_bytes > _MAX_LINE_BYTES:
                reason = f"line_too_large:{line_bytes}_bytes"
                audit.log_stream_guard(line_no, reason)
                skipped_bytes += 1
                continue

            stripped = raw_line.strip()
            if not stripped:
                continue

            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as exc:
                reason = f"json_parse_error:{exc}"
                audit.log_stream_guard(line_no, reason)
                skipped_json += 1
                continue

            candidates.append(obj)

            if len(candidates) >= _MAX_TOTAL_CANDIDATES:
                print(
                    f"[rank.py] WARNING: hit {_MAX_TOTAL_CANDIDATES} candidate limit at line {line_no}",
                    file=sys.stderr,
                )
                break

    if skipped_bytes or skipped_json:
        print(
            f"[rank.py] stream-guard: skipped {skipped_bytes} oversized lines, "
            f"{skipped_json} malformed JSON lines",
            file=sys.stderr,
        )

    return candidates


# ─────────────────────────────────────────────
# Security feature 3 -- embedding integrity
# ─────────────────────────────────────────────

def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_embedding_integrity(artifact_path: Path, expected_hash: str | None, audit: AuditLogger) -> bool:
    if not artifact_path.exists():
        return False
    if not expected_hash:
        return True

    actual = _sha256_of_file(artifact_path)
    audit.log_embedding_integrity(str(artifact_path), expected_hash, actual)

    if actual.lower() != expected_hash.lower():
        print(
            f"[rank.py] SECURITY: embedding integrity FAIL for {artifact_path} "
            f"(expected={expected_hash[:12]}... got={actual[:12]}...) -- falling back to lexical",
            file=sys.stderr,
        )
        return False
    return True


# ─────────────────────────────────────────────
# Lexical fallback
# ─────────────────────────────────────────────

def _lexical_jaccard(text: str, statements: list[str]) -> float:
    text_tokens = set(text.lower().split())
    if not text_tokens:
        return 0.0
    best = 0.0
    for stmt in statements:
        stmt_tokens = set(stmt.lower().split())
        inter = len(text_tokens & stmt_tokens)
        union = len(text_tokens | stmt_tokens) or 1
        best = max(best, inter / union)
    return best


def build_embedding_sim_fn(
    embeddings_path: str,
    jd_embeddings_path: str,
    candidate_ids: list[str],
    embed_hash: str | None = None,
    audit: AuditLogger | None = None,
):
    embed_path = Path(embeddings_path)
    jd_path = Path(jd_embeddings_path)
    id_path = Path("data/candidate_id_order.json")

    integrity_ok = True
    if embed_path.exists() and audit is not None:
        integrity_ok = verify_embedding_integrity(embed_path, embed_hash, audit)

    if integrity_ok and embed_path.exists() and jd_path.exists() and id_path.exists():
        matrix = np.load(embed_path)
        jd_matrix = np.load(jd_path)
        id_order = json.loads(id_path.read_text(encoding="utf-8"))
        id_to_row = {cid: i for i, cid in enumerate(id_order)}

        def sim_fn(text: str, statements: list[str], candidate_id: str | None = None) -> float:
            if candidate_id and candidate_id in id_to_row:
                row = matrix[id_to_row[candidate_id]]
                sims = jd_matrix @ row
                return float(np.max(sims))
            return _lexical_jaccard(text, statements)

        return sim_fn

    return lambda text, statements, candidate_id=None: _lexical_jaccard(text, statements)


# ─────────────────────────────────────────────
# Advanced feature helpers
# ─────────────────────────────────────────────

def _run_conformal_calibration(
    scored_pool: list[dict],
    cal_fraction: float = 0.10,
    alpha: float = 0.10,
) -> tuple[float, int]:
    """Calibrate conformal margin using a random subset of scored candidates."""
    from polyhire.explain.conformal import calibrate_conformal
    from eval.silver_label_eval import silver_relevance

    rng = random.Random(99)
    cal_size = max(30, int(len(scored_pool) * cal_fraction))
    cal_subset = rng.sample(scored_pool, min(cal_size, len(scored_pool)))

    cal_scores = [r["final_score"] for r in cal_subset]
    cal_labels = [silver_relevance(r["_candidate"]) / 3.0 for r in cal_subset]

    margin = calibrate_conformal(cal_scores, cal_labels, alpha=alpha)
    return margin, len(cal_subset)


def _apply_shapley(row: dict, weights: dict) -> dict:
    """Compute Shapley attribution and attach to row dict."""
    from polyhire.explain.attribution import shapley_exact, top_contributor, attribution_to_json
    attributions = shapley_exact(row, weights)
    row["top_contributor"] = top_contributor(attributions)
    row["shapley_breakdown"] = attribution_to_json(attributions)
    return row


def _apply_conformal(row: dict, margin: float) -> dict:
    from polyhire.explain.conformal import predict_interval
    lo, hi = predict_interval(row["final_score"], margin)
    row["confidence_interval"] = f"[{lo},{hi}]"
    return row


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PolyHire AI Phase B ranker")
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--embeddings", default="data/candidate_embeddings.npy")
    parser.add_argument("--jd-embeddings", default="data/jd_statement_embeddings.npy")
    parser.add_argument("--embed-sha256", default=None)
    parser.add_argument("--institution-table", default="data/bharat/institution_tiers.json")
    parser.add_argument("--lexicon", default="data/bharat/hinglish_lexicon.json")
    parser.add_argument("--top-n", type=int, default=100)
    parser.add_argument("--audit-log", default=None)
    # Advanced feature flags
    parser.add_argument("--explain",     action="store_true", help="Add exact Shapley attribution columns")
    parser.add_argument("--conformal",   action="store_true", help="Add conformal prediction interval column")
    parser.add_argument("--robust-rank", action="store_true", help="Sort final output by bootstrap rank stability")
    parser.add_argument("--redteam",     action="store_true", help="Run adversarial red-team suite and write report")
    parser.add_argument("--timeline",    action="store_true", help="Run population-level timeline diagnostics")
    parser.add_argument("--conformal-alpha", type=float, default=0.10, help="Conformal miscoverage rate (default 0.10 = 90%% CI)")
    args = parser.parse_args()

    t0 = time.time()

    # ── Security feature 2: Audit trail ────────────────────────────────
    audit_path = args.audit_log or (
        Path(args.out).parent / f"audit_report_{int(t0)}.jsonl"
    )
    audit = AuditLogger(out_path=audit_path)
    print(f"[rank.py] audit log -> {audit_path}", file=sys.stderr)

    # ── Stage 1: Load ──────────────────────────────────────────────────
    print(f"[rank.py] loading candidates from {args.candidates} ...", file=sys.stderr)
    candidates = load_candidates(args.candidates, audit)
    print(f"[rank.py] loaded {len(candidates)} candidates in {time.time()-t0:.1f}s", file=sys.stderr)

    # ── Timeline diagnostics (opt-in) ─────────────────────────────────
    if args.timeline:
        from polyhire.security.timeline import run_timeline_diagnostics
        import json as _json
        tl_report = run_timeline_diagnostics(candidates)
        tl_path = Path(args.out).parent / "timeline_diagnostic.json"
        tl_path.write_text(_json.dumps(tl_report, indent=2), encoding="utf-8")
        print(f"[rank.py] timeline diagnostics -> {tl_path}", file=sys.stderr)
        print(f"[rank.py] timeline verdict: {tl_report['dataset_verdict']}", file=sys.stderr)

    # ── Stage 2: Sanitize ──────────────────────────────────────────────
    sanitizer = InputSanitizer()
    for c in candidates:
        _, flags = sanitizer.sanitize_candidate(c)
        if flags:
            audit.log_sanitization(
                c.get("candidate_id", "UNKNOWN"), flags,
                severity="high" if any("critical" in f for f in flags) else "medium",
            )

    # ── Stage 3: Honeypot filter ───────────────────────────────────────
    company_first_seen = build_company_first_seen(candidates)
    detector = HoneypotDetector(company_first_seen, audit_logger=audit)
    clean_pool, flagged = detector.filter_pool(candidates)
    print(f"[rank.py] excluded {len(flagged)} honeypot-flagged candidates pre-ranking", file=sys.stderr)

    # ── Red-team suite (opt-in) ────────────────────────────────────────
    if args.redteam:
        from polyhire.security.redteam import run_adversarial_suite
        rt_out = str(Path(args.out).parent / "redteam_report.md")
        rt_results = run_adversarial_suite(detector=detector, n_per_strategy=200, out_report=rt_out)
        print("[rank.py] red-team suite results:", file=sys.stderr)
        for name, r in rt_results.items():
            status = "PASS" if r["detection_rate"] >= 0.80 else ("WARN" if r["detection_rate"] >= 0.40 else "FAIL")
            print(f"  [{status}] {name}: detection={r['detection_rate']:.0%}", file=sys.stderr)

    # ── Stage 4-6: Score, sort ─────────────────────────────────────────
    pool_max_exposure = max(
        (float(c.get("redrob_signals", {}).get("profile_views_received_30d", 0) or 0) for c in clean_pool),
        default=1.0,
    )

    candidate_ids = [c["candidate_id"] for c in clean_pool]
    embed_sim_fn = build_embedding_sim_fn(
        args.embeddings, args.jd_embeddings, candidate_ids,
        embed_hash=args.embed_sha256, audit=audit,
    )
    bharat = BharatContextualizer(args.institution_table, args.lexicon)
    ranker = FusionRanker(embed_sim_fn, bharat, pool_max_exposure=pool_max_exposure)

    print(f"[rank.py] scoring {len(clean_pool)} clean candidates...", file=sys.stderr)
    scored = []
    for c in clean_pool:
        breakdown = ranker.score(c)
        breakdown["_candidate"] = c
        scored.append(breakdown)

    scored.sort(key=lambda r: (-r["final_score"], -r["role_relevance"], r["candidate_id"]))
    print(f"[rank.py] scoring done in {time.time()-t0:.1f}s", file=sys.stderr)

    # ── Conformal calibration (opt-in) ─────────────────────────────────
    conformal_margin = None
    if args.conformal:
        conformal_margin, n_cal = _run_conformal_calibration(
            scored, cal_fraction=0.10, alpha=args.conformal_alpha
        )
        from polyhire.explain.conformal import conformal_summary
        print(
            f"[rank.py] conformal: {conformal_summary(conformal_margin, args.conformal_alpha, n_cal)}",
            file=sys.stderr,
        )

    # ── Robust rank aggregation (opt-in) ───────────────────────────────
    top_pool = scored[: max(300, args.top_n * 3)]  # operate on top-300 for speed
    if args.robust_rank:
        from polyhire.robustness import aggregate_robust_rank
        print(f"[rank.py] robust-rank: bootstrapping {len(top_pool)} candidates x 50 weight samples...", file=sys.stderr)
        top_pool = aggregate_robust_rank(top_pool, base_weights=dict(jd.WEIGHTS))
        print(f"[rank.py] robust-rank done in {time.time()-t0:.1f}s", file=sys.stderr)

    # ── Stage 7-8: Reason + deduplicate ────────────────────────────────
    top_n = top_pool[: args.top_n]
    rows = []
    for rank_pos, r in enumerate(top_n, start=1):
        # When robust-rank is active the sort key is _robust_score.
        # Use it as the submission score so the column is monotone-non-increasing.
        display_score = round(r.get("_robust_score", r["final_score"]), 4)

        # Apply Shapley if requested
        if args.explain:
            r = _apply_shapley(r, dict(jd.WEIGHTS))

        # Apply conformal interval if requested
        if args.conformal and conformal_margin is not None:
            r = _apply_conformal(r, conformal_margin)

        reasoning = generate_reasoning(r["_candidate"], r)
        row_out = {
            "candidate_id": r["candidate_id"],
            "rank":         rank_pos,
            "score":        display_score,
            "reasoning":    reasoning,
            "_candidate":   r["_candidate"],
            # Always store raw fusion score separately for debug output
            "_final_score": round(r["final_score"], 4),
        }

        # Carry through advanced columns
        for col in ("top_contributor", "shapley_breakdown", "confidence_interval", "rank_stability"):
            if col in r:
                row_out[col] = r[col]

        rows.append(row_out)

    rows = deduplicate_reasoning(rows)

    # ── Stage 9a: Write spec-valid submission.csv (exactly 4 cols) ───────
    # The validator requires precisely [candidate_id, rank, score, reasoning].
    # Advanced columns go into a separate debug CSV so the submission is clean.
    write_submission_csv(rows, args.out)

    # ── Stage 9b: Write debug CSV with all advanced columns (if any) ─────
    advanced_cols = ["top_contributor", "shapley_breakdown", "confidence_interval",
                     "rank_stability", "_final_score"]
    has_advanced = any(col in rows[0] for col in advanced_cols if rows)
    if has_advanced:
        debug_path = Path(args.out).with_suffix("") .parent / (Path(args.out).stem + "_debug.csv")
        write_debug_csv(rows, str(debug_path))
        print(f"[rank.py] debug CSV (with advanced cols) -> {debug_path}", file=sys.stderr)

    elapsed = time.time() - t0
    print(f"[rank.py] wrote {len(rows)} rows to {args.out} in {elapsed:.1f}s total", file=sys.stderr)
    if elapsed > 280:
        print("[rank.py] WARNING: approaching the 5-minute budget", file=sys.stderr)

    # ── Audit summary ───────────────────────────────────────────────────
    summary = audit.summary()
    print(f"[rank.py] audit summary: {summary}", file=sys.stderr)
    audit.close()

    validate_path = Path(__file__).parent / "validate_submission.py"
    if validate_path.exists():
        import subprocess
        result = subprocess.run(
            [sys.executable, str(validate_path), args.out, args.candidates],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            sys.exit(result.returncode)
        print("[rank.py] validate_submission.py passed", file=sys.stderr)


if __name__ == "__main__":
    main()
