"""
DCT Watermark Extractor — Content DNA Apex v7.1
FIX 28: Signature changed to accept bytes and return dict (not WatermarkResult).
This matches how it is called in:
  - background_tasks.py: wm_result = extract_watermark(media_bytes)
  - crypto/asset_verifier.py: wm = extract_watermark(media_bytes)
  - both expect: dict with keys asset_id, org_name, registered_at — or empty dict {}

Implements blind 2-stage extraction:
1. Recover seed using Master PN.
2. Recover metadata using Seed-based PN.
"""
import io
import numpy as np
import cv2
import struct
import hashlib
import logging
from PIL import Image
from typing import Optional, Dict

from watermark.dct_embed import get_master_pn

logger = logging.getLogger(__name__)


def extract_watermark(media_bytes: bytes) -> Dict:
    """
    Extract DCT watermark from raw image bytes.

    Args:
        media_bytes: Raw image file bytes (JPEG, PNG, WebP, etc.)

    Returns:
        dict with keys: asset_id, org_id, signed_at, confidence
        OR empty dict {} if no valid watermark found.
    """
    try:
        img = Image.open(io.BytesIO(media_bytes)).convert("RGB")
    except Exception as e:
        logger.debug("[dct_extract] Could not open image: %s", e)
        return {}

    try:
        img_arr = np.array(img)
        ycbcr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2YCrCb)
        Y = np.float32(ycbcr[:, :, 0])

        h, w = Y.shape
        h_blocks, w_blocks = h // 8, w // 8

        band1 = [(2, 1), (1, 2), (3, 0), (0, 3)]
        band2 = [(1, 1), (2, 0), (0, 2)]

        # Extract raw coefficients from DCT blocks
        corrs = []
        for i in range(h_blocks):
            for j in range(w_blocks):
                if len(corrs) >= 256:
                    break
                block = Y[i * 8:(i + 1) * 8, j * 8:(j + 1) * 8]
                dct_block = cv2.dct(block)
                val1 = sum(dct_block[c] for c in band1)
                val2 = sum(dct_block[c] for c in band2)
                corrs.append((val1 + val2) / 2.0)
            if len(corrs) >= 256:
                break

        if len(corrs) < 256:
            return {}

        corrs = np.array(corrs)

        # Stage 1: Recover watermark seed using Master PN
        master_pn = get_master_pn(32)
        seed_corrs = corrs[:32] * master_pn
        seed_bits = (seed_corrs > 0).astype(np.uint8)
        seed_bytes = np.packbits(seed_bits).tobytes()
        watermark_seed = struct.unpack(">I", seed_bytes)[0]

        # Stage 2: Recover metadata using seed-derived PN
        rng = np.random.default_rng(watermark_seed)
        seed_pn = rng.choice([-1, 1], size=224)
        meta_corrs = corrs[32:] * seed_pn
        meta_bits = (meta_corrs > 0).astype(np.uint8)
        meta_bytes = np.packbits(meta_bits).tobytes()

        # Unpack: Asset UUID int (8 bytes) + Owner UUID int (8 bytes) + timestamp (4 bytes) + checksum (8 bytes)
        asset_id_int, owner_id_int, timestamp = struct.unpack(">QQI", meta_bytes[:20])
        checksum_extracted = meta_bytes[20:28]

        # Validate checksum
        packed_meta = struct.pack(">QQI", asset_id_int, owner_id_int, timestamp)
        checksum_expected = hashlib.sha256(
            struct.pack(">I", watermark_seed) + packed_meta
        ).digest()[:8]

        if checksum_extracted != checksum_expected:
            logger.debug("[dct_extract] Checksum mismatch — no valid watermark")
            return {}

        import uuid as uuid_lib
        asset_id = str(uuid_lib.UUID(int=asset_id_int))
        org_id = str(uuid_lib.UUID(int=owner_id_int))
        confidence = float(np.mean(np.abs(corrs)))

        return {
            "asset_id": asset_id,
            "org_id": org_id,
            "org_name": "",        # Populated from DB if needed
            "registered_at": "",   # Populated from DB if needed
            "signed_at": timestamp,
            "confidence": confidence,
        }

    except Exception as e:
        logger.debug("[dct_extract] Extraction error: %s", e)
        return {}
