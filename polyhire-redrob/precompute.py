#!/usr/bin/env python3
"""Phase A — precompute candidate + JD embeddings (run once before submission)."""
import argparse
import gzip
import json
from pathlib import Path

import numpy as np

import jd_profile as jd


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", required=True)
    p.add_argument("--out", default="data/candidate_embeddings.npy")
    args = p.parse_args()

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise SystemExit(
            "sentence-transformers required for precompute.py: pip install sentence-transformers"
        ) from e

    model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

    opener = gzip.open if args.candidates.endswith(".gz") else open
    texts, ids = [], []
    with opener(args.candidates, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            c = json.loads(line)
            summary = c.get("profile", {}).get("summary", "")
            descriptions = " ".join(r.get("description", "") for r in c.get("career_history", [])[:3])
            texts.append((summary + " " + descriptions)[:2000])
            ids.append(c["candidate_id"])

    print(f"Embedding {len(texts)} candidate profiles ...")
    embeddings = model.encode(texts, batch_size=256, show_progress_bar=True, normalize_embeddings=True)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(out_path, embeddings.astype(np.float32))

    jd_embeddings = model.encode(jd.MUST_HAVE_CAPABILITY_STATEMENTS, normalize_embeddings=True)
    np.save("data/jd_statement_embeddings.npy", jd_embeddings.astype(np.float32))

    with open("data/candidate_id_order.json", "w", encoding="utf-8") as f:
        json.dump(ids, f)

    print(f"Saved embeddings to {out_path} ({embeddings.shape})")


if __name__ == "__main__":
    main()
