"""
POST /watermark/embed  — Embed invisible DCT watermark.
POST /watermark/extract — Extract hidden watermark from image.
"""
import io
import logging
import os
import shutil
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from config import settings
from watermark.dct_embed import embed_watermark
from watermark.dct_extract import extract_watermark

logger = logging.getLogger(__name__)
router = APIRouter()


class EmbedRequest(BaseModel):
    asset_id: str
    owner_id: str


class EmbedResponse(BaseModel):
    status: str
    asset_id: str
    owner_id: str
    message: str


class ExtractResponse(BaseModel):
    status: str
    asset_id_hash: Optional[str] = None
    owner_id_hash: Optional[str] = None
    checksum_valid: bool = False
    message: str


@router.post("/watermark/embed")
async def watermark_embed(
    file: UploadFile = File(...),
    asset_id: str = "",
    owner_id: str = "",
):
    """
    Embed invisible DCT watermark into the uploaded image.
    Returns the watermarked image as a PNG stream.
    """
    if not asset_id or not owner_id:
        raise HTTPException(status_code=400, detail="asset_id and owner_id are required")

    try:
        from PIL import Image
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")

        watermarked = embed_watermark(
            image=image,
            asset_id=asset_id,
            owner_id=owner_id,
            alpha=settings.WATERMARK_ALPHA,
        )

        # Return watermarked image as PNG
        buf = io.BytesIO()
        watermarked.save(buf, format="PNG", quality=95)
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename=watermarked_{asset_id[:8]}.png",
                "X-Asset-Id": asset_id,
                "X-Owner-Id": owner_id,
                "X-Watermark-Status": "embedded",
            },
        )

    except Exception as exc:
        logger.exception("Watermark embedding failed")
        raise HTTPException(status_code=500, detail=f"Embedding failed: {exc}")


@router.post("/watermark/extract", response_model=ExtractResponse)
async def watermark_extract(
    file: UploadFile = File(...),
    owner_id: str = "",
):
    """
    Extract hidden watermark from any image.
    Requires the owner_id that was used for embedding (PN sequence seed).
    """
    if not owner_id:
        raise HTTPException(status_code=400, detail="owner_id is required for extraction")

    try:
        from PIL import Image
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")

        result = extract_watermark(image=image, owner_id=owner_id)

        if result is None:
            return ExtractResponse(
                status="not_found",
                checksum_valid=False,
                message="No valid watermark found or checksum mismatch.",
            )

        return ExtractResponse(
            status="found",
            asset_id_hash=f"{result.asset_id_hash:016x}",
            owner_id_hash=f"{result.owner_id_hash:08x}",
            checksum_valid=result.checksum_valid,
            message="Watermark successfully extracted and verified.",
        )

    except Exception as exc:
        logger.exception("Watermark extraction failed")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}")
