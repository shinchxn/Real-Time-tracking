"""
Celery Tasks — Content DNA Apex v7.1
Implements the full matching pipeline and discovery triggers.

FIX 7:  All asyncio.get_event_loop replaced with asyncio.run()
FIX 8:  Real CLIP + pHash feature extraction (cached model)
FIX 9:  DomainClassifier integrated into sighting pipeline
FIX 10: Added run_dork_sweep, crawl_platform, deep_rescan tasks
FIX 11: anchor_to_blockchain decrypts key from vault (no hardcoded key)
FIX 12: extract_watermark used as first-pass detection layer
FIX 13: fingerprint_and_match accepts base64-encoded string (JSON-safe)
"""
import asyncio
import base64
import logging

from celery_app import celery_app
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── CLIP model cache (module-level, loaded once per worker) ──────────────────
_clip_model = None
_clip_processor = None


def _get_clip():
    """Lazy-load CLIP model once per Celery worker process."""
    global _clip_model, _clip_processor
    if _clip_model is None:
        from transformers import CLIPModel, CLIPProcessor
        from config import settings
        logger.info("[CLIP] Loading model: %s", settings.CLIP_MODEL)
        _clip_model = CLIPModel.from_pretrained(settings.CLIP_MODEL)
        _clip_processor = CLIPProcessor.from_pretrained(settings.CLIP_MODEL)
        logger.info("[CLIP] Model loaded.")
    return _clip_model, _clip_processor


# ── Task 1: fingerprint_and_match ────────────────────────────────────────────

@celery_app.task(queue='fingerprint', bind=True, max_retries=3)
def fingerprint_and_match(self, media_bytes_b64: str, source_url: str, platform: str):
    """
    Full Forensic Matching Pipeline.
    FIX 13: Accepts base64-encoded string instead of raw bytes (JSON-safe).
    """
    import io
    import numpy as np
    import imagehash
    import torch
    from PIL import Image
    from config import settings
    from detection.faiss_index import FAISSIndex
    from detection.fusion import compute_simple_fusion_score
    from storage.db_client import log_sighting
    from watermark.dct_extract import extract_watermark
    from discovery.domain_classifier import DomainClassifier

    # Decode bytes from base64
    media_bytes = base64.b64decode(media_bytes_b64)

    # ── FIX 12: DCT Watermark as first pass (highest confidence) ────────────
    try:
        wm_result = extract_watermark(media_bytes)
        if wm_result and wm_result.get("asset_id"):
            asyncio.run(log_sighting(
                asset_id=wm_result["asset_id"],
                platform=platform,
                source_url=source_url,
                author_handle="",
                fusion_score=1.0,
                severity="CRITICAL",
                layer_scores={"watermark": 1.0},
                proof_type="DCT_WATERMARK_MATCH"
            ))
            return
    except Exception as e:
        logger.warning("[fingerprint_and_match] Watermark check failed: %s", e)

    # ── FIX 8: Real CLIP + pHash feature extraction ──────────────────────────
    try:
        img = Image.open(io.BytesIO(media_bytes)).convert("RGB")

        # CLIP embedding
        clip_model, clip_processor = _get_clip()
        inputs = clip_processor(images=img, return_tensors="pt")
        with torch.no_grad():
            clip_vec = clip_model.get_image_features(**inputs)
        clip_embedding = clip_vec[0].cpu().numpy().astype(np.float32)

        # Perceptual hash
        phash_val = str(imagehash.phash(img))

        features = {
            "clip": clip_embedding,
            "phash": phash_val
        }
    except Exception as e:
        logger.error("[fingerprint_and_match] Feature extraction failed: %s", e)
        raise self.retry(exc=e, countdown=30)

    # ── FAISS search ──────────────────────────────────────────────────────────
    index = FAISSIndex()
    matches = index.search(features["clip"], k=5)

    for match in matches:
        score = compute_simple_fusion_score(features, match)
        if score > settings.THRESHOLD_MEDIUM:
            # ── FIX 9: Domain classification before logging sighting ─────────
            try:
                classifier = DomainClassifier()
                domain_class = classifier.classify_sync(source_url)
                if domain_class == "legitimate_owner":
                    logger.info("[fingerprint_and_match] Skipping — legitimate owner domain: %s", source_url)
                    return

                severity = "CRITICAL" if domain_class == "piracy_hub" else "HIGH"
            except Exception:
                severity = "HIGH"

            asyncio.run(log_sighting(
                asset_id=match.get("asset_id", ""),
                platform=platform,
                source_url=source_url,
                author_handle="",
                fusion_score=score,
                severity=severity,
                layer_scores={"clip": float(match.get("score", 0)), "phash": score},
                proof_type="DNA_FUSION_MATCH"
            ))

            # Send ntfy push alert for high-severity violations
            if severity in ("CRITICAL", "HIGH"):
                try:
                    from api.alerts_ntfy import send_violation_alert
                    asyncio.run(send_violation_alert(
                        asset_id=match.get("asset_id", ""),
                        source_url=source_url,
                        score=score,
                        severity=severity,
                    ))
                except Exception as e:
                    logger.warning("ntfy alert failed: %s", e)

            return



