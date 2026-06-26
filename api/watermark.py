"""
Watermark Routes — Content DNA Apex
Embed and extract DCT + DWT watermarks on demand
"""
import base64
import io
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from fastapi.responses import JSONResponse
from PIL import Image

from auth.rate_limiter import limiter, LIMIT_WATERMARK
from watermark.dct_embed import embed_dct_watermark
from watermark.dct_extract import extract_watermark as extract_dct
from watermark.dwt_embed import embed_dwt_watermark

router = APIRouter()
_WM_SEED = int(os.getenv("WATERMARK_MASTER_SEED", str(0xDEADBEEF)), 16)


@router.post("/watermark/embed/dct")
@limiter.limit(LIMIT_WATERMARK)
async def embed_dct(request: Request, file: UploadFile = File(...)):
    """Embed invisible DCT watermark (survives JPEG compression)."""
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        asset_id_int = int(uuid.uuid4().hex[:15], 16)
        ts = int(datetime.now().timestamp())
        wm = embed_dct_watermark(image, asset_id=asset_id_int, owner_id=0xDEAD,
                                  timestamp=ts, watermark_seed=_WM_SEED)
        buf = io.BytesIO()
        wm.save(buf, format="PNG")
        return JSONResponse({
            "method": "DCT",
            "watermarked_image": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}",
            "note": "Invisible watermark embedded in frequency domain"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/watermark/embed/dwt")
@limiter.limit(LIMIT_WATERMARK)
async def embed_dwt(request: Request, file: UploadFile = File(...)):
    """Embed invisible DWT watermark (survives resize and crop)."""
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        asset_id_int = int(uuid.uuid4().hex[:15], 16)
        ts = int(datetime.now().timestamp())
        wm = embed_dwt_watermark(image, asset_id=asset_id_int, owner_id=0xDEAD, timestamp=ts)
        buf = io.BytesIO()
        wm.save(buf, format="PNG")
        return JSONResponse({
            "method": "DWT",
            "watermarked_image": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}",
            "note": "Invisible watermark embedded in wavelet domain"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/watermark/embed/both")
@limiter.limit(LIMIT_WATERMARK)
async def embed_both(request: Request, file: UploadFile = File(...)):
    """Embed both DCT + DWT watermarks (maximum resilience)."""
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        asset_id_int = int(uuid.uuid4().hex[:15], 16)
        ts = int(datetime.now().timestamp())
        wm = embed_dct_watermark(image, asset_id=asset_id_int, owner_id=0xDEAD,
                                  timestamp=ts, watermark_seed=_WM_SEED)
        wm = embed_dwt_watermark(wm, asset_id=asset_id_int, owner_id=0xDEAD, timestamp=ts)
        buf = io.BytesIO()
        wm.save(buf, format="PNG")
        return JSONResponse({
            "method": "DCT+DWT",
            "watermarked_image": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}",
            "note": "Dual-layer invisible watermark embedded"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/watermark/extract")
@limiter.limit(LIMIT_WATERMARK)
async def watermark_extract(request: Request, file: UploadFile = File(...)):
    """Extract and verify DCT watermark from an image."""
    try:
        contents = await file.read()
        result = extract_dct(contents)
        if result:
            return JSONResponse({
                "watermark_found": True,
                "asset_id": result.get("asset_id"),
                "org_id": result.get("org_id"),
                "confidence": round(result.get("confidence", 0.0), 4),
                "signed_at": result.get("signed_at"),
            })
        return JSONResponse({"watermark_found": False, "asset_id": None})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
