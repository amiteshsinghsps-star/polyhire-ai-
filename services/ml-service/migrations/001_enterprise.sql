-- PolyHire AI — Enterprise Features SQL Migration (§23–24)
-- Run against PostgreSQL 16+ (also works with SQLite for local dev).

-- §23.3 Portfolio optimization
CREATE TABLE IF NOT EXISTS open_roles (
    id                  TEXT PRIMARY KEY,
    jd_id               TEXT,
    shortlist_slots     INTEGER NOT NULL DEFAULT 10,
    status              TEXT DEFAULT 'open',
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS portfolio_assignments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    optimization_run_id TEXT NOT NULL,
    candidate_id        TEXT NOT NULL,
    assigned_role_id    TEXT NOT NULL,
    score                REAL NOT NULL,
    created_at          TEXT DEFAULT (datetime('now'))
);

-- §23.4 Audit & compliance ledger (append-only)
CREATE TABLE IF NOT EXISTS audit_ledger (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    jd_id               TEXT NOT NULL,
    candidate_id        TEXT NOT NULL,
    rank                INTEGER NOT NULL,
    feature_snapshot    TEXT NOT NULL,
    model_version       TEXT NOT NULL,
    fusion_score        REAL NOT NULL,
    timestamp           TEXT NOT NULL,
    prev_hash           TEXT NOT NULL,
    entry_hash          TEXT NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_audit_jd ON audit_ledger(jd_id);

-- §23.6 Passive talent pool mining
CREATE TABLE IF NOT EXISTS role_archetypes (
    id                  TEXT PRIMARY KEY,
    sample_role_titles  TEXT,
    derived_from_jd_count INTEGER DEFAULT 0,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS passive_match_flags (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id        TEXT NOT NULL,
    archetype_id        TEXT NOT NULL,
    similarity          REAL NOT NULL,
    flagged_at          TEXT NOT NULL,
    actioned            INTEGER DEFAULT 0
);

-- §23.7 Interview question cache
CREATE TABLE IF NOT EXISTS interview_questions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id        TEXT NOT NULL,
    jd_id               TEXT,
    question_text       TEXT NOT NULL,
    probes_for          TEXT NOT NULL,
    strong_answer_signal TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

-- §23.8 Model drift monitoring
CREATE TABLE IF NOT EXISTS model_drift_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at          TEXT DEFAULT (datetime('now')),
    drift_detected      INTEGER NOT NULL,
    drifted_features    TEXT,
    recommendation      TEXT
);

-- §23.1 Uncertainty bands extend rankings
-- These columns are added to the in-memory pipeline results, not a separate table.
-- The output_writer.py handles persisting them when a DB is connected.