# ── Task 2: anchor_to_blockchain ─────────────────────────────────────────────

@celery_app.task(queue='blockchain')
def anchor_to_blockchain(asset_id: str):
    """
    FIX 11: Anchors asset DNA to Polygon POS.
    Private key is decrypted from vault — never hardcoded.
    """
    from blockchain.registry import ContentRegistryContract
    from storage.db_client import get_asset_by_id, get_org_by_id
    from cryptography.fernet import Fernet
    from config import settings

    asset = asyncio.run(get_asset_by_id(asset_id))
    if not asset:
        logger.error("anchor_to_blockchain: asset %s not found", asset_id)
        return

    org = asyncio.run(get_org_by_id(asset.get("org_id", "")))
    if not org or not org.get("blockchain_signing_key_enc"):
        logger.error("anchor_to_blockchain: no signing key for org %s", asset.get("org_id"))
        return

    # Decrypt signing key from vault
    fernet = Fernet(settings.BLOCKCHAIN_KEY_ENCRYPTION_KEY.encode())
    private_key = fernet.decrypt(org["blockchain_signing_key_enc"].encode()).decode()

    try:
        registry = ContentRegistryContract()
        tx_hash = registry.register_asset(
            private_key=private_key,
            dna_hash_hex=asset.get("dna_hash", ""),
            ipfs_cid=asset.get("ipfs_cid", ""),
            merkle_root_hex=asset.get("merkle_root", "")
        )
        logger.info("Asset %s anchored. TX: %s", asset_id, tx_hash)
    finally:
        private_key = None  # Explicitly clear from memory


# ── Task 3: generate_dmca ─────────────────────────────────────────────────────

@celery_app.task(queue='dmca')
def generate_dmca(sighting_id: str):
    """Generates and stores DMCA evidence."""
    from viral.dmca_generator import DMCAGenerator
    from storage.db_client import mark_dmca_generated, get_sightings_for_asset, get_asset_by_id, get_org_by_id

    # Fetch sighting record
    async def _get_data():
        from storage.db_client import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            sighting = await conn.fetchrow(
                "SELECT * FROM sightings WHERE sighting_id = $1::uuid",
                sighting_id
            )
        return dict(sighting) if sighting else None

    sighting_record = asyncio.run(_get_data())
    if not sighting_record:
        logger.error("generate_dmca: sighting %s not found", sighting_id)
        return

    asset_record = asyncio.run(get_asset_by_id(sighting_record.get("asset_id", "")))
    org_record = asyncio.run(get_org_by_id(asset_record.get("org_id", ""))) if asset_record else {}

    generator = DMCAGenerator()
    notice_html = generator.generate_notice(
        asset=asset_record or {},
        sighting=sighting_record,
        org=org_record or {},
        fusion_score=float(sighting_record.get("fusion_score", 0.0))
    )

    # Save HTML to evidence dir
    import os
    from config import settings
    os.makedirs(settings.EVIDENCE_DIR, exist_ok=True)
    evidence_path = os.path.join(settings.EVIDENCE_DIR, f"dmca_{sighting_id}.html")
    with open(evidence_path, "w", encoding="utf-8") as f:
        f.write(notice_html)

    asyncio.run(mark_dmca_generated(sighting_id, evidence_path))
    logger.info("DMCA notice generated for sighting %s → %s", sighting_id, evidence_path)


# ── Task 4: run_dork_sweep ────────────────────────────────────────────────────

