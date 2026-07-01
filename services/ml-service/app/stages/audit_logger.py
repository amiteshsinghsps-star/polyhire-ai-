"""
Enterprise Feature §23.4 — Compliance & Audit Ledger.

Append-only audit trail with hash-chaining (blockchain-style) so tampering
is detectable. Supports four-fifths-rule disparate impact checks.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger(__name__)


class AuditLogger:
    """
    In-memory / SQLite audit trail. Each entry is hash-chained to the previous
    entry so tampering is detectable. Falls back to in-memory when no DB is available.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._memory_store: list[dict[str, Any]] = []
        self._init_db()

    def _init_db(self) -> None:
        if not self._db_path:
            log.info("No db_path set; audit ledger runs in-memory only.")
            return
        try:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_ledger (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    jd_id           TEXT NOT NULL,
                    candidate_id    TEXT NOT NULL,
                    rank            INTEGER NOT NULL,
                    feature_snapshot TEXT NOT NULL,
                    model_version   TEXT NOT NULL,
                    fusion_score    REAL NOT NULL,
                    timestamp       TEXT NOT NULL,
                    prev_hash       TEXT NOT NULL,
                    entry_hash      TEXT NOT NULL UNIQUE
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_jd ON audit_ledger(jd_id)"
            )
            self._conn.commit()
            log.info("Audit ledger DB initialized at %s.", self._db_path)
        except Exception as exc:  # noqa: BLE001
            log.warning("Audit DB init failed (%s), falling back to memory.", exc)
            self._conn = None

    def _previous_hash(self, jd_id: str) -> str:
        if self._conn:
            row = self._conn.execute(
                "SELECT entry_hash FROM audit_ledger WHERE jd_id = ? ORDER BY id DESC LIMIT 1",
                (jd_id,),
            ).fetchone()
            return row[0] if row else "genesis"
        # Memory fallback
        for entry in reversed(self._memory_store):
            if entry["jd_id"] == jd_id:
                return entry["entry_hash"]
        return "genesis"

    def log_ranking_decision(
        self,
        jd_id: str,
        candidate_id: str,
        rank: int,
        feature_snapshot: dict[str, Any],
        model_version: str,
        fusion_score: float,
    ) -> str:
        prev_hash = self._previous_hash(jd_id)
        timestamp = datetime.now(timezone.utc).isoformat()
        payload = {
            "jd_id": jd_id,
            "candidate_id": candidate_id,
            "rank": rank,
            "feature_snapshot": feature_snapshot,
            "model_version": model_version,
            "fusion_score": fusion_score,
            "timestamp": timestamp,
            "prev_hash": prev_hash,
        }
        entry_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()

        entry = {
            "id": len(self._memory_store) + 1,
            "jd_id": jd_id,
            "candidate_id": candidate_id,
            "rank": rank,
            "feature_snapshot": feature_snapshot,
            "model_version": model_version,
            "fusion_score": fusion_score,
            "timestamp": timestamp,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
        }

        if self._conn:
            self._conn.execute(
                """INSERT INTO audit_ledger
                (jd_id, candidate_id, rank, feature_snapshot, model_version,
                 fusion_score, timestamp, prev_hash, entry_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (jd_id, candidate_id, rank,
                 json.dumps(feature_snapshot, default=str),
                 model_version, fusion_score, timestamp, prev_hash, entry_hash),
            )
            self._conn.commit()
        else:
            self._memory_store.append(entry)

        return entry_hash

    def get_trail(self, jd_id: str) -> list[dict[str, Any]]:
        """Returns all audit entries for a JD."""
        if self._conn:
            rows = self._conn.execute(
                "SELECT * FROM audit_ledger WHERE jd_id = ? ORDER BY id ASC",
                (jd_id,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]

        return [e for e in self._memory_store if e["jd_id"] == jd_id]

    def verify_chain_integrity(self, jd_id: str) -> bool:
        """Re-walks the hash chain to confirm no entry has been altered."""
        trail = self.get_trail(jd_id)
        expected_prev = "genesis"
        for entry in trail:
            if entry.get("prev_hash") != expected_prev:
                return False
            payload = {
                "jd_id": entry["jd_id"],
                "candidate_id": entry["candidate_id"],
                "rank": entry["rank"],
                "feature_snapshot": entry["feature_snapshot"],
                "model_version": entry["model_version"],
                "fusion_score": entry["fusion_score"],
                "timestamp": entry["timestamp"],
                "prev_hash": entry["prev_hash"],
            }
            recomputed = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()
            ).hexdigest()
            if recomputed != entry["entry_hash"]:
                return False
            expected_prev = entry["entry_hash"]
        return True

    def get_disparate_impact_report(
        self,
        jd_id: str,
        group_assignments: dict[str, str],
    ) -> dict[str, Any]:
        """
        Computes four-fifths-rule disparate impact across a grouping attribute.
        group_assignments: {candidate_id: group_value}
        """
        trail = self.get_trail(jd_id)
        shortlisted_ids = {e["candidate_id"] for e in trail if e["rank"] <= 20}

        group_stats: dict[str, dict[str, int]] = {}
        for cid, group in group_assignments.items():
            if group not in group_stats:
                group_stats[group] = {"shortlisted": 0, "total": 0}
            group_stats[group]["total"] += 1
            if cid in shortlisted_ids:
                group_stats[group]["shortlisted"] += 1

        rates: dict[str, float] = {}
        for group, stats in group_stats.items():
            rates[group] = stats["shortlisted"] / stats["total"] if stats["total"] else 0.0

        max_rate = max(rates.values()) if rates else 0.0
        flags = {
            g: (r / max_rate < 0.8 if max_rate else False)
            for g, r in rates.items()
        }

        return {
            "selection_rates": rates,
            "four_fifths_rule_flags": flags,
            "total_candidates": len(group_assignments),
        }

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | tuple) -> dict[str, Any]:
        keys = [
            "id", "jd_id", "candidate_id", "rank", "feature_snapshot",
            "model_version", "fusion_score", "timestamp", "prev_hash", "entry_hash",
        ]
        return dict(zip(keys, row))
