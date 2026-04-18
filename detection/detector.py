"""
Detector — Full async detection pipeline.

    Input (file/URL)
        → Validate & Fetch
        → Preprocess
        → 4-Layer DNA (parallel)
        → FAISS Query
        → Fusion Score re-rank
        → Watermark check (CRITICAL only)
        → Alert + Store
"""
import asyncio
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

import httpx
import numpy as np
from PIL import Image

from config import settings
from detection.faiss_index import FAISSIndex
from detection.fusion import FusionResult, compute_fusion_score, classify_severity
from fingerprint.clip_embedder import get_clip_embedding
from fingerprint.phash import extract_phashes, PerceptualHashes
from fingerprint.color_moments import extract_color_moments
from fingerprint.hog import extract_hog_descriptor
from watermark.dct_extract import extract_watermark

from detection.platform_simulator import apply_simulators
from fingerprint.dct_freq import extract_dct_frequency_signature
from fingerprint.spatial_attention import extract_clip_spatial_attention

logger = logging.getLogger(__name__)


@dataclass
class DetectionMatch:
    """Single match result from the detection pipeline."""
    asset_id: str
    fusion_score: float
    clip_score: float
    phash_score: float
    color_score: float
    hog_score: float
    dct_score: float      # v3
    spatial_score: float  # v3
    severity: str
    watermark_match: Optional[bool] = None
    transform_type: str = "unknown"
    is_ai_clone: bool = False # v3


@dataclass
class DetectionResult:
    """Full detection pipeline result."""
    query_id: str
    best_match: Optional[DetectionMatch] = None
    matches: List[DetectionMatch] = field(default_factory=list)
    severity: str = "MISS"
    timestamp: str = ""
    viral_spread: Optional[dict] = None # v3

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


async def fetch_and_validate_url(url: str) -> Image.Image:
    """Fetch an image from a URL (respects robots.txt intent — no scraping)."""
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type and "octet-stream" not in content_type:
            raise ValueError(f"URL did not return an image (content-type: {content_type})")
        return Image.open(io.BytesIO(resp.content)).convert("RGB")


def load_image(file_path: str) -> Image.Image:
    """Load and validate a local image file."""
    img = Image.open(file_path)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


async def extract_all_fingerprints(image: Image.Image):
    """
    Extract all 6 fingerprint layers in parallel. (v3 Apex)
    """
    clip_coro = get_clip_embedding(
        image,
        device=settings.DEVICE,
        model_name=settings.CLIP_MODEL,
        nvidia_api_key=settings.NVIDIA_API_KEY,
        nvidia_api_url=settings.NVIDIA_API_URL,
    )
    phash_coro = extract_phashes(image)
    hog_coro = extract_hog_descriptor(image)
    color_coro = extract_color_moments(image)
    
    # New v3 layers
    dct_sig_coro = asyncio.to_thread(extract_dct_frequency_signature, image)
    spatial_coro = extract_clip_spatial_attention(image, device=settings.DEVICE)

    clip_vec, phashes, hog_vec, color_vec, dct_vec, spatial_vec = await asyncio.gather(
        clip_coro, phash_coro, hog_coro, color_coro, dct_sig_coro, spatial_coro
    )
    return clip_vec, phashes, hog_vec, color_vec, dct_vec, spatial_vec