@celery_app.task(queue='dork', bind=True, max_retries=3)
def run_dork_sweep(self, asset_id: str, asset_record: dict):
    """
    FIX 10: Runs Google dorking sweep for a newly registered asset.
    Finds unauthorized copies across the web using 12+ search templates.
    """
    try:
        from discovery.google_dorking import GoogleDorkingEngine

        engine = GoogleDorkingEngine()
        search_terms = [
            asset_record.get("filename", ""),
            asset_record.get("title", ""),
            asset_id
        ]
        search_terms = [t for t in search_terms if t]

        results = engine.sweep(search_terms)

        logger.info("Dork sweep for asset %s: found %d candidates", asset_id, len(results))

        for result in results:
            fingerprint_and_match.apply_async(
                args=[result.get("media_bytes_b64", ""), result.get("url", ""), result.get("platform", "web")],
                queue='fingerprint'
            )
    except Exception as exc:
        logger.error("run_dork_sweep failed for %s: %s", asset_id, exc)
        raise self.retry(exc=exc, countdown=60)


# ── Task 5: crawl_platform ────────────────────────────────────────────────────

@celery_app.task(queue='crawl', bind=True, max_retries=3)
def crawl_platform(self, platform: str, targets: list):
    """
    FIX 10: Crawls a specific platform (instagram, web) for pirated content.
    Triggered by Celery Beat on schedule.
    """
    import requests as req_lib
    try:
        if platform == "instagram":
            from config import settings
            try:
                from discovery.instagram_crawler import InstagramCrawler
                crawler = InstagramCrawler(
                    username=settings.INSTAGRAM_USERNAME,
                    password=settings.INSTAGRAM_PASSWORD,
                    session_enc=settings.INSTAGRAM_SESSION_ENC,
                    fernet_key=settings.FERNET_KEY
                )
                for hashtag in targets:
                    posts = crawler.crawl_hashtag(hashtag, limit=50)
                    for post in posts:
                        media_b64 = base64.b64encode(post["media_bytes"]).decode()
                        fingerprint_and_match.apply_async(
                            args=[media_b64, post["url"], "instagram"],
                            queue='fingerprint'
                        )
            except ImportError:
                logger.warning("crawl_platform: InstagramCrawler not available, skipping instagram crawl")

        elif platform == "web":
            for feed_url in targets:
                try:
                    resp = req_lib.get(feed_url, timeout=10)
                    resp.raise_for_status()
                    media_b64 = base64.b64encode(resp.content).decode()
                    fingerprint_and_match.apply_async(
                        args=[media_b64, feed_url, "web"],
                        queue='fingerprint'
                    )
                except req_lib.RequestException as e:
                    logger.warning("Failed to fetch %s: %s", feed_url, e)

        else:
            logger.warning("crawl_platform: Unknown platform: %s", platform)

    except Exception as exc:
        logger.error("crawl_platform failed (%s): %s", platform, exc)
        raise self.retry(exc=exc, countdown=120)


# ── Task 6: deep_rescan ───────────────────────────────────────────────────────

@celery_app.task(queue='rescan', bind=True, max_retries=2)
def deep_rescan(self, asset_id: str):
    """
    FIX 10: Re-runs full forensic pipeline on all known sightings for an asset.
    Used when detection model is updated or thresholds change.
    """
    import requests as req_lib
    try:
        from storage.db_client import get_asset_by_id, get_sightings_for_asset

        asset = asyncio.run(get_asset_by_id(asset_id))
        if not asset:
            logger.error("deep_rescan: asset %s not found", asset_id)
            return

        sightings = asyncio.run(get_sightings_for_asset(asset_id))

        logger.info("deep_rescan: rescanning %d sightings for asset %s", len(sightings), asset_id)

        for sighting in sightings:
            try:
                resp = req_lib.get(sighting["source_url"], timeout=15)
                if resp.status_code == 200:
                    media_b64 = base64.b64encode(resp.content).decode()
                    fingerprint_and_match.apply_async(
                        args=[media_b64, sighting["source_url"], sighting["platform"]],
                        queue='fingerprint'
                    )
            except Exception as e:
                logger.warning("deep_rescan: could not fetch %s: %s", sighting.get("source_url"), e)

    except Exception as exc:
        logger.error("deep_rescan failed for %s: %s", asset_id, exc)
        raise self.retry(exc=exc, countdown=120)
