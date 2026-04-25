-- Supabase Complete Schema

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE assets (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id         uuid NOT NULL,
  title            text,
  media_type       text CHECK(media_type IN ('image','video','audio')),
  file_path        text,
  clip_vec         vector(768),
  spatial_attn     vector(196),
  dct_freq_vec     vector(512),
  hog_vec          vector(128),
  color_vec        vector(9),
  audio_mel        vector(256),
  face_vec         vector(512),
  phash text, dhash text, whash text, ahash text,
  dct_wm_embedded  boolean DEFAULT false,
  dwt_wm_embedded  boolean DEFAULT false,
  filename_beacon  text,
  blockchain_tx    text,
  ipfs_cid         text,
  zk_commitment    text,
  scan_schedule    text DEFAULT 'STANDARD_ASSET',
  last_proactive_scan timestamptz,
  ai_generated_prob float4,
  created_at       timestamptz DEFAULT now()
);

CREATE TABLE violations (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id         uuid REFERENCES assets(id),
  source_url       text,
  platform         text,
  fusion_score     float4,
  clip_score       float4,
  phash_dist       int,
  hog_score        float4,
  dct_score        float4,
  severity         text,
  transform_type   text,
  detection_channel text,
  viral_depth      int DEFAULT 0,
  dmca_status      text DEFAULT 'pending',
  blockchain_logged boolean DEFAULT false,
  detected_at      timestamptz DEFAULT now()
);

CREATE TABLE sightings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id uuid REFERENCES assets(id),
  source_url text, platform text,
  reported_by text, detection_channel text,
  score float4, ts timestamptz DEFAULT now()
);

CREATE TABLE beacon_nodes (
  id uuid PRIMARY KEY, owner_id uuid,
  capabilities text[], credits_earned int DEFAULT 0,
  sightings_submitted int DEFAULT 0
);

CREATE TABLE partners (
  id uuid PRIMARY KEY, name text,
  webhook_inbound_url text, webhook_outbound_url text,
  api_key_hash text
);

CREATE TABLE spread_graph (
  parent_id uuid REFERENCES violations(id),
  child_id uuid REFERENCES violations(id),
  similarity float4, transform text,
  created_at timestamptz DEFAULT now()
);
