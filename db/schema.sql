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
    dct_vec     vector(128),      -- DCT Frequency Signature (v3)
    spatial_vec vector(256),      -- CLIP Spatial Attention (v3)
    phash       text,             
    dhash       text,             
    ahash       text,             
    audio_fp    bytea,            -- Audio Chromaprint
    audio_mel   vector(128),      -- Audio Mel-CNN vector
    watermarked boolean DEFAULT false,
    created_at  timestamptz DEFAULT now()
);

-- ── Violations table ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS violations (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id     uuid REFERENCES assets(id) ON DELETE CASCADE,
    source       text,            
    fusion_score float4,
    severity     text,            
    clip_score   float4,
    phash_score  float4,
    dct_score    float4,
    spatial_score float4,
    is_ai_clone  boolean DEFAULT false,
    transform    text,            
    detected_at  timestamptz DEFAULT now(),
    dmca_sent    boolean DEFAULT false,
    bundle_url   text             -- URL to legal evidence bundle
);

-- ── Viral Spread Table (v3) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS spread_incidents (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id     uuid REFERENCES assets(id),
    incident_id  uuid REFERENCES violations(id),
    platform     text,
    reach_est    int,
    parent_id    uuid REFERENCES spread_incidents(id),
    captured_at  timestamptz DEFAULT now()
);
