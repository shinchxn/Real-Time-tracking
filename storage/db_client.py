"""
Async PostgreSQL DB Client — Content DNA Apex v7.0
Full asyncpg connection pool. All methods async-native.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asyncpg
import numpy as np

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None
_pool_lock = asyncio.Lock()


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is not None:
            return _pool
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/contentdna")
        _pool = await asyncpg.create_pool(
            dsn=database_url, min_size=2, max_size=20,
            command_timeout=30, statement_cache_size=0,
        )
        logger.info("[DB] asyncpg pool initialized (min=2, max=20)")
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("[DB] asyncpg pool closed")


def _vec_to_bytes(arr: np.ndarray) -> bytes:
    return arr.astype(np.float32).tobytes()


def _bytes_to_vec(data: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(data, dtype=np.float32).reshape(dim)


async def register_asset(
    org_id: str, asset_type: str, dna_vector: np.ndarray,
    watermark_seed: int, metadata: Optional[Dict[str, Any]] = None,
    original_filename: str = "", sdna_path: str = "",
) -> str:
    pool = await get_pool()
    dna_bytes = _vec_to_bytes(dna_vector)
    meta_json = json.dumps(metadata or {})
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO registered_assets
                (org_id, asset_type, original_filename, dna_vector,
                 watermark_seed, metadata, sdna_path)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
            RETURNING asset_id::text
            """,
            org_id, asset_type, original_filename,
            dna_bytes, watermark_seed, meta_json, sdna_path,
        )
    asset_id = row["asset_id"]
    logger.info("[DB] Registered asset %s (org=%s, type=%s)", asset_id, org_id, asset_type)
    return asset_id


async def log_sighting(
    asset_id: str, platform: str, source_url: str,
    author_handle: str, fusion_score: float, severity: str,
    layer_scores: Dict[str, float], post_id: str = "",
    proof_type: str = "FORENSIC_VISUAL_MATCH",
    embargo_violation: bool = False,
) -> str:
    pool = await get_pool()
    layer_scores_json = json.dumps(layer_scores)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO sightings
                (asset_id, platform, source_url, author_handle,
                 fusion_score, severity, layer_scores, proof_type, embargo_violation)
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)
            RETURNING sighting_id::text
            """,
            asset_id, platform, source_url, author_handle,
            fusion_score, severity, layer_scores_json, proof_type, embargo_violation,
        )
    sighting_id = row["sighting_id"]
    logger.info("[DB] Logged sighting %s [%s] score=%.3f on %s",
                sighting_id, severity, fusion_score, platform)
    return sighting_id


async def get_recent_sightings(
    org_id: str, hours: int = 24, min_severity: str = "MEDIUM",
) -> List[Dict[str, Any]]:
    severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "MISS": 0}
    min_rank = severity_order.get(min_severity, 2)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.sighting_id::text, s.asset_id::text, s.platform,
                   s.source_url, s.author_handle, s.fusion_score, s.severity,
                   s.layer_scores, s.proof_type, s.embargo_violation,
                   s.detected_at, s.dmca_generated, s.evidence_path
            FROM sightings s
            JOIN registered_assets a ON a.asset_id = s.asset_id
            WHERE a.org_id = $1
              AND s.detected_at >= NOW() - ($2 * INTERVAL '1 hour')
              AND s.severity = ANY($3::text[])
            ORDER BY s.detected_at DESC
            LIMIT 500
            """,
            org_id, hours,
            [k for k, v in severity_order.items() if v >= min_rank],
        )
    result = []
    for row in rows:
        d = dict(row)
        if isinstance(d.get("layer_scores"), str):
            d["layer_scores"] = json.loads(d["layer_scores"])
        if isinstance(d.get("detected_at"), datetime):
            d["detected_at"] = d["detected_at"].isoformat()
        result.append(d)
    return result


