-- ============================================================
-- Content DNA — Supabase DDL  (PostgreSQL + pgvector)
-- Run this migration against your Supabase SQL editor.
-- ============================================================

-- Enable pgvector extension (Supabase has this built-in)
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Assets table ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS assets (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    uuid NOT NULL,
    title       text,
    file_path   text,             -- Supabase Storage path
    clip_vec    vector(768),      -- CLIP ViT-L/14 embedding
    hog_vec     vector(128),      -- HOG edge descriptor
    color_vec   vector(9),        -- HSV color moments
    phash       text,             -- 64-bit perceptual hash (hex)
    dhash       text,             -- 64-bit difference hash (hex)
    ahash       text,             -- 64-bit average hash (hex)
    watermarked boolean DEFAULT false,
    created_at  timestamptz DEFAULT now()
);

-- Index for vector similarity search (IVFFlat on CLIP)
CREATE INDEX IF NOT EXISTS idx_assets_clip_vec
    ON assets USING ivfflat (clip_vec vector_cosine_ops)
    WITH (lists = 256);

-- ── Violations table ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS violations (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id     uuid REFERENCES assets(id) ON DELETE CASCADE,
    source       text,            -- URL or 'upload'
    fusion_score float4,
    severity     text,            -- CRITICAL / HIGH / MEDIUM
    clip_score   float4,
    phash_dist   int,
    transform    text,            -- detected attack type
    detected_at  timestamptz DEFAULT now()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_violations_severity
    ON violations (severity);
CREATE INDEX IF NOT EXISTS idx_violations_detected_at
    ON violations (detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_violations_asset_id
    ON violations (asset_id);

-- ── Supabase Storage bucket (create via dashboard or API) ───
-- INSERT INTO storage.buckets (id, name, public)
-- VALUES ('content-dna-assets', 'content-dna-assets', false);
