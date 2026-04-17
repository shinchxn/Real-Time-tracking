"""
POST /upload — Ingest original asset.

Generates all 4 fingerprint layers, stores in FAISS + Supabase,
and optionally uploads the file to Supabase Storage.
"""
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from config import settings
from detection.detector import extract_all_fingerprints, load_image
from detection.faiss_index import FAISSIndex
from db.supabase_client import SupabaseClient
from PIL import Image

logger = logging.getLogger(__name__)
router = APIRouter()


class UploadResponse(BaseModel):
    asset_id: str
    owner_id: str
    filename: str
    status: str
    fingerprints: dict
    timestamp: str


def _get_deps():
    """Retrieve shared app-state singletons (set during lifespan)."""
    from main import app_state
    return app_state["faiss_index"], app_state["supabase"]


@router.post("/upload", response_model=UploadResponse)
async def upload_asset(
    file: UploadFile = File(...),
    owner_id: str = "default-owner",
    title: str = "",
):
    """
    Ingest a new original asset:
      1. Validate + save file.
      2. Extract 4-layer Content DNA (parallel).
      3. Add to FAISS index.
      4. Persist to Supabase / SQLite.
    """
    faiss_index, supabase = _get_deps()

    if file.filename is None:
        raise HTTPException(status_code=400, detail="Filename required")

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Extension '{ext}' not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}",
        )

    asset_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()

    # Save to disk
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, f"{asset_id}_{file.filename}")
    try:
        with open(file_path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"File save failed: {exc}")

    try:
        image = load_image(file_path)
        clip_vec, phashes, hog_vec, color_vec = await extract_all_fingerprints(image)

        # Add to FAISS
        idx = faiss_index.add(
            clip_vec=clip_vec,
            hog_vec=hog_vec,
            color_vec=color_vec,
            asset_id=asset_id,
            phash=phashes.phash,
            dhash=phashes.dhash,
            ahash=phashes.ahash,
            extra_meta={
                "owner_id": owner_id,
                "filename": file.filename,
                "title": title,
                "file_path": file_path,
            },
        )

        # Persist to Supabase / SQLite
        await supabase.insert_asset({
            "id": asset_id,
            "owner_id": owner_id,
            "title": title or file.filename,
            "file_path": file_path,
            "clip_vec": clip_vec,
            "hog_vec": hog_vec,
            "color_vec": color_vec,
            "phash": phashes.phash,
            "dhash": phashes.dhash,
            "ahash": phashes.ahash,
            "watermarked": False,
        })

        logger.info("Asset ingested: %s (%s) → idx=%d", asset_id, file.filename, idx)

        return UploadResponse(
            asset_id=asset_id,
            owner_id=owner_id,
            filename=file.filename,
            status="success",
            fingerprints={
                "clip_dim": int(clip_vec.shape[0]),
                "phash": phashes.phash,
                "dhash": phashes.dhash,
                "ahash": phashes.ahash,
                "hog_dim": int(hog_vec.shape[0]),
                "color_dim": int(color_vec.shape[0]),
            },
            timestamp=ts,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Upload pipeline failed")
        try:
            os.remove(file_path)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")