async def mark_dmca_generated(sighting_id: str, evidence_path: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE sightings
            SET dmca_generated = TRUE, evidence_path = $1
            WHERE sighting_id = $2::uuid
            """,
            evidence_path, sighting_id,
        )
    logger.info("[DB] DMCA marked for sighting %s", sighting_id)


async def get_asset_by_id(asset_id: str) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT asset_id::text, org_id::text, asset_type, original_filename,
                   dna_vector, watermark_seed, registered_at, metadata, sdna_path
            FROM registered_assets WHERE asset_id = $1::uuid
            """,
            asset_id,
        )
    if not row:
        return None
    d = dict(row)
    if isinstance(d.get("metadata"), str):
        d["metadata"] = json.loads(d["metadata"])
    if isinstance(d.get("registered_at"), datetime):
        d["registered_at"] = d["registered_at"].isoformat()
    return d


async def get_asset_dna_vector(asset_id: str, dim: int = 512) -> Optional[np.ndarray]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT dna_vector FROM registered_assets WHERE asset_id = $1::uuid",
            asset_id,
        )
    if val is None:
        return None
    return _bytes_to_vec(bytes(val), dim)


async def get_org_by_api_key_hash(key_hash: str) -> Optional[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT org_id::text, org_name, plan, rate_limit_scan,
                   public_key_pem, key_fingerprint
            FROM organizations
            WHERE api_key_hash = $1 AND active = TRUE
            """,
            key_hash,
        )
    return dict(row) if row else None


async def get_high_severity_assets_for_rescan(hours: int = 168) -> List[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT asset_id::text FROM sightings
            WHERE severity IN ('HIGH', 'CRITICAL')
              AND detected_at >= NOW() - ($1 * INTERVAL '1 hour')
            """,
            hours,
        )
    return [row["asset_id"] for row in rows]


async def get_upcoming_broadcast_windows() -> List[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT asset_id::text, metadata FROM registered_assets
            WHERE metadata->>'broadcast_window_start' IS NOT NULL
              AND (metadata->>'embargo_until')::timestamptz > NOW()
            ORDER BY (metadata->>'broadcast_window_start')::text ASC
            LIMIT 100
            """,
        )
    result = []
    for row in rows:
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)
        result.append({"asset_id": row["asset_id"], "metadata": meta})
    return result


async def get_session(session_id: str) -> Optional[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT session_data FROM sessions WHERE session_id = $1",
            session_id,
        )
    return val


async def save_session(session_id: str, encrypted_data: str) -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO sessions (session_id, session_data, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (session_id) DO UPDATE
            SET session_data = EXCLUDED.session_data, updated_at = NOW()
            """,
            session_id, encrypted_data,
        )
    logger.info("[DB] Session %s saved", session_id)


async def append_custody_entry(
    asset_id: str, event_type: str,
    actor_hash: str, prev_hash: str,
) -> str:
    import hashlib, time
    entry_content = f"{asset_id}{event_type}{actor_hash}{prev_hash}{time.time_ns()}"
    entry_hash = hashlib.sha3_256(entry_content.encode()).hexdigest()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO custody_log
                (asset_id, event_type, actor_hash, prev_entry_hash, entry_hash)
            VALUES ($1::uuid, $2, $3, $4, $5)
            RETURNING log_id::text
            """,
            asset_id, event_type, actor_hash, prev_hash, entry_hash,
        )
    logger.info("[DB] Custody entry %s for asset %s [%s]",
                row["log_id"], asset_id, event_type)
    return entry_hash


async def get_custody_chain(asset_id: str) -> List[Dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT log_id::text, event_type, actor_hash,
                   prev_entry_hash, entry_hash, logged_at
            FROM custody_log WHERE asset_id = $1::uuid
            ORDER BY logged_at ASC
            """,
            asset_id,
        )
    result = []
    for row in rows:
        d = dict(row)
        if isinstance(d.get("logged_at"), datetime):
            d["logged_at"] = d["logged_at"].isoformat()
        result.append(d)
    return result
