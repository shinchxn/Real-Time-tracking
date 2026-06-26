-- Merged Forensic AI Schema (v7.1 Apex)
-- Combines .sdna forensic identity with pgvector similarity search

BEGIN;

-- 1. Enable Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 2. Organizations (Authentication & Identity)
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

-- 3. Assets (The "Forensic Vault")
-- Now using pgvector for DNA storage
CREATE TABLE IF NOT EXISTS assets (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id           UUID REFERENCES organizations(org_id),
    title            TEXT,
    media_type       TEXT CHECK(media_type IN ('image','video','audio')),
    original_filename TEXT,
    sdna_path        TEXT,
    
    -- AI DNA Vectors (pgvector)
    clip_vec         VECTOR(768),
    spatial_attn     VECTOR(196),
    dct_freq_vec     VECTOR(512),
    hog_vec          VECTOR(128),
    color_vec        VECTOR(9),
    
    watermark_seed   INTEGER,
    metadata         JSONB,
    blockchain_tx    TEXT,
    ipfs_cid         TEXT,
    zk_commitment    TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Sightings & Violations (Discovery Logs)
CREATE TABLE IF NOT EXISTS sightings (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id         UUID REFERENCES assets(id),
    platform         TEXT,
    source_url       TEXT,
    author_handle    TEXT,
    fusion_score     FLOAT4,
    severity         TEXT CHECK (severity IN ('CRITICAL','HIGH','MEDIUM','LOW','MISS')),
    layer_scores     JSONB,
    proof_type       TEXT CHECK (proof_type IN ('SDNA_CONTAINER_MATCH','CRYPTOGRAPHIC_LAYER_MATCH','FORENSIC_VISUAL_MATCH')),
    dmca_generated   BOOLEAN DEFAULT FALSE,
    evidence_path    TEXT,
    detected_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Leaker Identification (Analog Hole Defense)
CREATE TABLE IF NOT EXISTS stream_assignments (
    stream_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_id    TEXT NOT NULL,
    org_id           UUID REFERENCES organizations(org_id),
    asset_id         UUID REFERENCES assets(id),
    bit_sequence     BYTEA NOT NULL,
    assigned_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS leaker_identifications (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sighting_id      UUID REFERENCES sightings(id),
    subscriber_id    TEXT,
    stream_id        UUID REFERENCES stream_assignments(stream_id),
    confidence       FLOAT,
    identified_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Viral Spread Graph
CREATE TABLE IF NOT EXISTS spread_graph (
    parent_id        UUID REFERENCES sightings(id),
    child_id         UUID REFERENCES sightings(id),
    similarity       FLOAT4,
    transform        TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Indexes (For speed)
CREATE INDEX IF NOT EXISTS idx_assets_clip ON assets USING hnsw (clip_vec vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_sightings_asset ON sightings(asset_id);
CREATE INDEX IF NOT EXISTS idx_sightings_detected ON sightings(detected_at DESC);

COMMIT;
