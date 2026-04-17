"""
POST /detect  — File upload detection.
POST /check-url — URL-based detection.

Both endpoints run the full detection pipeline and return
fusion-scored matches with severity classification.
"""
import io
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel
from typing import List, Optional

from config import settings
from detection.detector import (
    DetectionResult,
    detect_pipeline,
    fetch_and_validate_url,
    load_image,
)
from db.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)
router = APIRouter()


class DetectMatch(BaseModel):
    asset_id: str
    fusion_score: float
    clip_score: float
    phash_score: float
    color_score: float
    hog_score: float
    severity: str
    watermark_match: Optional[bool] = None


class DetectResponse(BaseModel):
    query_id: str
    severity: str
    best_match: Optional[DetectMatch] = None
    matches: List[DetectMatch] = []
    timestamp: str


class CheckURLRequest(BaseModel):
    url: str
    owner_id: str = ""


def _get_deps():
    from main import app_state
    return app_state["faiss_index"], app_state["supabase"]


def _result_to_response(result: DetectionResult) -> DetectResponse:
    """Convert internal DetectionResult to API response."""
    matches = []
    for m in result.matches:
        matches.append(DetectMatch(
            asset_id=m.asset_id,
            fusion_score=round(m.fusion_score, 4),
            clip_score=round(m.clip_score, 4),
            phash_score=round(m.phash_score, 4),
            color_score=round(m.color_score, 4),
            hog_score=round(m.hog_score, 4),
            severity=m.severity,
            watermark_match=m.watermark_match,
        ))

    best = None
    if result.best_match:
        bm = result.best_match
        best = DetectMatch(
            asset_id=bm.asset_id,
            fusion_score=round(bm.fusion_score, 4),
            clip_score=round(bm.clip_score, 4),
            phash_score=round(bm.phash_score, 4),
            color_score=round(bm.color_score, 4),
            hog_score=round(bm.hog_score, 4),
            severity=bm.severity,
            watermark_match=bm.watermark_match,
        )

    return DetectResponse(
        query_id=result.query_id,
        severity=result.severity,
        best_match=best,
        matches=matches,
        timestamp=result.timestamp,
    )


async def _store_violation(result: DetectionResult, source: str, supabase: SupabaseClient):
    """Store violation in DB if severity is not MISS."""
    if result.severity == "MISS" or result.best_match is None:
        return
    bm = result.best_match
    await supabase.insert_violation({
        "asset_id": bm.asset_id,
        "source": source,
        "fusion_score": bm.fusion_score,
        "severity": bm.severity,
        "clip_score": bm.clip_score,
        "phash_dist": 0,
        "transform": bm.transform_type,
    })


@router.post("/detect", response_model=DetectResponse)
async def detect_file(
    file: UploadFile = File(...),
    owner_id: str = "",
):
    """
    Upload a file → extract Content DNA → run fusion-scored detection → return matches + alerts.
    """
    faiss_index, supabase = _get_deps()
    query_id = str(uuid.uuid4())

    if file.filename is None:
        raise HTTPException(status_code=400, detail="Filename required")

    try:
        contents = await file.read()
        from PIL import Image
        image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid image: {exc}")

    try:
        result = await detect_pipeline(
            image=image,
            faiss_index=faiss_index,
            query_id=query_id,
            owner_id=owner_id,
            k=20,
        )

        # Store violation asynchronously
        await _store_violation(result, source="upload", supabase=supabase)

        return _result_to_response(result)

    except Exception as exc:
        logger.exception("Detect pipeline failed")
        raise HTTPException(status_code=500, detail=f"Detection failed: {exc}")


@router.post("/check-url", response_model=DetectResponse)
async def check_url(body: CheckURLRequest):
    """
    Fetch image from URL → validate → detect → return result.
    No scraping — respects content-type validation.
    """
    faiss_index, supabase = _get_deps()
    query_id = str(uuid.uuid4())

    if not body.url:
        raise HTTPException(status_code=400, detail="URL is required")

    try:
        image = await fetch_and_validate_url(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to fetch URL: {exc}")

    try:
        result = await detect_pipeline(
            image=image,
            faiss_index=faiss_index,
            query_id=query_id,
            owner_id=body.owner_id,
            k=20,
        )
        await _store_violation(result, source=body.url, supabase=supabase)
        return _result_to_response(result)

    except Exception as exc:
        logger.exception("URL check pipeline failed")
        raise HTTPException(status_code=500, detail=f"Detection failed: {exc}")
