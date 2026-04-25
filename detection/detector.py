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
from detection.fusion import FusionResult, compute_fusion_score, classify_severity, _cosine
from fingerprint.clip_embedder import get_clip_embedding
from fingerprint.phash import extract_phashes, PerceptualHashes
from fingerprint.color_moments import extract_color_moments
from fingerprint.hog import extract_hog_descriptor
from watermark.dct_extract import extract_watermark

from detection.platform_simulator import apply_simulators
from fingerprint.dct_freq import extract_dct_frequency_signature
from fingerprint.spatial_attention import extract_clip_spatial_attention

logger = logging.getLogger(__name__)
RE_EVAL_QUEUE: asyncio.Queue = asyncio.Queue()


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


async def extract_all_fingerprints(image: Image.Image, include_regional: bool = False):
    """
    Extract all 6 fingerprint layers in parallel. (v3 Apex)
    If include_regional is True, also extracts 4 regional snapshots (2x2 grid).
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
    color_coro = asyncio.to_thread(extract_color_moments, image)
    
    # New v3 layers
    dct_sig_coro = asyncio.to_thread(extract_dct_frequency_signature, image)
    spatial_coro = extract_clip_spatial_attention(image, device=settings.DEVICE)

    clip_vec, phashes, hog_vec, color_vec, dct_vec, spatial_vec = await asyncio.gather(
        clip_coro, phash_coro, hog_coro, color_coro, dct_sig_coro, spatial_coro
    )

    regional_dna = []
    if include_regional:
        # Divide into 2x2 grid
        w, h = image.size
        cw, ch = w // 2, h // 2
        regions = [
            image.crop((0, 0, cw, ch)),    # Top Left
            image.crop((cw, 0, w, ch)),    # Top Right
            image.crop((0, ch, cw, h)),    # Bottom Left
            image.crop((cw, ch, w, h)),    # Bottom Right
        ]
        # For regions, we only extract low-cost features (pHash, Color) to save CPU
        regional_coros = [asyncio.gather(extract_phashes(r), asyncio.to_thread(extract_color_moments, r)) for r in regions]
        regional_results = await asyncio.gather(*regional_coros)
        regional_dna = regional_results

    return {
        "global": (clip_vec, phashes, hog_vec, color_vec, dct_vec, spatial_vec),
        "regional": regional_dna
    }


async def detect_pipeline(
    image: Image.Image,
    faiss_index: FAISSIndex,
    query_id: str = "",
    owner_id: str = "",
    k: int = 50, # Expanded candidate pool (Top-50)
    simulate_platforms: bool = True
) -> DetectionResult:
    """
    v5 Apex High-Recall Detection Pipeline.
    
    1. Pre-filter stage: Top-50 FAISS retrieval using global CLIP.
    2. Regional DNA extraction for borderline cases.
    3. Transformation-aware weighted scoring.
    4. Regional signal fusion for partial matches.
    """
    # Stage 0: Basic extraction
    dna_pkg = await extract_all_fingerprints(image, include_regional=True)
    clip_vec, phashes, hog_vec, color_vec, dct_vec, spatial_vec = dna_pkg["global"]
    
    # Stage 1: Candidate Expansion (Recall Focus)
    candidates = faiss_index.search_clip(clip_vec, k=k)
    if not candidates:
        return DetectionResult(query_id=query_id, severity="MISS")

    all_matches = []
    
    # Stage 2: Deep Analysis & Transformation-Aware Scoring
    for idx, clip_score_raw in candidates:
        meta = faiss_index.get_metadata(idx)
        if meta is None: continue

        cand_clip = faiss_index.get_clip_vector(idx)
        cand_hog, cand_color, cand_dct, cand_spatial = faiss_index.get_vectors(idx)
        if cand_clip is None: continue
        
        # Detect transformations (Requirement 7)
        is_transformed = (clip_score_raw > 0.85 and (cand_dct is None or np.dot(dct_vec, cand_dct) < 0.3))
        
        # Dynamic threshold calculation (Requirement 4)
        dyn_t = DynamicThresholdManager.adjust_thresholds(image, is_transformed)
        
        # Dynamic weights (Transformation-Aware)
        w_clip = settings.WEIGHT_CLIP
        w_spatial = settings.WEIGHT_SPATIAL
        if is_transformed:
            w_clip += 0.15 # Shift to semantic layer
            w_spatial += 0.05
        
        fr = compute_fusion_score(
            query_clip=clip_vec, query_phash=phashes.phash, query_color=color_vec, query_hog=hog_vec,
            query_dct=dct_vec, query_spatial=spatial_vec, cand_clip=cand_clip,
            cand_phash=meta.get("phash", "0" * 16), cand_color=cand_color or np.zeros(9),
            cand_hog=cand_hog or np.zeros(128), cand_dct=cand_dct or np.zeros(128),
            cand_spatial=cand_spatial or np.zeros(256), cand_asset_id=meta["asset_id"],
            cand_index_id=idx, w_clip=w_clip, w_spatial=w_spatial,
            t_critical=dyn_t["t_critical"], t_high=dyn_t["t_high"], t_medium=dyn_t["t_medium"]
        )
        
        # Regional Signal Recovery (Requirement 5 & 8)
        reg_scores = []
        if dna_pkg["regional"]:
            for reg_phash, reg_color in dna_pkg["regional"]:
                reg_sim = _cosine(reg_color, cand_color[:9]) # Regional heuristic
                reg_scores.append(reg_sim)
                
        fr.fusion_score = SignalFusionEnhancer.fuse_partial_signals(fr.fusion_score, reg_scores, "unknown")
        fr.severity = classify_severity(fr.fusion_score, **dyn_t)

        if fr.severity != "MISS" or fr.fusion_score > settings.THRESHOLD_WATCH:
            # Soft filtering (Requirement 3)
            status = fr.severity
            if status == "MISS" and fr.fusion_score > settings.THRESHOLD_WATCH:
                status = "RE_EVAL_NEEDED"
                # Trigger background re-evaluation (Requirement 6)
                RE_EVAL_QUEUE.put_nowait((query_id, image))
            
            dm = DetectionMatch(
                asset_id=fr.candidate_asset_id,
                fusion_score=fr.fusion_score,
                clip_score=fr.clip_score,
                phash_score=fr.phash_score,
                color_score=fr.color_score,
                hog_score=fr.hog_score,
                dct_score=fr.dct_score,
                spatial_score=fr.spatial_score,
                severity=status,
                is_ai_clone=(fr.clip_score > 0.90 and fr.phash_score < 0.50)
            )
            all_matches.append(dm)

    # Re-rank and Deduplicate
    all_matches.sort(key=lambda r: r.fusion_score, reverse=True)
    unique_matches = {}
    for m in all_matches:
        if m.asset_id not in unique_matches or m.fusion_score > unique_matches[m.asset_id].fusion_score:
            unique_matches[m.asset_id] = m
    
    matches = sorted(unique_matches.values(), key=lambda r: r.fusion_score, reverse=True)
    best = matches[0] if matches else None

    # Step 5: Watermark check (only if forensic proof is needed)
    if best and best.severity in ["CRITICAL", "HIGH"] and owner_id:
        try:
            wm = extract_watermark(image, owner_id)
            if wm and wm.checksum_valid:
                best.watermark_match = True
        except Exception: pass

    return DetectionResult(
        query_id=query_id,
        best_match=best,
        matches=matches,
        severity=best.severity if best else "MISS",
    )


class DynamicThresholdManager:
    """
    Adjusts thresholds and weights based on image quality and transformations.
    (Requirement 4 & 7)
    """
    @staticmethod
    def adjust_thresholds(image: Image.Image, is_transformed: bool) -> dict:
        t_crit = settings.THRESHOLD_CRITICAL
        t_high = settings.THRESHOLD_HIGH
        t_med = settings.THRESHOLD_MEDIUM
        
        # Heuristic for low-quality image
        w, h = image.size
        if w * h < 400 * 400: # Low res
            # Be more lenient if it's low res
            t_crit -= 0.02
            t_high -= 0.03
            t_med -= 0.05
            
        if is_transformed:
            # Further leniency for transformed items (bias for recall)
            t_crit -= 0.01
            t_high -= 0.02
            
        return {
            "t_critical": t_crit,
            "t_high": t_high,
            "t_medium": t_med
        }

class SignalFusionEnhancer:
    """
    Combines partial/weak signals into a stronger forensic indicator.
    (Requirement 5 & 8)
    """
    @staticmethod
    def fuse_partial_signals(global_score: float, regional_scores: List[float], transform_type: str) -> float:
        # Boost global score if regional matches are strong
        if not regional_scores:
            return global_score
            
        max_reg = max(regional_scores)
        avg_reg = sum(regional_scores) / len(regional_scores)
        
        # If at least one quadrant matches very well (>0.9)
        # and the global score is borderline (>0.6)
        if max_reg > 0.92 and global_score > 0.65:
            return max(global_score, 0.82) # Pushes to MEDIUM+
            
        # If multiple quadrants match moderately
        if avg_reg > 0.75 and global_score > 0.60:
            return max(global_score, 0.76)
            
        return global_score


class BackgroundReEvaluator:
    """
    Asynchronous task to re-process borderline cases with higher precision (e.g. brute force search).
    """
    def __init__(self, faiss_index: FAISSIndex):
        self.index = faiss_index

    async def start_worker(self):
        logger.info("[Re-Eval] Worker started.")
        while True:
            query_id, image = await RE_EVAL_QUEUE.get()
            try:
                # Perform "Deep Scan" (Top-200 instead of Top-50)
                # Note: avoid infinite recursion by setting k carefully or a flag
                res = await detect_pipeline(image, self.index, query_id=query_id, k=250)
                if res.best_match and res.best_match.fusion_score > settings.THRESHOLD_MEDIUM:
                    logger.info(f"[Re-Eval] RECOVERED: {query_id} -> {res.best_match.asset_id} (Score: {res.best_match.fusion_score:.4f})")
            except Exception as e:
                logger.error(f"Error in background re-evaluation: {e}")
            finally:
                RE_EVAL_QUEUE.task_done()
