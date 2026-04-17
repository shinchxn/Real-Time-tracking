"""
Invisible DCT Watermark — Embedding

Payload: asset_id (64-bit) + owner_id (32-bit) + CRC-16 checksum (16-bit) = 112 bits
Embeds into mid-band DCT coefficients of the Y channel (YCbCr).
Spread-spectrum modulation via PN sequence seeded from owner_id.
"""
import logging
import struct
import zlib
from typing import Tuple

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_BLOCK = 8
_MID_BAND_INDICES = [(2, 1), (1, 2), (3, 0)]  # 3 coefficients per block
_PAYLOAD_BITS = 112  # 64 + 32 + 16


def _uuid_to_int64(uuid_str: str) -> int:
    """Convert a UUID hex string to a 64-bit integer (truncated hash)."""
    import hashlib
    h = hashlib.sha256(uuid_str.encode()).digest()
    return struct.unpack(">Q", h[:8])[0]


def _build_payload(asset_id: str, owner_id: str) -> np.ndarray:
    """
    Build a 112-bit payload array:
        [0:64]   → asset_id hash
        [64:96]  → owner_id hash
        [96:112] → CRC-16 checksum of the first 96 bits
    """
    a_int = _uuid_to_int64(asset_id)
    o_hash = struct.unpack(">I", struct.pack(">Q", _uuid_to_int64(owner_id))[:4])[0]

    bits = []
    for i in range(64):
        bits.append((a_int >> (63 - i)) & 1)
    for i in range(32):
        bits.append((o_hash >> (31 - i)) & 1)

    # CRC-16 over the 96-bit payload (pack into 12 bytes)
    payload_bytes = bytearray()
    for i in range(0, 96, 8):
        byte_val = 0
        for b in range(8):
            byte_val = (byte_val << 1) | bits[i + b]
        payload_bytes.append(byte_val)

    crc = zlib.crc32(bytes(payload_bytes)) & 0xFFFF
    for i in range(16):
        bits.append((crc >> (15 - i)) & 1)

    return np.array(bits, dtype=np.int8)


def _pn_sequence(seed: int, length: int) -> np.ndarray:
    """Generate a pseudo-random ±1 sequence seeded from owner_id."""
    rng = np.random.RandomState(seed & 0x7FFFFFFF)
    return rng.choice([-1, 1], size=length).astype(np.float64)


def embed_watermark(
    image: Image.Image,
    asset_id: str,
    owner_id: str,
    alpha: float = 0.08,
) -> Image.Image:
    """
    Embed an invisible DCT watermark into the image.

    Args:
        image:    PIL RGB Image.
        asset_id: UUID string identifying the asset.
        owner_id: UUID string identifying the owner.
        alpha:    Embedding strength (default 0.08 — imperceptible).

    Returns:
        PIL RGB Image with embedded watermark.
    """
    img_rgb = np.array(image.convert("RGB"))
    img_ycrcb = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2YCrCb).astype(np.float64)

    y_channel = img_ycrcb[:, :, 0]
    h, w = y_channel.shape

    # Crop to multiples of block size
    bh, bw = (h // _BLOCK) * _BLOCK, (w // _BLOCK) * _BLOCK
    y_crop = y_channel[:bh, :bw].copy()

    payload = _build_payload(asset_id, owner_id)
    pn_seed = _uuid_to_int64(owner_id) & 0x7FFFFFFF
    pn = _pn_sequence(pn_seed, _PAYLOAD_BITS)

    # Spread-spectrum payload: payload XOR mapped to ±1
    spread = np.where(payload == 1, 1.0, -1.0) * pn  # element-wise

    bit_idx = 0
    num_blocks = (bh // _BLOCK) * (bw // _BLOCK)
    blocks_per_bit = max(1, num_blocks // _PAYLOAD_BITS)

    for bit_pos in range(_PAYLOAD_BITS):
        val = spread[bit_pos] * alpha
        for blk in range(blocks_per_bit):
            global_blk = bit_pos * blocks_per_bit + blk
            row = (global_blk // (bw // _BLOCK)) * _BLOCK
            col = (global_blk % (bw // _BLOCK)) * _BLOCK
            if row + _BLOCK > bh or col + _BLOCK > bw:
                break

            block = y_crop[row:row + _BLOCK, col:col + _BLOCK]
            dct_block = cv2.dct(block)

            for ri, ci in _MID_BAND_INDICES:
                dct_block[ri, ci] += val

            y_crop[row:row + _BLOCK, col:col + _BLOCK] = cv2.idct(dct_block)

    # Write back
    img_ycrcb[:bh, :bw, 0] = np.clip(y_crop, 0, 255)
    result = cv2.cvtColor(img_ycrcb.astype(np.uint8), cv2.COLOR_YCrCb2RGB)
    logger.info("Watermark embedded for asset=%s owner=%s", asset_id, owner_id)
    return Image.fromarray(result)
