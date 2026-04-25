-- Content DNA Apex v7.0 — PostgreSQL Schema
-- Run via: psql $DATABASE_URL -f storage/migrations/001_initial.sql

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Organizations ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS organizations (
    org_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_name TEXT NOT NULL,
    api_key_hash TEXT NOT NULL UNIQUE,
    private_key_encrypted BYTEA NOT NULL,
    public_key_pem TEXT NOT NULL,
    aes_key_encrypted BYTEA NOT NULL,
    key_fingerprint TEXT NOT NULL,
    authorized_domains JSONB DEFAULT '[]',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Registered Assets ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS registered_assets (
    asset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID REFERENCES organizations(org_id),
    asset_type TEXT CHECK (asset_type IN ('image','video','clip')),
    original_filename TEXT,
    dna_vector BYTEA,
    watermark_seed INTEGER,
    sdna_path TEXT,
    metadata JSONB,
    registered_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Sightings ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sightings (
    sighting_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID REFERENCES registered_assets(asset_id),
    platform TEXT,
    source_url TEXT,
    author_handle TEXT,
    fusion_score FLOAT,
    severity TEXT CHECK (severity IN ('CRITICAL','HIGH','MEDIUM','LOW','MISS')),
    layer_scores JSONB,
    proof_type TEXT CHECK (proof_type IN ('SDNA_CONTAINER_MATCH','CRYPTOGRAPHIC_LAYER_MATCH','FORENSIC_VISUAL_MATCH')),
    embargo_violation BOOLEAN DEFAULT FALSE,
    dmca_generated BOOLEAN DEFAULT FALSE,
    evidence_path TEXT,
    detected_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Custody Log ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS custody_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID REFERENCES registered_assets(asset_id),
    event_type TEXT,
    actor_hash TEXT,
    prev_entry_hash TEXT,
    entry_hash TEXT,
    logged_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Sessions ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    session_data TEXT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Stream Assignments (v7.1) ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS stream_assignments (
    stream_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_id TEXT NOT NULL,
    org_id UUID REFERENCES organizations(org_id),
    asset_id UUID REFERENCES registered_assets(asset_id),
    bit_sequence BYTEA NOT NULL,
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    event_metadata JSONB
);

-- ── Leaker Identifications (v7.1) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leaker_identifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sighting_id UUID REFERENCES sightings(sighting_id),
    subscriber_id TEXT,
    stream_id UUID REFERENCES stream_assignments(stream_id),
    confidence FLOAT,
    matched_segments INTEGER,
    total_segments INTEGER,
    identified_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── Indexes ────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_sightings_asset ON sightings(asset_id);
CREATE INDEX IF NOT EXISTS idx_sightings_severity ON sightings(severity);
CREATE INDEX IF NOT EXISTS idx_sightings_detected ON sightings(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_assets_org ON registered_assets(org_id);

COMMIT;
