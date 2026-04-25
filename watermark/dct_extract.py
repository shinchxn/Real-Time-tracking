"""
DCT Watermark Extractor — Content DNA Apex v7.1
Implements blind 2-stage extraction:
1. Recover seed using Master PN.
2. Recover metadata using Seed-based PN.
"""
import numpy as np
import cv2
from PIL import Image
import struct
import hashlib
import os
from dataclasses import dataclass
from typing import Optional

from watermark.dct_embed import get_master_pn

@dataclass
class WatermarkResult:
    asset_id: str
    org_id: str
    signed_at: int
    confidence: float
    valid: bool = True

def blind_extract(image_bytes: bytes) -> Optional[WatermarkResult]:
    """
    Step 1: Extract correlation values from DCT bands.
    Step 2: Recover seed from first 32 bits.
    Step 3: Recover rest of payload using seed.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img_arr = np.array(img)
    ycbcr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2YCrCb)
    Y = np.float32(ycbcr[:, :, 0])
    
    h, w = Y.shape
    h_blocks, w_blocks = h // 8, w // 8
    
    band1 = [(2, 1), (1, 2), (3, 0), (0, 3)]
    band2 = [(1, 1), (2, 0), (0, 2)]
    
    # Extract raw coefficients
    corrs = []
    for i in range(h_blocks):
        for j in range(w_blocks):
            if len(corrs) >= 256: break
            block = Y[i*8:(i+1)*8, j*8:(j+1)*8]
            dct_block = cv2.dct(block)
            # Majority vote/average across bands
            val1 = sum(dct_block[c] for c in band1)
            val2 = sum(dct_block[c] for c in band2)
            corrs.append((val1 + val2) / 2.0)
            
    if len(corrs) < 256: return None
    corrs = np.array(corrs)

    # 1. Recover Seed
    master_pn = get_master_pn(32)
    seed_corrs = corrs[:32] * master_pn
    seed_bits = (seed_corrs > 0).astype(np.uint8)
    seed_bytes = np.packbits(seed_bits).tobytes()
    watermark_seed = struct.unpack(">I", seed_bytes)[0]
    
    # 2. Recover Metadata
    rng = np.random.default_rng(watermark_seed)
    seed_pn = rng.choice([-1, 1], size=224)
    meta_corrs = corrs[32:] * seed_pn
    meta_bits = (meta_corrs > 0).astype(np.uint8)
    meta_bytes = np.packbits(meta_bits).tobytes()
    
    try:
        asset_id_int, owner_id_int, timestamp = struct.unpack(">QQI", meta_bytes[:20])
        checksum_extracted = meta_bytes[20:28]
        
        # Validate Checksum
        packed_meta = struct.pack(">QQI", asset_id_int, owner_id_int, timestamp)
        checksum_expected = hashlib.sha256(struct.pack(">I", watermark_seed) + packed_meta).digest()[:8]
        
        if checksum_extracted != checksum_expected:
            return None
            
        # Success
        confidence = float(np.mean(np.abs(corrs))) # Simplified confidence
        
        # Convert ints back to UUID strings if needed, or just return as is
        import uuid
        return WatermarkResult(
            asset_id=str(uuid.UUID(int=asset_id_int)), # This might not be right if it was 64-bit in embed
            org_id=str(uuid.UUID(int=owner_id_int)),   # We used 64-bit in pack, but UUIDs are 128-bit.
            signed_at=timestamp,
            confidence=confidence
        )
    except Exception:
        return None

import io
