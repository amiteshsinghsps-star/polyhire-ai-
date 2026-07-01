-- Bharat Intelligence Layer — persistence for transparency, audit, and drift monitoring

CREATE TABLE IF NOT EXISTS bil_tier_adjustments (
    id                  SERIAL PRIMARY KEY,
    candidate_id        TEXT,
    jd_id               TEXT,
    city                TEXT,
    detected_tier       TEXT NOT NULL CHECK (detected_tier IN ('tier_1', 'tier_2', 'tier_3')),
    original_engagement NUMERIC NOT NULL,
    normalized_engagement NUMERIC NOT NULL,
    original_recency    NUMERIC NOT NULL,
    normalized_recency  NUMERIC NOT NULL,
    engagement_delta    NUMERIC NOT NULL,
    applied_at          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bil_tier_candidate ON bil_tier_adjustments(candidate_id);
CREATE INDEX IF NOT EXISTS idx_bil_tier_jd ON bil_tier_adjustments(jd_id);

CREATE TABLE IF NOT EXISTS bil_institution_scores (
    id                  SERIAL PRIMARY KEY,
    candidate_id        TEXT,
    raw_institution     TEXT,
    normalized_name     TEXT,
    nirf_score          NUMERIC NOT NULL,
    match_type          TEXT NOT NULL,
    in_nirf_database    BOOLEAN NOT NULL DEFAULT false,
    scored_at           TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bil_institution_cache ON bil_institution_scores(candidate_id, normalized_name);

CREATE TABLE IF NOT EXISTS bil_code_switch_log (
    id                      SERIAL PRIMARY KEY,
    candidate_id            TEXT,
    has_devanagari          BOOLEAN DEFAULT false,
    has_other_indic         BOOLEAN DEFAULT false,
    has_hinglish            BOOLEAN DEFAULT false,
    original_skill_count    INTEGER NOT NULL,
    augmented_skill_count   INTEGER NOT NULL,
    skills_added            TEXT[],
    translation_used        BOOLEAN DEFAULT false,
    detected_at             TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS bil_informal_sector_log (
    id                      SERIAL PRIMARY KEY,
    candidate_id            TEXT,
    detected_patterns       TEXT[],
    informal_sector_score   NUMERIC NOT NULL,
    high_confidence_skills  TEXT[],
    skills_injected         TEXT[],
    explanation             TEXT,
    logged_at               TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE candidates
    ADD COLUMN IF NOT EXISTS city                  TEXT,
    ADD COLUMN IF NOT EXISTS bharat_tier           TEXT,
    ADD COLUMN IF NOT EXISTS institution           TEXT,
    ADD COLUMN IF NOT EXISTS institution_tier_score NUMERIC DEFAULT 0.50,
    ADD COLUMN IF NOT EXISTS informal_sector_score  NUMERIC DEFAULT 0.00,
    ADD COLUMN IF NOT EXISTS code_switch_detected   BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS bharat_context_applied BOOLEAN DEFAULT false;

CREATE OR REPLACE VIEW bharat_shortlist_impact AS
SELECT
    r.jd_id,
    COUNT(*) AS total_shortlisted,
    SUM(CASE WHEN c.bharat_tier IN ('tier_2', 'tier_3') THEN 1 ELSE 0 END) AS tier2_3_shortlisted,
    ROUND(100.0 * SUM(CASE WHEN c.bharat_tier IN ('tier_2', 'tier_3') THEN 1 ELSE 0 END)
          / NULLIF(COUNT(*), 0), 1) AS tier2_3_pct,
    ROUND(AVG(bta.engagement_delta), 4) AS avg_engagement_delta,
    SUM(CASE WHEN c.code_switch_detected THEN 1 ELSE 0 END) AS code_switch_count,
    ROUND(AVG(c.informal_sector_score), 4) AS avg_informal_score
FROM rankings r
JOIN candidates c ON c.id = r.candidate_id
LEFT JOIN bil_tier_adjustments bta ON bta.candidate_id = r.candidate_id AND bta.jd_id = r.jd_id
WHERE r.rank <= 20
GROUP BY r.jd_id;
