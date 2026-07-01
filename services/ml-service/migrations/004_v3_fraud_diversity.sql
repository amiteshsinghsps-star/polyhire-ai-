-- =============================================================================
-- PolyHire AI v3.0 — Migration 004: Fraud & Diversity Tables
-- Idempotent: safe to run multiple times (IF NOT EXISTS throughout)
-- =============================================================================

-- fraud_signals: per-candidate fraud assessment records
CREATE TABLE IF NOT EXISTS fraud_signals (
    id              BIGSERIAL PRIMARY KEY,
    candidate_id    TEXT        NOT NULL,
    jd_id           TEXT,
    fraud_risk_score NUMERIC(5,4) NOT NULL DEFAULT 0.0,
    fraud_label     TEXT        NOT NULL DEFAULT 'clean',  -- clean|suspicious|high_risk|blocked
    fraud_flags     JSONB       NOT NULL DEFAULT '[]',
    detector_scores JSONB       NOT NULL DEFAULT '{}',
    trust_penalty   NUMERIC(5,4) NOT NULL DEFAULT 0.0,
    recruiter_action TEXT,
    assessed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fraud_label_valid CHECK (fraud_label IN ('clean', 'suspicious', 'high_risk', 'blocked')),
    CONSTRAINT fraud_risk_range  CHECK (fraud_risk_score BETWEEN 0 AND 1)
);

CREATE INDEX IF NOT EXISTS idx_fraud_signals_candidate ON fraud_signals (candidate_id);
CREATE INDEX IF NOT EXISTS idx_fraud_signals_label     ON fraud_signals (fraud_label);
CREATE INDEX IF NOT EXISTS idx_fraud_signals_jd        ON fraud_signals (jd_id);
CREATE INDEX IF NOT EXISTS idx_fraud_signals_assessed  ON fraud_signals (assessed_at DESC);

COMMENT ON TABLE fraud_signals IS
  'ResumeShield™ — per-candidate fraud assessments. fraud_label drives recruiter dashboard badges.';


-- diversity_audit: per-pipeline-run shortlist diversity metrics
CREATE TABLE IF NOT EXISTS diversity_audit (
    id               BIGSERIAL PRIMARY KEY,
    jd_id            TEXT        NOT NULL,
    diversity_score  NUMERIC(5,4),  -- Shannon entropy normalised [0,1]
    entropy_bits     NUMERIC(6,4),
    tier_distribution JSONB        DEFAULT '{}',
    institution_bias_detected BOOLEAN DEFAULT FALSE,
    elite_concentration NUMERIC(5,4),
    jd_gender_bias   TEXT,          -- neutral|masculine|feminine
    jd_bias_score    NUMERIC(5,4),
    changes_made     INT           DEFAULT 0,
    audited_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_diversity_audit_jd  ON diversity_audit (jd_id);
CREATE INDEX IF NOT EXISTS idx_diversity_audit_ts  ON diversity_audit (audited_at DESC);

COMMENT ON TABLE diversity_audit IS
  'DiverseHire™ — shortlist diversity entropy + JD language bias audit trail.';


-- vector_integrity_log: HMAC verification and poison detection events
CREATE TABLE IF NOT EXISTS vector_integrity_log (
    id              BIGSERIAL PRIMARY KEY,
    candidate_id    TEXT        NOT NULL,
    event_type      TEXT        NOT NULL,  -- 'hmac_ok'|'hmac_fail'|'poison_detected'|'norm_outlier'
    evidence        JSONB       NOT NULL DEFAULT '[]',
    vector_norm     NUMERIC(12,6),
    z_score         NUMERIC(8,4),
    logged_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vec_integrity_candidate ON vector_integrity_log (candidate_id);
CREATE INDEX IF NOT EXISTS idx_vec_integrity_event     ON vector_integrity_log (event_type);
CREATE INDEX IF NOT EXISTS idx_vec_integrity_ts        ON vector_integrity_log (logged_at DESC);

COMMENT ON TABLE vector_integrity_log IS
  'Vector DB Security — HMAC verification and RAG poisoning detection events.';
