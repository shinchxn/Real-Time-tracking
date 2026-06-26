"""
AI Detection Routes — Content DNA Apex
Deepfake, diffusion artifact, and AI-clone detection endpoints
"""
import io
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from PIL import Image

from auth.rate_limiter import limiter, LIMIT_AI

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ai/detect-generated")
@limiter.limit(LIMIT_AI)
async def detect_generated(request: Request, file: UploadFile = File(...)):
    """Detect if an image was AI-generated (diffusion model artifacts)."""
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        from ai_detection.diffusion_detector import detect_diffusion_artifacts
        score = detect_diffusion_artifacts(image)
        return JSONResponse({
            "filename": file.filename,
            "diffusion_score": round(score, 4),
            "ai_generated": score > 0.82,
            "confidence": "HIGH" if score > 0.90 else "MEDIUM" if score > 0.75 else "LOW",
            "detector": "wavelet_LL3_spectral"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/detect-manipulation")
@limiter.limit(LIMIT_AI)
async def detect_manipulation(request: Request, file: UploadFile = File(...)):
    """Detect deepfake / GAN manipulation artifacts."""
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        from ai_detection.deepfake_detector import detect_deepfake
        score = detect_deepfake(image)
        return JSONResponse({
            "filename": file.filename,
            "manipulation_score": round(score, 4),
            "manipulated": score > 0.75,
            "confidence": "HIGH" if score > 0.85 else "MEDIUM" if score > 0.65 else "LOW",
            "detector": "laplacian_variance"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/detect-clone")
@limiter.limit(LIMIT_AI)
async def detect_clone(request: Request, file: UploadFile = File(...)):
    """Detect if an image is an AI-generated clone of a registered asset."""
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")

        from ai_detection.deepfake_detector import detect_deepfake
        from ai_detection.diffusion_detector import detect_diffusion_artifacts
        from detection.detector import detect_pipeline

        deepfake_score = detect_deepfake(image)
        diffusion_score = detect_diffusion_artifacts(image)

        faiss_index = request.app.state.faiss_index
        detection_result = await detect_pipeline(image, faiss_index)

        is_clone = False
        matched_asset = None
        if detection_result.best_match:
            bm = detection_result.best_match
            # AI clone: semantically similar (high CLIP) but pixel-different (low pHash)
            is_clone = bm.clip_score > 0.88 and bm.phash_score < 0.55
            matched_asset = {
                "asset_id": bm.asset_id,
                "clip_similarity": round(bm.clip_score, 4),
                "pixel_similarity": round(bm.phash_score, 4),
            }

        return JSONResponse({
            "filename": file.filename,
            "is_ai_clone": is_clone,
            "ai_scores": {
                "deepfake": round(deepfake_score, 4),
                "diffusion": round(diffusion_score, 4),
            },
            "matched_asset": matched_asset,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
