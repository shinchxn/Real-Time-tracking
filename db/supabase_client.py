"""
Supabase Client — Async wrapper for assets / violations tables.

Graceful degradation: if Supabase is unavailable, writes are queued
to a local SQLite database and synced on reconnect.
"""
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import numpy as np

from config import settings

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Async Supabase REST client with SQLite fallback."""

    def __init__(self):
        self.url = settings.SUPABASE_URL.rstrip("/") if settings.SUPABASE_URL else ""
        self.key = settings.SUPABASE_KEY
        self.bucket = settings.SUPABASE_BUCKET
        self._available = bool(self.url and self.key)

        # SQLite fallback
        self._sqlite_path = settings.SQLITE_PATH
        self._init_sqlite()

    # ── SQLite fallback ──────────────────────────────────────────────

    def _init_sqlite(self) -> None:
        os.makedirs(os.path.dirname(self._sqlite_path), exist_ok=True)
        conn = sqlite3.connect(self._sqlite_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                title TEXT,
                file_path TEXT,
                clip_vec TEXT,
                hog_vec TEXT,
                color_vec TEXT,
                dct_vec TEXT,
                spatial_vec TEXT,
                phash TEXT,
                dhash TEXT,
                ahash TEXT,
                audio_fp BLOB,
                audio_mel TEXT,
                watermarked INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                id TEXT PRIMARY KEY,
                asset_id TEXT,
                source TEXT,
                fusion_score REAL,
                severity TEXT,
                clip_score REAL,
                phash_score REAL,
                dct_score REAL,
                spatial_score REAL,
                is_ai_clone INTEGER DEFAULT 0,
                transform TEXT,
                detected_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_sync (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT,
                operation TEXT,
                payload TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def _queue_for_sync(self, table: str, op: str, payload: dict) -> None:
        conn = sqlite3.connect(self._sqlite_path)
        conn.execute(
            "INSERT INTO pending_sync (table_name, operation, payload) VALUES (?, ?, ?)",
            (table, op, json.dumps(payload, default=str)),
        )
        conn.commit()
        conn.close()

    def _headers(self) -> dict:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    # ── Assets ───────────────────────────────────────────────────────

    async def insert_asset(self, asset: dict) -> dict:
        """Insert an asset record. Falls back to SQLite if Supabase is down."""
        asset_id = asset.get("id") or str(uuid.uuid4())
        asset["id"] = asset_id

        # Ensure vectors are serialised as lists
        for vkey in ("clip_vec", "hog_vec", "color_vec"):
            if vkey in asset and isinstance(asset[vkey], np.ndarray):
                asset[vkey] = asset[vkey].tolist()

        if self._available:
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    resp = await c.post(
                        f"{self.url}/rest/v1/assets",
                        headers=self._headers(),
                        json=asset,
                    )
                    resp.raise_for_status()
                    logger.info("Asset %s inserted into Supabase", asset_id)
                    return resp.json()[0] if resp.json() else asset
            except Exception:
                logger.warning("Supabase insert failed — falling back to SQLite")

        # SQLite fallback
        conn = sqlite3.connect(self._sqlite_path)
        conn.execute(
            """INSERT OR REPLACE INTO assets
               (id, owner_id, title, file_path, clip_vec, hog_vec, color_vec,
                dct_vec, spatial_vec, phash, dhash, ahash, audio_mel, watermarked, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                asset_id,
                asset.get("owner_id", ""),
                asset.get("title", ""),
                asset.get("file_path", ""),
                json.dumps(asset.get("clip_vec", [])),
                json.dumps(asset.get("hog_vec", [])),
                json.dumps(asset.get("color_vec", [])),
                json.dumps(asset.get("dct_vec", [])),
                json.dumps(asset.get("spatial_vec", [])),
                asset.get("phash", ""),
                asset.get("dhash", ""),
                asset.get("ahash", ""),
                json.dumps(asset.get("audio_mel", [])),
                int(asset.get("watermarked", False)),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        self._queue_for_sync("assets", "INSERT", asset)
        return asset

    async def get_asset(self, asset_id: str) -> Optional[dict]:
        """Retrieve an asset by ID."""
        if self._available:
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    resp = await c.get(
                        f"{self.url}/rest/v1/assets?id=eq.{asset_id}&select=*",
                        headers=self._headers(),
                    )
                    resp.raise_for_status()
                    rows = resp.json()
                    return rows[0] if rows else None
            except Exception:
                logger.warning("Supabase get_asset failed — falling back to SQLite")

        conn = sqlite3.connect(self._sqlite_path)
        cur = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            cols = ["id", "owner_id", "title", "file_path", "clip_vec", "hog_vec",
                    "color_vec", "phash", "dhash", "ahash", "watermarked", "created_at"]
            return dict(zip(cols, row))
        return None

    # ── Violations ───────────────────────────────────────────────────

    async def insert_violation(self, violation: dict) -> dict:
        """Insert a violation record."""
        vid = violation.get("id") or str(uuid.uuid4())
        violation["id"] = vid

        if self._available:
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    resp = await c.post(
                        f"{self.url}/rest/v1/violations",
                        headers=self._headers(),
                        json=violation,
                    )
                    resp.raise_for_status()
                    logger.info("Violation %s inserted into Supabase", vid)
                    return resp.json()[0] if resp.json() else violation
            except Exception:
                logger.warning("Supabase insert_violation failed — falling back")

        conn = sqlite3.connect(self._sqlite_path)
        conn.execute(
            """INSERT OR REPLACE INTO violations
               (id, asset_id, source, fusion_score, severity, clip_score,
                phash_dist, transform, detected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                vid,
                violation.get("asset_id", ""),
                violation.get("source", ""),
                violation.get("fusion_score", 0.0),
                violation.get("severity", ""),
                violation.get("clip_score", 0.0),
                violation.get("phash_dist", 0),
                violation.get("transform", ""),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        self._queue_for_sync("violations", "INSERT", violation)
        return violation

    async def list_violations(
        self,
        severity: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[dict]:
        """List violations with optional filters."""
        if self._available:
            try:
                params = f"select=*&order=detected_at.desc&limit={limit}&offset={offset}"
                if severity:
                    params += f"&severity=eq.{severity}"
                async with httpx.AsyncClient(timeout=10) as c:
                    resp = await c.get(
                        f"{self.url}/rest/v1/violations?{params}",
                        headers=self._headers(),
                    )
                    resp.raise_for_status()
                    return resp.json()
            except Exception:
                logger.warning("Supabase list_violations failed — falling back")

        conn = sqlite3.connect(self._sqlite_path)
        query = "SELECT * FROM violations"
        params_list = []
        if severity:
            query += " WHERE severity = ?"
            params_list.append(severity)
        query += " ORDER BY detected_at DESC LIMIT ? OFFSET ?"
        params_list.extend([limit, offset])
        cur = conn.execute(query, params_list)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
        return rows

    # ── Health ───────────────────────────────────────────────────────

    async def ping(self) -> bool:
        """Check Supabase availability."""
        if not self._available:
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as c:
                resp = await c.get(
                    f"{self.url}/rest/v1/",
                    headers=self._headers(),
                )
                return resp.status_code < 500
        except Exception:
            return False

    # ── Sync pending writes ──────────────────────────────────────────

    async def sync_pending(self) -> int:
        """Push queued SQLite writes to Supabase. Returns count synced."""
        if not self._available:
            return 0

        conn = sqlite3.connect(self._sqlite_path)
        cur = conn.execute("SELECT id, table_name, operation, payload FROM pending_sync ORDER BY id")
        rows = cur.fetchall()
        synced = 0

        for row_id, table, op, payload_str in rows:
            payload = json.loads(payload_str)
            try:
                async with httpx.AsyncClient(timeout=10) as c:
                    resp = await c.post(
                        f"{self.url}/rest/v1/{table}",
                        headers=self._headers(),
                        json=payload,
                    )
                    if resp.status_code < 400:
                        conn.execute("DELETE FROM pending_sync WHERE id = ?", (row_id,))
                        conn.commit()
                        synced += 1
            except Exception:
                break

        conn.close()
        if synced:
            logger.info("Synced %d pending records to Supabase", synced)
        return synced


# Module-level singleton
supabase = SupabaseClient()
