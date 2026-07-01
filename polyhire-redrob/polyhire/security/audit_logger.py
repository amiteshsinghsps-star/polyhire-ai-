"""
AuditLogger — writes a machine-readable JSON Lines audit report for every
honeypot flag and sanitization event that fires during a ranking run.

Output: audit_report_<ISO-timestamp>.jsonl next to submission.csv
        (or a caller-specified path).

Format (one JSON object per line):
  {
    "ts": "<ISO-8601>",
    "event": "honeypot_flagged" | "sanitization_flag" | "stream_guard" | "embedding_integrity",
    "candidate_id": "CAND_...",
    "rules": ["rule_a", "rule_b"],   # for honeypot events
    "severity": "high",              # for sanitization events
    "detail": "free-text context"
  }

This file is NOT part of the official submission package — it is for
internal transparency and post-run forensics only.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


class AuditLogger:
    """Append-only structured audit log writer.

    Usage::
        logger = AuditLogger(out_path="audit_report.jsonl")
        logger.log_honeypot(candidate_id, triggered_rules)
        logger.log_sanitization(candidate_id, flags, severity)
        logger.log_stream_guard(candidate_id, reason)
        logger.log_embedding_integrity(path, expected_hash, actual_hash)
        logger.close()

    The logger is also a context manager::
        with AuditLogger("audit.jsonl") as log:
            log.log_honeypot(...)
    """

    def __init__(self, out_path: str | Path | None = None, echo: bool = False) -> None:
        """
        Args:
            out_path: where to write the JSONL audit file.
                      If None, a timestamped file is placed in the CWD.
            echo:     if True, also mirror each event to stderr (for debugging).
        """
        if out_path is None:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            out_path = Path(f"audit_report_{ts}.jsonl")
        self._path = Path(out_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh: TextIO = open(self._path, "a", encoding="utf-8")
        self._echo = echo
        self._counts: dict[str, int] = {}

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #

    def log_honeypot(self, candidate_id: str, triggered_rules: list[str]) -> None:
        """Record a honeypot hard-exclusion."""
        self._write({
            "event": "honeypot_flagged",
            "candidate_id": candidate_id,
            "rules": triggered_rules,
            "detail": f"{len(triggered_rules)} rule(s) triggered",
        })

    def log_sanitization(
        self,
        candidate_id: str,
        flags: list[str],
        severity: str,
        field_ctx: str = "",
    ) -> None:
        """Record a prompt-injection or sanitization alert."""
        self._write({
            "event": "sanitization_flag",
            "candidate_id": candidate_id,
            "rules": flags,
            "severity": severity,
            "detail": f"field={field_ctx}" if field_ctx else "",
        })

    def log_stream_guard(
        self,
        line_no: int,
        reason: str,
        candidate_id: str = "UNKNOWN",
    ) -> None:
        """Record a JSONL stream-guard rejection (malformed / oversized line)."""
        self._write({
            "event": "stream_guard",
            "candidate_id": candidate_id,
            "line_no": line_no,
            "rules": [reason],
            "detail": reason,
        })

    def log_embedding_integrity(
        self,
        artifact_path: str,
        expected_sha256: str,
        actual_sha256: str,
    ) -> None:
        """Record an embedding artifact integrity check (pass or fail)."""
        ok = expected_sha256.lower() == actual_sha256.lower()
        self._write({
            "event": "embedding_integrity",
            "candidate_id": "N/A",
            "artifact": str(artifact_path),
            "expected_sha256": expected_sha256,
            "actual_sha256": actual_sha256,
            "rules": ["integrity_ok" if ok else "integrity_FAIL"],
            "detail": "PASS" if ok else "MISMATCH — embedding artifact may have been tampered",
        })

    def summary(self) -> dict[str, int]:
        """Return event-type → count totals."""
        return dict(self._counts)

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.flush()
            self._fh.close()

    # ------------------------------------------------------------------ #
    # context manager
    # ------------------------------------------------------------------ #

    def __enter__(self) -> "AuditLogger":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # internal
    # ------------------------------------------------------------------ #

    def _write(self, payload: dict) -> None:
        payload["ts"] = datetime.now(timezone.utc).isoformat()
        event = payload.get("event", "unknown")
        self._counts[event] = self._counts.get(event, 0) + 1

        line = json.dumps(payload, ensure_ascii=False)
        self._fh.write(line + "\n")
        self._fh.flush()

        if self._echo:
            print(f"[audit] {line}", file=sys.stderr)
