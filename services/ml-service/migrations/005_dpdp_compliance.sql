-- =============================================================================
-- PolyHire AI v3.0 — Migration 005: DPDP Compliance Tables
-- India's Digital Personal Data Protection Act (2023) with Rules 2025
-- Idempotent: safe to run multiple times (IF NOT EXISTS throughout)
-- =============================================================================

-- consent_ledger: every data processing event with candidate consent record
CREATE TABLE IF NOT EXISTS consent_ledger (
    id                   BIGSERIAL   PRIMARY KEY,
    event_id             TEXT        NOT NULL UNIQUE DEFAULT gen_random_uuid()::TEXT,
    candidate_id         TEXT        NOT NULL,
    purpose              TEXT        NOT NULL,
    consent_given        BOOLEAN     NOT NULL DEFAULT TRUE,
    lawful_basis         TEXT        NOT NULL DEFAULT 'legitimate_interest_hiring',
    data_fields_accessed JSONB       NOT NULL DEFAULT '[]',
    jd_id                TEXT,
    ip_address           INET,
    user_agent           TEXT,
    recorded_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_consent_candidate ON consent_ledger (candidate_id);
CREATE INDEX IF NOT EXISTS idx_consent_purpose   ON consent_ledger (purpose);
CREATE INDEX IF NOT EXISTS idx_consent_jd        ON consent_ledger (jd_id);
CREATE INDEX IF NOT EXISTS idx_consent_ts        ON consent_ledger (recorded_at DESC);

COMMENT ON TABLE consent_ledger IS
  'DPDP §6: per-candidate consent records. Immutable audit trail for regulatory inspection.';


-- erasure_requests: right-to-erasure requests per DPDP §12
CREATE TABLE IF NOT EXISTS erasure_requests (
    id              BIGSERIAL   PRIMARY KEY,
    request_id      TEXT        NOT NULL UNIQUE DEFAULT gen_random_uuid()::TEXT,
    candidate_id    TEXT        NOT NULL,
    reason          TEXT        NOT NULL DEFAULT 'data_subject_request',
    requester       TEXT        NOT NULL DEFAULT 'candidate',
    status          TEXT        NOT NULL DEFAULT 'pending',  -- pending|processing|completed|failed
    stores_cleared  JSONB       NOT NULL DEFAULT '[]',
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    notes           TEXT,

    CONSTRAINT erasure_status_valid CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_erasure_candidate ON erasure_requests (candidate_id);
CREATE INDEX IF NOT EXISTS idx_erasure_status    ON erasure_requests (status);
CREATE INDEX IF NOT EXISTS idx_erasure_ts        ON erasure_requests (requested_at DESC);

COMMENT ON TABLE erasure_requests IS
  'DPDP §12: right-to-erasure requests. Must be processed within 30 days per Act.';


-- transparency_log: algorithmic decision transparency records
CREATE TABLE IF NOT EXISTS transparency_log (
    id                    BIGSERIAL    PRIMARY KEY,
    log_id                TEXT         NOT NULL UNIQUE DEFAULT gen_random_uuid()::TEXT,
    candidate_id          TEXT         NOT NULL,
    jd_id                 TEXT         NOT NULL,
    rank                  INT,
    score                 NUMERIC(8,6),
    feature_contributions JSONB        DEFAULT '{}',
    explanation           TEXT,
    algorithm             TEXT         NOT NULL DEFAULT 'PolyHire-LightGBM-LambdaRank-v3',
    is_erased             BOOLEAN      NOT NULL DEFAULT FALSE,
    logged_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transparency_candidate ON transparency_log (candidate_id);
CREATE INDEX IF NOT EXISTS idx_transparency_jd        ON transparency_log (jd_id);
CREATE INDEX IF NOT EXISTS idx_transparency_ts        ON transparency_log (logged_at DESC);

COMMENT ON TABLE transparency_log IS
  'DPDP §12 + AI Act: algorithmic transparency for every ranking decision. '
  'Candidates can request their evaluation history.';


-- dpdp_audit_log: general regulatory audit events (breach, access, etc.)
CREATE TABLE IF NOT EXISTS dpdp_audit_log (
    id           BIGSERIAL    PRIMARY KEY,
    event_type   TEXT         NOT NULL,  -- 'jd_validated'|'breach_detected'|'access_logged'|'erasure_completed'
    actor        TEXT,                   -- recruiter ID or 'system'
    resource     TEXT,                   -- candidate_id or jd_id
    details      JSONB        DEFAULT '{}',
    severity     TEXT         NOT NULL DEFAULT 'info',  -- info|warning|critical
    logged_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dpdp_audit_event    ON dpdp_audit_log (event_type);
CREATE INDEX IF NOT EXISTS idx_dpdp_audit_severity ON dpdp_audit_log (severity);
CREATE INDEX IF NOT EXISTS idx_dpdp_audit_ts       ON dpdp_audit_log (logged_at DESC);

COMMENT ON TABLE dpdp_audit_log IS
  'General DPDP regulatory audit log. Required for breach notification within 72 hours.';
