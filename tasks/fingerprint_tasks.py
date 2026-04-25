"""
Celery Tasks — Content DNA Apex v6.0
Core fingerprinting, matching, sighting persistence, DMCA generation,
video processing, and deep rescan tasks.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
from typing import Dict, List, Optional

from tasks.celery_app import app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run a coroutine in Celery worker (which has no running event loop)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # In an async context — use asyncio.run_coroutine_threadsafe
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=120)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ── Task 1: Fingerprint + Match ───────────────────────────────────────────────

@app.task(
    name="tasks.fingerprint_tasks.fingerprint_and_match",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=120,
    time_limit=180,
)
def fingerprint_and_match(
    self,
    media_bytes: bytes,
    source_url: str,
    platform: str,
    author_handle: str = "",
    post_id: str = "",
) -> Optional[Dict]:
    """
    Full 6-layer DNA extraction → FAISS search → fusion scoring → DB log.

    Args:
        media_bytes: Raw image bytes.
        source_url: URL where content was found.
        platform: Platform name (instagram, web, etc.).
        author_handle: @username if available.
        post_id: Platform-native post identifier.

    Returns:
        Dict with sighting_id and severity if a match is found, else None.
    """
    from PIL import Image
    import numpy as np
    from config import settings
    from detection.faiss_index import FAISSIndex
    from detection.detector import extract_all_fingerprints, detect_pipeline

    logger.info("[FingerprintTask] Processing %s from %s", platform, source_url[:60])

    try:
        # Load image from bytes
        image = Image.open(io.BytesIO(media_bytes)).convert("RGB")

        # Get shared FAISS index (loaded once per worker process)
        faiss_index = _get_faiss_index()
        if faiss_index.total_vectors == 0:
            logger.warning("[FingerprintTask] FAISS index empty — no registered assets to match against.")
            return None

        # Run full detection pipeline
        result = _run_async(
            detect_pipeline(image, faiss_index, query_id=post_id or source_url)
        )

        if not result.best_match or result.severity == "MISS":
            return None

        match = result.best_match
        layer_scores = {
            "clip": match.clip_score,
            "phash": match.phash_score,
            "color": match.color_score,
            "hog": match.hog_score,
            "dct": match.dct_score,
            "spatial": match.spatial_score,
        }

        # Persist to PostgreSQL
        sighting_id = _run_async(
            _log_sighting_async(
                asset_id=match.asset_id,
                platform=platform,
                source_url=source_url,
                author_handle=author_handle,
                fusion_score=match.fusion_score,
                severity=match.severity,
                layer_scores=layer_scores,
                post_id=post_id,
            )
        )

        logger.info(
            "[FingerprintTask] MATCH: %s [%s] score=%.3f → sighting=%s",
            match.asset_id, match.severity, match.fusion_score, sighting_id
        )

        # Auto-trigger DMCA for CRITICAL matches
        if match.severity == "CRITICAL" and sighting_id:
            generate_dmca.apply_async(args=[sighting_id], queue="dmca")

        return {
            "sighting_id": sighting_id,
            "asset_id": match.asset_id,
            "severity": match.severity,
            "fusion_score": match.fusion_score,
        }

    except Exception as exc:
        logger.error("[FingerprintTask] Error processing %s: %s", source_url[:60], exc)
        raise self.retry(exc=exc)


# ── Task 2: Video URL Processing ─────────────────────────────────────────────

@app.task(
    name="tasks.fingerprint_tasks.process_video_url",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=300,
    time_limit=360,
)
def process_video_url(
    self,
    video_url: str,
    source_url: str,
    platform: str,
    author_handle: str = "",
) -> Optional[Dict]:
    """
    Extract frames from a video URL and run fingerprint detection on each frame.
    Aggregates results across frames using VideoSighting logic.
    """
    logger.info("[VideoTask] Processing video: %s", video_url[:80])

    try:
        from detection.video_detector import detect_video
        results = _run_async(detect_video(video_url, source_url, platform, author_handle))
        return {"video_sightings": len(results), "results": results}

    except Exception as exc:
        logger.error("[VideoTask] Failed for %s: %s", video_url[:80], exc)
        raise self.retry(exc=exc)


# ── Task 3: Deep Rescan ───────────────────────────────────────────────────────

@app.task(
    name="tasks.fingerprint_tasks.deep_rescan",
    bind=True,
    max_retries=1,
    soft_time_limit=600,
    time_limit=660,
)
def deep_rescan(self, asset_id: str) -> Dict:
    """
    Perform a Top-250 FAISS search sweep for a specific asset_id.
    Replaces BackgroundReEvaluator asyncio.Queue worker.
    Used for weekly re-scan of HIGH/CRITICAL severity assets.
    """
    logger.info("[DeepRescan] Starting rescan for asset %s", asset_id)

    try:
        from storage.db_client import get_asset_by_id
        from detection.faiss_index import FAISSIndex
        import numpy as np

        asset = _run_async(get_asset_by_id(asset_id))
        if not asset:
            return {"status": "not_found", "asset_id": asset_id}

        dna_bytes = asset.get("dna_vector", b"")
        if not dna_bytes:
            return {"status": "no_dna_vector", "asset_id": asset_id}

        faiss_index = _get_faiss_index()
        dim = faiss_index.clip_dim
        clip_vec = np.frombuffer(dna_bytes, dtype=np.float32)[:dim]

        candidates = faiss_index.search_clip(clip_vec, k=250)
        logger.info("[DeepRescan] Asset %s — %d candidates at k=250", asset_id, len(candidates))

        return {
            "status": "complete",
            "asset_id": asset_id,
            "candidates_found": len(candidates),
        }

    except Exception as exc:
        logger.error("[DeepRescan] Error for asset %s: %s", asset_id, exc)
        raise self.retry(exc=exc)


# ── Task 4: Generate DMCA ─────────────────────────────────────────────────────

@app.task(
    name="tasks.fingerprint_tasks.generate_dmca",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=60,
    time_limit=90,
)
def generate_dmca(self, sighting_id: str) -> Dict:
    """
    Generate a DMCA evidence bundle for a confirmed sighting.
    Saves PDF/Markdown to evidence store and updates DB.
    """
    logger.info("[DMCA] Generating bundle for sighting %s", sighting_id)

    try:
        import json
        from detection.dmca_report import generate_dmca_bundle
        from storage.db_client import get_recent_sightings, mark_dmca_generated

        # Resolve evidence directory
        evidence_dir = os.getenv("EVIDENCE_DIR", "data/evidence")
        os.makedirs(evidence_dir, exist_ok=True)

        # Build minimal violation dict from sighting_id
        # (In production, query specific sighting by ID)
        violation = {"id": sighting_id, "source": "pending", "severity": "HIGH", "fusion_score": 0.9}
        asset = {"id": "unknown", "title": "Protected Asset", "owner_id": "org", "created_at": ""}
        report_md = generate_dmca_bundle(violation, asset)

        # Save evidence file
        evidence_path = os.path.join(evidence_dir, f"dmca_{sighting_id}.md")
        with open(evidence_path, "w", encoding="utf-8") as f:
            f.write(report_md)

        # Update DB
        _run_async(mark_dmca_generated(sighting_id, evidence_path))

        logger.info("[DMCA] Bundle saved → %s", evidence_path)
        return {"status": "generated", "evidence_path": evidence_path}

    except Exception as exc:
        logger.error("[DMCA] Error for sighting %s: %s", sighting_id, exc)
        raise self.retry(exc=exc)


# ── Task 5: Persist Sighting (from Scrapy pipeline) ───────────────────────────

@app.task(
    name="tasks.fingerprint_tasks.persist_sighting",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    soft_time_limit=30,
    time_limit=45,
)
def persist_sighting(
    self,
    asset_id: str,
    platform: str,
    source_url: str,
    author_handle: str,
    fusion_score: float,
    severity: str,
    layer_scores: Dict,
    post_id: str = "",
) -> str:
    """Async-safe DB write for Scrapy pipeline sightings."""
    try:
        sighting_id = _run_async(
            _log_sighting_async(
                asset_id=asset_id,
                platform=platform,
                source_url=source_url,
                author_handle=author_handle,
                fusion_score=fusion_score,
                severity=severity,
                layer_scores=layer_scores,
                post_id=post_id,
            )
        )
        return sighting_id
    except Exception as exc:
        raise self.retry(exc=exc)


# ── Internal Helpers ──────────────────────────────────────────────────────────

_faiss_index_cache = None


def _get_faiss_index():
    """
    Load FAISS index once per worker process (cached at module level).
    Volume-mounted path is shared between FastAPI and Celery worker containers.
    """
    global _faiss_index_cache
    if _faiss_index_cache is None:
        from config import settings
        from detection.faiss_index import FAISSIndex
        _faiss_index_cache = FAISSIndex.load_or_create(
            clip_dim=settings.CLIP_EMBEDDING_DIM,
            index_dir=settings.FAISS_INDEX_DIR,
        )
    return _faiss_index_cache


async def _log_sighting_async(
    asset_id: str,
    platform: str,
    source_url: str,
    author_handle: str,
    fusion_score: float,
    severity: str,
    layer_scores: Dict,
    post_id: str = "",
) -> str:
    """Async wrapper for DB sighting log."""
    from storage.db_client import log_sighting
    return await log_sighting(
        asset_id=asset_id,
        platform=platform,
        source_url=source_url,
        author_handle=author_handle,
        fusion_score=fusion_score,
        severity=severity,
        layer_scores=layer_scores,
        post_id=post_id,
    )
