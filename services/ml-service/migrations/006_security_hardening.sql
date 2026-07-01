-- =============================================================================
-- Migration 006: Security Hardening (PII encryption + security event tables)
-- Idempotent — safe to re-run.
-- =============================================================================

-- ── pgcrypto for column-level PII encryption ──────────────────────────────
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ── PII encryption columns ────────────────────────────────────────────────
ALTER TABLE candidates
    ADD COLUMN IF NOT EXISTS name_enc   BYTEA,
    ADD COLUMN IF NOT EXISTS email_enc  BYTEA,
    ADD COLUMN IF NOT EXISTS phone_enc  BYTEA;

-- Encrypt existing plaintext data (runs on first migration, idempotent via WHERE)
DO $$
BEGIN
    IF current_setting('app.pii_key', true) IS NOT NULL
       AND current_setting('app.pii_key', true) <> '' THEN
        UPDATE candidates
        SET
            name_enc  = pgp_sym_encrypt(COALESCE(name,  ''), current_setting('app.pii_key', true)),
            email_enc = pgp_sym_encrypt(COALESCE(email, ''), current_setting('app.pii_key', true)),
            phone_enc = pgp_sym_encrypt(COALESCE(phone, ''), current_setting('app.pii_key', true))
        WHERE name_enc IS NULL AND (name IS NOT NULL OR email IS NOT NULL OR phone IS NOT NULL);
    END IF;
END $$;

-- ── Decryption view (internal service use only) ───────────────────────────
CREATE OR REPLACE VIEW candidates_decrypted AS
SELECT
    id,
    CASE
        WHEN name_enc IS NOT NULL AND current_setting('app.pii_key', true) <> ''
        THEN pgp_sym_decrypt(name_enc,  current_setting('app.pii_key', true))
        ELSE name
    END AS name,
    CASE
        WHEN email_enc IS NOT NULL AND current_setting('app.pii_key', true) <> ''
        THEN pgp_sym_decrypt(email_enc, current_setting('app.pii_key', true))
        ELSE email
    END AS email,
    CASE
        WHEN phone_enc IS NOT NULL AND current_setting('app.pii_key', true) <> ''
        THEN pgp_sym_decrypt(phone_enc, current_setting('app.pii_key', true))
        ELSE phone
    END AS phone,
    city, years_experience, skills, bharat_tier,
    trust_score, fraud_risk_score, fraud_label,
    erased_at, created_at, updated_at
FROM candidates;

-- ── Secure upsert function ────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION insert_candidate_encrypted(
    p_id           TEXT,
    p_name         TEXT,
    p_email        TEXT,
    p_phone        TEXT,
    p_city         TEXT,
    p_yoe          INTEGER,
    p_skills       TEXT[],
    p_bharat_tier  TEXT
) RETURNS VOID AS $$
DECLARE
    pii_key TEXT := current_setting('app.pii_key', true);
BEGIN
    IF pii_key IS NULL OR pii_key = '' THEN
        -- Fallback: store plaintext in development if key not configured
        INSERT INTO candidates (id, name, email, phone, city, years_experience, skills, bharat_tier)
        VALUES (p_id, p_name, p_email, p_phone, p_city, p_yoe, p_skills, p_bharat_tier)
        ON CONFLICT (id) DO UPDATE SET
            name = p_name, email = p_email, phone = p_phone, updated_at = NOW();
    ELSE
        INSERT INTO candidates (id, name_enc, email_enc, phone_enc, city, years_experience, skills, bharat_tier)
        VALUES (
            p_id,
            pgp_sym_encrypt(COALESCE(p_name,  ''), pii_key),
            pgp_sym_encrypt(COALESCE(p_email, ''), pii_key),
            pgp_sym_encrypt(COALESCE(p_phone, ''), pii_key),
            p_city, p_yoe, p_skills, p_bharat_tier
        )
        ON CONFLICT (id) DO UPDATE SET
            name_enc  = pgp_sym_encrypt(COALESCE(p_name,  ''), pii_key),
            email_enc = pgp_sym_encrypt(COALESCE(p_email, ''), pii_key),
            phone_enc = pgp_sym_encrypt(COALESCE(p_phone, ''), pii_key),
            updated_at = NOW();
    END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ── Security event log ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS security_events (
    id            BIGSERIAL PRIMARY KEY,
    event_type    TEXT        NOT NULL,
    recruiter_id  TEXT        NOT NULL DEFAULT 'system',
    severity      TEXT        NOT NULL DEFAULT 'medium',  -- low | medium | high | critical
    details       JSONB       NOT NULL DEFAULT '{}',
    ip_address    INET,
    user_agent    TEXT,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_security_events_type      ON security_events (event_type);
CREATE INDEX IF NOT EXISTS idx_security_events_occurred  ON security_events (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_events_severity  ON security_events (severity) WHERE severity IN ('high', 'critical');

-- ── Honeypot integrity log ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS honeypot_integrity_log (
    id                   BIGSERIAL PRIMARY KEY,
    jd_id                TEXT        NOT NULL,
    is_intact            BOOLEAN     NOT NULL DEFAULT TRUE,
    alert_level          TEXT        NOT NULL DEFAULT 'none',
    honeypots_injected   INTEGER     NOT NULL DEFAULT 3,
    honeypots_in_top_20  INTEGER     NOT NULL DEFAULT 0,
    compromised_detail   JSONB,
    check_timestamp      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_honeypot_log_jd   ON honeypot_integrity_log (jd_id);
CREATE INDEX IF NOT EXISTS idx_honeypot_log_alert ON honeypot_integrity_log (alert_level) WHERE alert_level <> 'none';

-- ── Rate limiting tracker (per recruiter, per endpoint) ───────────────────
CREATE TABLE IF NOT EXISTS rate_limit_log (
    recruiter_id  TEXT        NOT NULL,
    endpoint      TEXT        NOT NULL,
    window_start  TIMESTAMPTZ NOT NULL,
    request_count INTEGER     NOT NULL DEFAULT 1,
    PRIMARY KEY (recruiter_id, endpoint, window_start)
);
