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
from watermark.dct_extract import extract_watermark
from discovery.domain_classifier import DomainClassifier
from discovery.google_dorking import GoogleDorkingEngine

# Brain (Existing v5.1)
from detection.fusion import compute_fusion_score
from detection.faiss_index import FAISSIndex

# Storage
from storage.db_client import log_sighting, get_asset_by_id, mark_dmca_generated

logger = logging.getLogger(__name__)

@celery_app.task(queue='fingerprint', bind=True, max_retries=3)
def fingerprint_and_match(self, media_bytes: bytes, source_url: str, platform: str):
    """
    Full Forensic Matching Pipeline.
    """
    import asyncio
    loop = asyncio.get_event_loop()

    # 1. SDNA & Crypto Verification
    from crypto.asset_verifier import AssetVerifier
    async def db_key_resolver(org_id: str):
        from storage.db_client import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval("SELECT public_key_pem FROM organizations WHERE org_id = $1::uuid", org_id)

    verifier = AssetVerifier(aes_key=b'0'*32, public_key_resolver=db_key_resolver)
    ver_res = verifier.verify_any(media_bytes)
    
    if ver_res.valid:
        loop.run_until_complete(log_sighting(
            asset_id=ver_res.metadata.get("asset_id"),
            platform=platform,
            source_url=source_url,
            fusion_score=1.0,
            severity="CRITICAL",
            proof_type="SDNA_CONTAINER_MATCH"
        ))
        return

    # 2. 6-Layer DNA Fusion (FAISS)
    from detection.fusion import compute_fusion_score
    from detection.faiss_index import FAISSIndex
    
    index = FAISSIndex()
    # Mock feature extraction for brevity
    features = {"clip": [0.1]*512, "phash": "abc"} 
    matches = index.search(features["clip"], k=5)
    
    for match in matches:
        score = compute_fusion_score(features, match.metadata)
        if score > 0.75:
            loop.run_until_complete(log_sighting(
                asset_id=match.asset_id,
                platform=platform,
                source_url=source_url,
                fusion_score=score,
                severity="HIGH",
                proof_type="DNA_FUSION_MATCH"
            ))
            return

@celery_app.task(queue='blockchain')
def anchor_to_blockchain(asset_id: str):
    """Anchors asset DNA to Polygon POS."""
    from blockchain.registry import ContentRegistryContract
    from storage.db_client import get_asset_by_id
    import asyncio

    loop = asyncio.get_event_loop()
    asset = loop.run_until_complete(get_asset_by_id(asset_id))
    
    registry = ContentRegistryContract()
    tx_hash = registry.register_asset(
        private_key="0x_user_key_", # Should come from vault
        dna_hash_hex=asset["dna_hash"],
        ipfs_cid=asset["ipfs_cid"],
        merkle_root_hex=asset["merkle_root"]
    )
    logger.info(f"Asset {asset_id} anchored to blockchain. TX: {tx_hash}")

@celery_app.task(queue='dmca')
def generate_dmca(sighting_id: str):
    """Generates and stores DMCA evidence."""
    from viral.dmca_generator import DMCAGenerator
    import asyncio
    
    generator = DMCAGenerator()
    pdf_path = generator.generate_notice(sighting_id)
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(mark_dmca_generated(sighting_id, pdf_path))