async def detect_pipeline(
    image: Image.Image,
    faiss_index: FAISSIndex,
    query_id: str = "",
    owner_id: str = "",
    k: int = 20,
    simulate_platforms: bool = True
) -> DetectionResult:
    """
    v3 Apex Detection Pipeline.
    
    1. Simulate Platform Transforms (pre-match simulation).
    2. Extract 6-layer DNA in parallel.
    3. Hybrid FAISS query and Multi-Layer Fusion re-rank.
    4. AI Clone Detection (Semantic Space Analysis).
    5. Forensic Watermark check.
    """
    # v3 feature: Platform simulation
    images_to_check = [image]
    if simulate_platforms:
        images_to_check.extend(apply_simulators(image))

    all_matches = []
    
    for img in images_to_check:
        # Step 2: extract all 6 fingerprints in parallel
        clip_vec, phashes, hog_vec, color_vec, dct_vec, spatial_vec = await extract_all_fingerprints(img)

        # Step 3: FAISS search (CLIP cosine)
        candidates = faiss_index.search_clip(clip_vec, k=k)

        if not candidates:
            continue

        # Step 4: Re-rank with 6-layer fusion score
        for idx, clip_score_raw in candidates:
            meta = faiss_index.get_metadata(idx)
            if meta is None: continue

            cand_clip = faiss_index.get_clip_vector(idx)
            cand_hog, cand_color, cand_dct, cand_spatial = faiss_index.get_vectors(idx)

            if cand_clip is None: continue
            
            # v3 Fusion logic
            fr = compute_fusion_score(
                query_clip=clip_vec,
                query_phash=phashes.phash,
                query_color=color_vec,
                query_hog=hog_vec,
                query_dct=dct_vec,         # v3
                query_spatial=spatial_vec, # v3
                cand_clip=cand_clip,
                cand_phash=meta.get("phash", "0" * 16),
                cand_color=cand_color or np.zeros(9),
                cand_hog=cand_hog or np.zeros(128),
                cand_dct=cand_dct or np.zeros(128),         # v3
                cand_spatial=cand_spatial or np.zeros(256), # v3
                cand_asset_id=meta["asset_id"],
                cand_index_id=idx,
                w_clip=settings.WEIGHT_CLIP,
                w_phash=settings.WEIGHT_PHASH,
                w_color=settings.WEIGHT_COLOR,
                w_hog=settings.WEIGHT_HOG,
                w_dct=settings.WEIGHT_DCT_SIG,         # v3
                w_spatial=settings.WEIGHT_CLIP_SPATIAL, # v3
                t_critical=settings.THRESHOLD_CRITICAL,
                t_high=settings.THRESHOLD_HIGH,
                t_medium=settings.THRESHOLD_MEDIUM,
            )
            
            if fr.severity != "MISS":
                # AI Clone Detection (v3)
                # If high semantic similarity (CLIP) but low perceptual similarity (pHash/DCT)
                # it's likely an img2img attack.
                is_ai_clone = (fr.clip_score > 0.90 and fr.phash_score < 0.60)
                
                dm = DetectionMatch(
                    asset_id=fr.candidate_asset_id,
                    fusion_score=fr.fusion_score,
                    clip_score=fr.clip_score,
                    phash_score=fr.phash_score,
                    color_score=fr.color_score,
                    hog_score=fr.hog_score,
                    dct_score=fr.dct_score,
                    spatial_score=fr.spatial_score,
                    severity=fr.severity,
                    is_ai_clone=is_ai_clone
                )
                all_matches.append(dm)

    # Sort and pick best
    all_matches.sort(key=lambda r: r.fusion_score, reverse=True)
    
    # Deduplicate matches for the same asset_id
    unique_matches = {}
    for m in all_matches:
        if m.asset_id not in unique_matches or m.fusion_score > unique_matches[m.asset_id].fusion_score:
            unique_matches[m.asset_id] = m
    
    matches = sorted(unique_matches.values(), key=lambda r: r.fusion_score, reverse=True)
    best = matches[0] if matches else None

    # Step 5: Watermark check for CRITICAL/HIGH matches
    if best and (best.severity in ["CRITICAL", "HIGH"]) and owner_id:
        try:
            wm = extract_watermark(image, owner_id)
            if wm and wm.checksum_valid:
                best.watermark_match = True
            else:
                best.watermark_match = False
        except Exception:
            best.watermark_match = None

    overall_severity = best.severity if best else "MISS"

    return DetectionResult(
        query_id=query_id,
        best_match=best,
        matches=matches,
        severity=overall_severity,
    )
