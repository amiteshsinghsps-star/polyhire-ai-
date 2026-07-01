#!/usr/bin/env python3
"""
Bootstrap-train the LightGBM LambdaRank fusion ranker from weak supervision.

The challenge dataset may not ship with relevance labels. This script:
  1. Loads/synthesizes a candidate pool.
  2. Generates N synthetic JDs (one per skill domain).
  3. Runs retrieval + reranking for each.
  4. Uses the rerank_score (sigmoid-squashed) as a pseudo-label.
  5. Trains LambdaRank on the fused feature matrix.

Output: models/fusion_ranker.txt — drop-in upgrade over the linear baseline.

Usage:
    python -m scripts.train_fusion_ranker
    python -m scripts.train_fusion_ranker --n-jds 30 --dataset data/candidates.json
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow `python -m scripts.train_fusion_ranker` from the ml-service dir.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.dataset import SKILL_DOMAINS, load_dataset  # noqa: E402
from app.features import build_feature_vector  # noqa: E402
from app.stages.embedder import EMBED_DIM, Embedder  # noqa: E402
from app.stages.fusion_ranker import FEATURE_COLS, FusionRanker  # noqa: E402
from app.stages.reranker import Reranker  # noqa: E402
from app.stages.retriever import Retriever  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("train_fusion")


DOMAIN_JD_TEMPLATES = {
    "backend": (
        "Senior Backend Engineer. Must have: {skills}. "
        "5+ years of experience building distributed systems with python and postgresql. "
        "Nice to have: kafka, kubernetes. Domain: backend infrastructure."
    ),
    "frontend": (
        "Frontend Engineer. Must have: {skills}. "
        "3+ years with react and typescript. Nice to have: next.js, graphql."
    ),
    "data": (
        "Data Engineer. Must have: {skills}. "
        "4+ years with sql, spark, airflow. Nice to have: snowflake, dbt."
    ),
    "ml": (
        "Machine Learning Engineer. Must have: {skills}. "
        "4+ years with pytorch, nlp, deep learning. Nice to have: llm, rag."
    ),
    "devops": (
        "DevOps / Platform Engineer. Must have: {skills}. "
        "4+ years with kubernetes, terraform, aws. Nice to have: gcp, prometheus."
    ),
    "mobile": (
        "Mobile Engineer. Must have: {skills}. "
        "3+ years building native android/ios apps. Nice to have: flutter."
    ),
}


def synth_jds(n_per_domain: int) -> list[tuple[str, dict]]:
    """Generate synthetic structured JDs, one per (domain, sample)."""
    jds: list[tuple[str, dict]] = []
    for domain, skills_pool in SKILL_DOMAINS.items():
        template = DOMAIN_JD_TEMPLATES.get(domain, DOMAIN_JD_TEMPLATES["backend"])
        for _ in range(n_per_domain):
            import random

            must = random.sample(skills_pool, min(4, len(skills_pool)))
            nice = random.sample(skills_pool, min(3, len(skills_pool)))
            text = template.format(skills=", ".join(must))
            jds.append(
                (
                    text,
                    {
                        "role_title": f"{domain.title()} Engineer",
                        "seniority": "senior",
                        "must_have_skills": must,
                        "nice_to_have_skills": nice,
                        "domain": domain,
                        "min_years_experience": 4.0,
                        "soft_requirements": [],
                        "implicit_requirements": [],
                    },
                )
            )
    return jds


def main() -> int:
    parser = argparse.ArgumentParser(description="Train PolyHire fusion ranker (weak supervision).")
    parser.add_argument("--dataset", default=None, help="Path to candidate dataset (JSON/JSONL/CSV).")
    parser.add_argument("--n-jds-per-domain", type=int, default=5)
    parser.add_argument("--output", default="models/fusion_ranker.txt")
    args = parser.parse_args()

    settings = get_settings()
    log.info("Loading candidate pool …")
    profiles = load_dataset(args.dataset)
    log.info("Loaded %d candidates.", len(profiles))

    # Embed + index
    embedder = Embedder()
    retriever = Retriever(dim=EMBED_DIM)
    reranker = Reranker()
    trust = {p.id: float(p.trust_score or 1.0) for p in profiles}

    vectors = embedder.embed_candidates_batch([p.profile_text for p in profiles])
    payloads = [
        {
            "id": p.id,
            "name": p.name,
            "summary": p.summary,
            "skills": list(p.skills),
            "current_title": p.current_title,
            "profile_text": p.profile_text,
            "metadata": p.metadata.model_dump(),
            "trust_score": trust[p.id],
        }
        for p in profiles
    ]
    retriever.upsert_candidates([p.id for p in profiles], vectors, payloads)

    # Build training data across synthetic JDs
    jds = synth_jds(args.n_jds_per_domain)
    log.info("Generating weak labels across %d synthetic JDs …", len(jds))

    feature_frames: list[pd.DataFrame] = []
    labels: list[np.ndarray] = []
    groups: list[int] = []

    for jd_text, jd_struct in jds:
        jd_vec = embedder.embed_jd(jd_struct)
        hits = retriever.search(jd_vec, top_k=settings.rerank_top_k)
        if not hits:
            continue
        reranked = reranker.rerank(jd_text, hits, top_k=settings.rerank_top_k)
        rows = []
        ys = []
        for c in reranked:
            feat = build_feature_vector(
                embedding_similarity=c.get("embedding_similarity", 0.0),
                rerank_score=c.get("rerank_score", 0.0),
                structured_jd=jd_struct,
                candidate=c,
            )
            feat["id"] = c.get("id")
            rows.append(feat)
            # Weak label: sigmoid of rerank score → relevance grade in (0,1).
            # LambdaRank only needs *relative* ordering within a group.
            ys.append(1.0 / (1.0 + np.exp(-(c.get("rerank_score", 0.0)))))
        if len(rows) >= 5:
            feature_frames.append(pd.DataFrame(rows))
            labels.append(np.asarray(ys, dtype=np.float64))
            groups.append(len(rows))

    if not feature_frames:
        log.error("No training groups could be assembled; cannot train.")
        return 1

    X = pd.concat(feature_frames, ignore_index=True)
    y = np.concatenate(labels)
    log.info("Training set: %d rows across %d groups.", len(X), len(groups))

    ranker = FusionRanker(model_path=args.output)
    ranker.train(X, y, groups)  # train() selects FEATURE_COLS internally
    log.info("Trained fusion ranker saved to %s", args.output)

    # Quick sanity print: feature importance if available
    try:
        import lightgbm as lgb

        booster = lgb.Booster(model_file=args.output)
        imp = booster.feature_importance(importance_type="gain")
        ranked = sorted(zip(FEATURE_COLS, imp), key=lambda kv: kv[1], reverse=True)
        log.info("Feature importance (gain):")
        for name, gain in ranked:
            log.info("  %-28s %.3f", name, float(gain))
    except Exception as exc:  # noqa: BLE001
        log.debug("Could not print feature importance (%s).", exc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
