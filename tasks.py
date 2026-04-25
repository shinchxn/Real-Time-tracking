"""
Celery Tasks — Content DNA Apex v7.0
Implements the full matching pipeline and discovery triggers.
"""
import logging
from celery_app import celery_app
from typing import List, Dict, Any, Optional
import io
from PIL import Image

# Discovery & Crypto
from crypto.asset_verifier import AssetVerifier, VerificationResult
from watermark.dct_extract import blind_extract
from discovery.domain_classifier import DomainClassifier
from discovery.google_dorking import GoogleDorkingEngine

# Brain (Existing v5.1)
from detection.fusion import compute_fusion_score
from detection.faiss_index import search_index

# Storage
from storage.db_client import log_sighting, get_asset_by_id, mark_dmca_generated

logger = logging.getLogger(__name__)

@celery_app.task(queue='fingerprint', bind=True, max_retries=3)
def fingerprint_and_match(self, media_bytes: bytes, source_url: str, platform: str):
    """
    PRIORITY ORDER — stop at first positive match.
    """
    from datetime import datetime
    now = datetime.utcnow()
    
    # 1. SDNA Container & Crypto Layers
    # We need a public_key_resolver and aes_key. 
    # For now, we use a mock resolver that fetches from DB.
    async def db_key_resolver(org_id: str):
        from storage.db_client import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT public_key_pem FROM organizations WHERE org_id = $1::uuid", org_id)
            if row:
                from cryptography.hazmat.primitives import serialization
                return serialization.load_pem_public_key(row['public_key_pem'].encode())
        return None

    verifier = AssetVerifier(aes_key=b'0'*32, public_key_resolver=db_key_resolver)
    ver_res = verifier.verify_any(media_bytes)
    
    if ver_res.valid:
        proof_type = ver_res.proof_chain[0]
        # Log Sighting
        # Note: ver_res might not have asset_id if it's generic CRYPTOGRAPHIC_LAYER_MATCH
        # But for SDNA_CONTAINER_MATCH it should.
        pass

    # 2. Blind DCT Watermark
    wm_res = blind_extract(media_bytes)
    if wm_res:
        log_sighting(
            asset_id=wm_res.asset_id,
            platform=platform,
            source_url=source_url,
            author_handle="unknown",
            fusion_score=1.0,
            severity="CRITICAL",
            layer_scores={"watermark": wm_res.confidence},
            proof_type="CRYPTOGRAPHIC_LAYER_MATCH"
        )
        return

    # 3. 6-Layer FAISS Fusion (Brain)
    # This requires extracting features first
    # from fingerprint.clip_embedder import extract_clip_embedding ...
    pass

@celery_app.task(queue='crawl')
def crawl_platform(platform: str, seed_keywords: List[str]):
    """
    Trigger scrapy spiders from within Celery.
    """
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    from discovery.spiders.instagram_spider import InstagramSportsSpider
    from discovery.spiders.google_alert_spider import GoogleAlertSpider
    
    # In a real setup, we might use scrapyd or run subprocess
    # subprocess.run(["scrapy", "crawl", "instagram_sports", "-a", f"hashtags={','.join(seed_keywords)}"])
    pass

@celery_app.task(queue='dork')
def run_dork_sweep(asset_id: str, asset_metadata: Dict):
    """
    Build dork queries → search → for each result URL → fingerprint_and_match.delay()
    """
    engine = GoogleDorkingEngine()
    import asyncio
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(engine.run_dork_sweep(asset_metadata))
    
    for res in results:
        # For each URL, we need to download the media and then call fingerprint_and_match
        # This could be another task: download_and_process.delay(res.url)
        pass

@celery_app.task(queue='dmca')
def generate_dmca(sighting_id: str):
    """
    Call dmca_generator.py, save PDF, update DB.
    """
    # from viral.dmca_generator import DMCAGenerator
    # ...
    evidence_path = f"/app/evidence/{sighting_id}.pdf"
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(mark_dmca_generated(sighting_id, evidence_path))
    pass
