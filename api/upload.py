"""Upload & Registration — Content DNA Apex"""
import base64, hashlib, io, logging, os, traceback, uuid
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, Request, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image
import numpy as np

from detection.detector import extract_all_fingerprints
from watermark.dct_embed import embed_dct_watermark
from watermark.dwt_embed import embed_dwt_watermark
from crypto.lsb_fingerprint import embed_lsb_fingerprint

logger = logging.getLogger(__name__)
router = APIRouter()
_WM_SEED = int(os.getenv("WATERMARK_MASTER_SEED", str(0xDEADBEEF)), 16)


@router.post("/upload")
async def upload_asset(request: Request, file: UploadFile = File(...)):
    """
    Full pipeline:
    1. Extract 6-layer forensic DNA
    2. Register in FAISS index
    3. Embed DCT watermark (frequency domain)
    4. Embed DWT watermark (wavelet domain)
    5. Embed LSB steganographic fingerprint (blue channel)
    6. Embed XMP metadata
    7. Queue blockchain anchor (Celery)
    8. Return DNA report + watermarked PNG
    """
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        logger.info("Registering: %s", file.filename)

        # 1. 6-layer DNA
        dna_pkg = await extract_all_fingerprints(image)
        clip_vec, phashes, hog_vec, color_vec, dct_vec, spatial_vec = (
            dna_pkg["global"]
        )

        # 2. FAISS registration
        asset_id = str(uuid.uuid4())
        faiss_index = request.app.state.faiss_index
        faiss_idx = faiss_index.add(
            asset_id=asset_id,
            clip_vec=clip_vec, hog_vec=hog_vec, color_vec=color_vec,
            dct_vec=dct_vec, spatial_vec=spatial_vec,
            phash=str(phashes.phash),
            metadata={
                "filename": file.filename,
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "phash": str(phashes.phash),
                "dhash": str(phashes.dhash),
            }
        )

        # DNA hash (for blockchain + DMCA)
        dna_hash = hashlib.sha256(
            clip_vec.tobytes() + hog_vec.tobytes()
        ).hexdigest()

        # 3-5. Triple watermarking
        asset_id_int = int(uuid.UUID(asset_id).int >> 64)
        owner_id_int = 0xDEAD
        ts = int(datetime.now().timestamp())

        # Layer A: DCT (frequency domain — survives JPEG Q>=40)
        wm = embed_dct_watermark(
            image, asset_id=asset_id_int, owner_id=owner_id_int,
            timestamp=ts, watermark_seed=_WM_SEED,
        )
        # Layer B: DWT (wavelet — survives social media pipelines)
        wm = embed_dwt_watermark(wm, asset_id_int, owner_id_int, ts)
        # Layer C: LSB (blue channel — fast extraction path)
        fp_bits = bin(asset_id_int)[2:].zfill(256)[:256]
        arr = np.array(wm)
        arr = embed_lsb_fingerprint(arr, fp_bits, asset_id[:8])
        wm = Image.fromarray(arr)

        # 6. XMP metadata (non-fatal)
        try:
            from crypto.xmp_embedder import embed_xmp_metadata
            tmp = io.BytesIO()
            wm.save(tmp, format="PNG")
            xmp = embed_xmp_metadata(tmp.getvalue(), {
                "asset_id": asset_id, "org_id": "demo",
                "signature": dna_hash[:32],
                "signed_at": datetime.now(timezone.utc).isoformat(),
            })
            wm = Image.open(io.BytesIO(xmp))
        except Exception as e:
            logger.warning("XMP embed skipped: %s", e)

        # Encode result
        buf = io.BytesIO()
        wm.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        # 7. Async blockchain anchor
        blockchain_tx = "pending"
        try:
            from tasks.fingerprint_tasks import anchor_to_blockchain
            t = anchor_to_blockchain.apply_async(
                args=[asset_id, dna_hash, ""], queue="blockchain"
            )
            blockchain_tx = f"queued:{t.id}"
        except Exception as e:
            logger.warning("Blockchain queue skipped: %s", e)

        # Register in viral spread graph
        try:
            request.app.state.spread_graph.add_asset(asset_id, dna_hash)
        except Exception:
            pass

        return JSONResponse({
            "status": "registered",
            "asset_id": asset_id,
            "dna_hash": dna_hash,
            "faiss_id": int(faiss_idx),
            "filename": file.filename,
            "watermark_layers": ["DCT", "DWT", "LSB", "XMP"],
            "blockchain_tx": blockchain_tx,
            "fingerprints": {
                "clip_dim": len(clip_vec),
                "phash": str(phashes.phash),
                "dhash": str(phashes.dhash),
                "ahash": str(phashes.ahash),
            },
            "watermarked_image": f"data:image/png;base64,{img_b64}",
        })
    except Exception as e:
        logger.error("Registration failed: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
