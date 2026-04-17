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
    severity: str
    watermark_match: Optional[bool] = None
    transform_type: str = "unknown"


@dataclass
class DetectionResult:
    """Full detection pipeline result."""
    query_id: str
    best_match: Optional[DetectionMatch] = None
    matches: List[DetectionMatch] = field(default_factory=list)
    severity: str = "MISS"
    timestamp: str = ""

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
    Extract all 4 fingerprint layers in parallel.

    Returns:
        (clip_vec, phashes, hog_vec, color_vec)
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

    clip_vec, phashes, hog_vec, color_vec = await asyncio.gather(
        clip_coro, phash_coro, hog_coro, color_coro,
    )
    return clip_vec, phashes, hog_vec, color_vec


async def detect_pipeline(
    image: Image.Image,
    faiss_index: FAISSIndex,
    query_id: str = "",
    owner_id: str = "",
    k: int = 20,
) -> DetectionResult:
    """
    Full async detection pipeline.

    Steps:
        1. Parallel 4-layer fingerprint extraction.
        2. FAISS approximate nearest neighbor (CLIP).
        3. Re-rank candidates with fusion score.
        4. Watermark check on CRITICAL candidates.
        5. Classify severity and build result.
    """
    # Step 1: extract all fingerprints in parallel
    clip_vec, phashes, hog_vec, color_vec = await extract_all_fingerprints(image)

    # Step 2: FAISS search (CLIP cosine / inner product)
    candidates = faiss_index.search_clip(clip_vec, k=k)

    if not candidates:
        return DetectionResult(query_id=query_id, severity="MISS")

    # Step 3: Re-rank with fusion score
    fusion_results: List[FusionResult] = []
    for idx, clip_score_raw in candidates:
        meta = faiss_index.get_metadata(idx)
        if meta is None:
            continue

        cand_clip = faiss_index.get_clip_vector(idx)
        cand_hog, cand_color = faiss_index.get_vectors(idx)

        if cand_clip is None:
            continue
        if cand_hog is None:
            cand_hog = np.zeros(128, dtype=np.float32)
        if cand_color is None:
            cand_color = np.zeros(9, dtype=np.float32)

        fr = compute_fusion_score(
            query_clip=clip_vec,
            query_phash=phashes.phash,
            query_color=color_vec,
            query_hog=hog_vec,
            cand_clip=cand_clip,
            cand_phash=meta.get("phash", "0" * 16),
            cand_color=cand_color,
            cand_hog=cand_hog,
            cand_asset_id=meta["asset_id"],
            cand_index_id=idx,
            w_clip=settings.WEIGHT_CLIP,
            w_phash=settings.WEIGHT_PHASH,
            w_color=settings.WEIGHT_COLOR,
            w_hog=settings.WEIGHT_HOG,
            t_critical=settings.THRESHOLD_CRITICAL,
            t_high=settings.THRESHOLD_HIGH,
            t_medium=settings.THRESHOLD_MEDIUM,
        )
        fusion_results.append(fr)

    # Sort by fusion score descending
    fusion_results.sort(key=lambda r: r.fusion_score, reverse=True)

    # Build detection matches
    matches: List[DetectionMatch] = []
    for fr in fusion_results:
        if fr.severity == "MISS":
            continue
        dm = DetectionMatch(
            asset_id=fr.candidate_asset_id,
            fusion_score=fr.fusion_score,
            clip_score=fr.clip_score,
            phash_score=fr.phash_score,
            color_score=fr.color_score,
            hog_score=fr.hog_score,
            severity=fr.severity,
        )
        matches.append(dm)

    best = matches[0] if matches else None

    # Step 4: Watermark check for CRITICAL matches
    if best and best.severity == "CRITICAL" and owner_id:
        try:
            wm = extract_watermark(image, owner_id)
            if wm and wm.checksum_valid:
                best.watermark_match = True
            else:
                best.watermark_match = False
        except Exception:
            logger.exception("Watermark extraction failed during detection")
            best.watermark_match = None

    overall_severity = best.severity if best else "MISS"

    return DetectionResult(
        query_id=query_id,
        best_match=best,
        matches=matches,
        severity=overall_severity,
    )
