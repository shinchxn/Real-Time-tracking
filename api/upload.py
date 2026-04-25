import base64
import io
import logging
import traceback
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, Request, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image

from detection.detector import extract_all_fingerprints
from watermark.dct_embed import embed_dct_watermark

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload")
async def upload_asset(request: Request, file: UploadFile = File(...)):
    """
    Registers a new original asset into the Content DNA system.
    1. Extract 6-layer forensic DNA.
    2. Store in FAISS vector search index.
    3. Embed invisible DCT watermark.
    4. Return JSON metadata + base64 watermarked image.
    """
    try:
        # 1. Load image
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        logger.info(f"Registering asset: {file.filename}")
        
        # 2. Forensic DNA Extraction (6-layer)
        dna_pkg = await extract_all_fingerprints(image)
        clip_vec, phashes, hog_vec, color_vec, dct_vec, spatial_vec = dna_pkg["global"]
        
        # 3. Registration in Vector Store
        asset_id = str(uuid.uuid4())
        
        faiss_index = request.app.state.faiss_index
        idx = faiss_index.add(
            asset_id=asset_id,
            clip_vec=clip_vec,
            hog_vec=hog_vec,
            color_vec=color_vec,
            dct_vec=dct_vec,
            spatial_vec=spatial_vec,
            phash=str(phashes.phash),
            metadata={"filename": file.filename, "registered_at": datetime.now(timezone.utc).isoformat()}
        )
        
        # 4. Watermark Embedding (Invisible DCT)
        owner_id_placeholder = 123456
        watermarked_img = embed_dct_watermark(
            image, 
            asset_id=int(uuid.uuid4().hex[:15], 16),
            owner_id=owner_id_placeholder,
            timestamp=int(datetime.now().timestamp())
        )
        
        # 5. Encode watermarked image as base64 for JSON transport
        img_io = io.BytesIO()
        watermarked_img.save(img_io, format="PNG")
        img_b64 = base64.b64encode(img_io.getvalue()).decode("ascii")
        
        logger.info(f"Successfully registered asset {asset_id} at FAISS index {idx}")
        
        return JSONResponse(content={
            "status": "registered",
            "asset_id": asset_id,
            "faiss_id": int(idx),
            "filename": file.filename,
            "fingerprints": {
                "clip_dim": len(clip_vec),
                "hog_dim": len(hog_vec),
                "color_dim": len(color_vec),
                "dct_dim": len(dct_vec),
                "spatial_dim": len(spatial_vec),
                "phash": str(phashes.phash),
            },
            "watermarked_image": f"data:image/png;base64,{img_b64}",
        })
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload/video")
async def upload_video():
    return {"status": "feature_coming_soon", "version": "5.2-alpha"}
