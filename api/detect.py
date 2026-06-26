"""Detection API — 6-layer DNA + deepfake + diffusion + viral"""
import io, logging
from fastapi import APIRouter, UploadFile, File, Request, HTTPException, Query
from PIL import Image
from detection.detector import detect_pipeline, fetch_and_validate_url

logger = logging.getLogger(__name__)
router = APIRouter()


def _ai_scores(image: Image.Image) -> dict:
    out = {"deepfake_score": 0.0, "diffusion_score": 0.0, "ai_generated": False}
    try:
        from ai_detection.deepfake_detector import detect_deepfake
        out["deepfake_score"] = round(detect_deepfake(image), 4)
    except Exception as e:
        logger.debug("deepfake: %s", e)
    try:
        from ai_detection.diffusion_detector import detect_diffusion_artifacts
        out["diffusion_score"] = round(detect_diffusion_artifacts(image), 4)
    except Exception as e:
        logger.debug("diffusion: %s", e)
    out["ai_generated"] = (
        out["deepfake_score"] > 0.75 or out["diffusion_score"] > 0.82
    )
    return out


@router.post("/detect")
async def detect(request: Request, file: UploadFile = File(...)):
    try:
        image = Image.open(io.BytesIO(await file.read())).convert("RGB")
        result = await detect_pipeline(image, request.app.state.faiss_index)
        ai = _ai_scores(image)
        spread = {}
        if result.best_match:
            try:
                spread = request.app.state.spread_graph.get_metrics(
                    result.best_match.asset_id
                )
            except Exception:
                pass
        resp = {
            "query_id": result.query_id,
            "severity": result.severity,
            "timestamp": result.timestamp,
            "ai_detection": ai,
            "viral_spread": spread,
            "best_match": None,
            "all_matches": [],
        }
        if result.best_match:
            bm = result.best_match
            resp["best_match"] = {
                "asset_id": bm.asset_id,
                "fusion_score": round(bm.fusion_score, 4),
                "severity": bm.severity,
                "is_ai_clone": bm.is_ai_clone,
                "layer_scores": {
                    k: round(getattr(bm, f"{k}_score"), 4)
                    for k in ["clip","phash","color","hog","dct","spatial"]
                },
            }
        resp["all_matches"] = [
            {"asset_id": m.asset_id,
             "fusion_score": round(m.fusion_score, 4),
             "severity": m.severity}
            for m in result.matches[:10]
        ]
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-url")
async def check_url(request: Request, url: str = Query(...)):
    try:
        image = await fetch_and_validate_url(url)
        result = await detect_pipeline(image, request.app.state.faiss_index)
        ai = _ai_scores(image)
        resp = {"url": url, "severity": result.severity, "ai_detection": ai,
                "best_match": None}
        if result.best_match:
            bm = result.best_match
            resp["best_match"] = {
                "asset_id": bm.asset_id,
                "fusion_score": round(bm.fusion_score, 4),
                "severity": bm.severity,
            }
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/asset/{id}")
async def get_asset(id: str, request: Request):
    for idx, meta in request.app.state.faiss_index.metadata.items():
        if meta.get("asset_id") == id:
            return {"status": "found", "id": id, "faiss_idx": idx,
                    "metadata": meta}
    raise HTTPException(status_code=404, detail="Asset not found")


@router.post("/verify")
async def verify_asset(request: Request, file: UploadFile = File(...)):
    try:
        from crypto.asset_verifier import AssetVerifier
        r = await AssetVerifier().verify_any(await file.read())
        return {"valid": r.valid, "layers_detected": r.layers_detected,
                "proof_chain": r.proof_chain, "metadata": r.metadata,
                "reason": r.reason}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
