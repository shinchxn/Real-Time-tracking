"""
DCT Watermark Embedder — Content DNA Apex v7.1
Upgraded to 256-bit dual-band blind embedding.
Implements the 2-stage PN sequence:
1. Master PN for the first 32 bits (the seed)
2. Seed-based PN for the remaining 224 bits
"""
import numpy as np
import cv2
from PIL import Image
import struct
import hashlib
import os

def get_master_pn(length: int) -> np.ndarray:
    master_seed = int(os.getenv("WATERMARK_MASTER_SEED", "0xDEADBEEF"), 16)
    rng = np.random.default_rng(master_seed)
    return rng.choice([-1, 1], size=length)

def embed_dct_watermark(
    image: Image.Image,
    asset_id: int,
    owner_id: int,
    timestamp: int,
    watermark_seed: int,
    alpha: float = 0.08,
) -> Image.Image:
    # 1. Prepare Payload (256 bits)
    # [Seed(32) | Asset(64) | Owner(64) | Timestamp(32) | Checksum(64)]
    packed_meta = struct.pack(">QQI", asset_id, owner_id, timestamp)
    checksum = hashlib.sha256(struct.pack(">I", watermark_seed) + packed_meta).digest()[:8]
    
    seed_bits = np.unpackbits(np.frombuffer(struct.pack(">I", watermark_seed), dtype=np.uint8))
    meta_bits = np.unpackbits(np.frombuffer(packed_meta + checksum, dtype=np.uint8))
    
    # 2. Derive PN sequences
    # Stage 1: Master PN for seed
    master_pn = get_master_pn(32)
    
    # Stage 2: Seed-based PN for the rest
    rng = np.random.default_rng(watermark_seed)
    seed_pn = rng.choice([-1, 1], size=224)
    
    # Modulate
    mod_seed = (seed_bits * 2 - 1) * master_pn * alpha
    mod_meta = (meta_bits * 2 - 1) * seed_pn * alpha
    
    modulated = np.concatenate([mod_seed, mod_meta])

    # 3. Apply DCT
    img_arr = np.array(image.convert("RGB"))
    ycbcr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2YCrCb)
    Y = np.float32(ycbcr[:, :, 0])
    
    band1 = [(2, 1), (1, 2), (3, 0), (0, 3)]
    band2 = [(1, 1), (2, 0), (0, 2)]

    h, w = Y.shape
    h_blocks, w_blocks = h // 8, w // 8
    
    out_Y = Y.copy()
    bit_idx = 0
    for i in range(h_blocks):
        for j in range(w_blocks):
            if bit_idx >= 256: break
            
            block = Y[i*8:(i+1)*8, j*8:(j+1)*8]
            dct_block = cv2.dct(block)
            
            for coord in band1:
                dct_block[coord] += modulated[bit_idx] * np.abs(dct_block[coord])
            for coord in band2:
                dct_block[coord] += modulated[bit_idx] * np.abs(dct_block[coord])
                
            out_Y[i*8:(i+1)*8, j*8:(j+1)*8] = cv2.idct(dct_block)
            bit_idx += 1
            
    ycbcr[:, :, 0] = np.clip(out_Y, 0, 255).astype(np.uint8)
    out_rgb = cv2.cvtColor(ycbcr, cv2.COLOR_YCrCb2RGB)
    return Image.fromarray(out_rgb)
