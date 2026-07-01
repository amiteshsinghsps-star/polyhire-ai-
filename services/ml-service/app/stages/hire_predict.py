"""
HirePredict™ Outcome Loop — Stage 11 (closed feedback system)
==============================================================
Closes the loop: after a hire, the system learns which features
actually predicted post-hire success — not just shortlisting quality.

Architecture:
  - SQLite-backed (zero deps beyond stdlib) feedback store
  - LightGBM binary classifier trains incrementally on outcomes
  - Predictions attached per-candidate in subsequent pipeline runs
  - Falls back to a heuristic model when < 10 outcomes collected

Outcome schema:
  jd_id         — which job this outcome belongs to
  candidate_id  — who was hired
  hired         — bool: was this candidate hired?
  retained_30d  — bool: still at company after 30 days? (optional)
  features      — the fusion feature vector at shortlist time
  outcome_date  — when the outcome was recorded
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

DB_PATH = Path("data/hire_predict.db")

FEATURE_COLS = [
    "embedding_similarity", "rerank_score", "years_experience_match",
    "skill_overlap_ratio", "recency_of_activity", "career_trajectory_slope",
    "engagement_score", "trust_score", "intent_score",
]

MIN_SAMPLES_TO_TRAIN = 10


# ── SQLite store ──────────────────────────────────────────────────────────────

class HirePredictStore:
    """Lightweight SQLite-backed outcome persistence."""

    def __init__(self, db_path: Path | str = DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS outcomes (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    jd_id         TEXT NOT NULL,
                    candidate_id  TEXT NOT NULL,
                    hired         INTEGER NOT NULL,
                    retained_30d  INTEGER,
                    features      TEXT NOT NULL,
                    outcome_date  TEXT NOT NULL,
                    UNIQUE(jd_id, candidate_id)
                )
            """)
            conn.commit()

    def save_outcome(
        self,
        jd_id: str,
        candidate_id: str,
        hired: bool,
        features: dict,
        retained_30d: Optional[bool] = None,
    ) -> dict:
        outcome_date = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO outcomes
                   (jd_id, candidate_id, hired, retained_30d, features, outcome_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    jd_id, candidate_id,
                    int(hired),
                    int(retained_30d) if retained_30d is not None else None,
                    json.dumps(features),
                    outcome_date,
                ),
            )
            conn.commit()
        log.info("HirePredict: saved outcome for %s/%s hired=%s", jd_id, candidate_id, hired)
        return {"status": "saved", "jd_id": jd_id, "candidate_id": candidate_id, "hired": hired}

    def load_training_data(self) -> tuple[np.ndarray, np.ndarray]:
        """Returns (X, y) for LightGBM training. y=1 if hired AND retained."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT features, hired, retained_30d FROM outcomes"
            ).fetchall()

        if not rows:
            return np.empty((0, len(FEATURE_COLS))), np.empty(0)

        X_rows, y_rows = [], []
        for feat_json, hired, retained in rows:
            try:
                feat = json.loads(feat_json)
                x = [float(feat.get(col, 0.0)) for col in FEATURE_COLS]
                # Label: hired=1, but downgrade if churned within 30d
                label = int(hired)
                if retained is not None and not retained:
                    label = 0
                X_rows.append(x)
                y_rows.append(label)
            except Exception:
                pass

        return np.array(X_rows, dtype=np.float32), np.array(y_rows, dtype=np.float32)

    def count_outcomes(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]

    def load_outcomes_for_jd(self, jd_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT candidate_id, hired, retained_30d, outcome_date FROM outcomes WHERE jd_id=?",
                (jd_id,),
            ).fetchall()
        return [
            {"candidate_id": r[0], "hired": bool(r[1]),
             "retained_30d": bool(r[2]) if r[2] is not None else None,
             "outcome_date": r[3]}
            for r in rows
        ]


# ── Predictor ─────────────────────────────────────────────────────────────────

class HirePredictModel:
    """
    LightGBM binary classifier (hired + retained vs. not hired).
    Falls back to heuristic blend until MIN_SAMPLES_TO_TRAIN outcomes exist.
    """

    MODEL_PATH = Path("models/hire_predict.txt")

    def __init__(self, store: HirePredictStore) -> None:
        self.store = store
        self._model = None
        self._lgb = None
        self._trained = False
        self._try_load()

    def _try_load(self) -> None:
        if not self.MODEL_PATH.exists():
            return
        try:
            import lightgbm as lgb
            self._lgb = lgb
            self._model = lgb.Booster(model_file=str(self.MODEL_PATH))
            self._trained = True
            log.info("HirePredict: loaded model from %s", self.MODEL_PATH)
        except Exception as exc:
            log.warning("HirePredict: could not load model (%s)", exc)

    def train(self) -> dict:
        X, y = self.store.load_training_data()
        n = len(y)
        if n < MIN_SAMPLES_TO_TRAIN:
            return {"status": "insufficient_data", "samples": n, "required": MIN_SAMPLES_TO_TRAIN}
        try:
            import lightgbm as lgb
            self._lgb = lgb
            dataset = lgb.Dataset(X, label=y)
            params = {
                "objective": "binary",
                "metric": "binary_logloss",
                "learning_rate": 0.05,
                "num_leaves": 15,
                "min_data_in_leaf": 3,
                "verbose": -1,
            }
            self._model = lgb.train(params, dataset, num_boost_round=100)
            self.MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._model.save_model(str(self.MODEL_PATH))
            self._trained = True
            return {"status": "trained", "samples": n, "model_path": str(self.MODEL_PATH)}
        except Exception as exc:
            log.error("HirePredict training failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    def predict(self, candidates: list[dict]) -> list[dict]:
        """
        Attach hire_probability and retention_prediction to each candidate.
        Falls back to a heuristic score when model is not trained.
        """
        for c in candidates:
            features = self._extract_features(c)
            if self._trained and self._model is not None:
                try:
                    X = np.array([[features.get(col, 0.0) for col in FEATURE_COLS]], dtype=np.float32)
                    prob = float(self._model.predict(X)[0])
                except Exception:
                    prob = self._heuristic_prob(features)
            else:
                prob = self._heuristic_prob(features)
            c["hire_probability"] = round(prob, 4)
            c["hire_predict_label"] = (
                "high" if prob >= 0.70 else
                "medium" if prob >= 0.45 else
                "low"
            )
        return candidates

    @staticmethod
    def _extract_features(c: dict) -> dict:
        return {
            "embedding_similarity":    c.get("embedding_similarity", c.get("score", 0.5)),
            "rerank_score":            c.get("rerank_score", 0.5),
            "years_experience_match":  c.get("years_experience_match", 0.5),
            "skill_overlap_ratio":     c.get("skill_overlap_ratio", 0.5),
            "recency_of_activity":     c.get("recency_of_activity", 0.5),
            "career_trajectory_slope": c.get("career_trajectory_slope", 0.5),
            "engagement_score":        c.get("engagement_score", 0.5),
            "trust_score":             c.get("trust_score", 1.0),
            "intent_score":            c.get("intent_score", 0.5),
        }

    @staticmethod
    def _heuristic_prob(f: dict) -> float:
        """Weighted heuristic blend when model is not yet trained."""
        return min(1.0, max(0.0,
            0.25 * f.get("embedding_similarity", 0.5) +
            0.20 * f.get("rerank_score", 0.5) +
            0.15 * f.get("skill_overlap_ratio", 0.5) +
            0.15 * f.get("trust_score", 1.0) +
            0.15 * f.get("intent_score", 0.5) +
            0.10 * f.get("years_experience_match", 0.5)
        ))

    def accuracy_report(self) -> dict:
        n = self.store.count_outcomes()
        return {
            "total_outcomes": n,
            "model_trained": self._trained,
            "min_samples_required": MIN_SAMPLES_TO_TRAIN,
            "model_path": str(self.MODEL_PATH) if self._trained else None,
            "ready": self._trained,
            "note": (
                "Model trained and ready." if self._trained else
                f"Collecting outcomes ({n}/{MIN_SAMPLES_TO_TRAIN}). Using heuristic fallback."
            ),
        }
