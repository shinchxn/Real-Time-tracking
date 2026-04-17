"""
Invisible DCT Watermark — Extraction & Verification

Mirrors the embedding process: decomposes into 8×8 DCT blocks,
correlates mid-band coefficients with the PN sequence,
majority-votes each bit, and verifies the CRC-16 checksum.
"""
import logging
import struct
import zlib
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_BLOCK = 8
_MID_BAND_INDICES = [(2, 1), (1, 2), (3, 0)]
_PAYLOAD_BITS = 112  # 64 + 32 + 16


def _uuid_to_int64(uuid_str: str) -> int:
    import hashlib
    h = hashlib.sha256(uuid_str.encode()).digest()
    return struct.unpack(">Q", h[:8])[0]


def _pn_sequence(seed: int, length: int) -> np.ndarray:
    rng = np.random.RandomState(seed & 0x7FFFFFFF)
    return rng.choice([-1, 1], size=length).astype(np.float64)


@dataclass
class WatermarkResult:
    """Extracted watermark data."""
    asset_id_hash: int      # 64-bit integer
    owner_id_hash: int      # 32-bit integer
    checksum_valid: bool
    raw_bits: list


def extract_watermark(
    image: Image.Image,
    owner_id: str,
) -> Optional[WatermarkResult]:
    """
    Extract hidden watermark from an image.

    Args:
        image:    PIL Image (may be cropped / compressed / filtered).
        owner_id: Owner UUID used to generate the PN sequence.

    Returns:
        WatermarkResult or None if extraction fails / checksum mismatch.
    """
    img_rgb = np.array(image.convert("RGB"))
    img_ycrcb = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2YCrCb).astype(np.float64)
    y_channel = img_ycrcb[:, :, 0]
    h, w = y_channel.shape

    bh, bw = (h // _BLOCK) * _BLOCK, (w // _BLOCK) * _BLOCK
    y_crop = y_channel[:bh, :bw]

    pn_seed = _uuid_to_int64(owner_id) & 0x7FFFFFFF
    pn = _pn_sequence(pn_seed, _PAYLOAD_BITS)

    num_blocks = (bh // _BLOCK) * (bw // _BLOCK)
    blocks_per_bit = max(1, num_blocks // _PAYLOAD_BITS)

    extracted_bits = []

    for bit_pos in range(_PAYLOAD_BITS):
        votes = 0.0
        count = 0
        for blk in range(blocks_per_bit):
            global_blk = bit_pos * blocks_per_bit + blk
            row = (global_blk // (bw // _BLOCK)) * _BLOCK
            col = (global_blk % (bw // _BLOCK)) * _BLOCK
            if row + _BLOCK > bh or col + _BLOCK > bw:
                break

            block = y_crop[row:row + _BLOCK, col:col + _BLOCK]
            dct_block = cv2.dct(block)

            for ri, ci in _MID_BAND_INDICES:
                votes += dct_block[ri, ci] * pn[bit_pos]
                count += 1

        # Majority vote
        if count > 0:
            extracted_bits.append(1 if votes > 0 else 0)
        else:
            extracted_bits.append(0)

    # Reconstruct asset_id hash (64 bits)
    asset_int = 0
    for i in range(64):
        asset_int = (asset_int << 1) | extracted_bits[i]

    # Reconstruct owner_id hash (32 bits)
    owner_int = 0
    for i in range(64, 96):
        owner_int = (owner_int << 1) | extracted_bits[i]

    # Reconstruct CRC-16 (16 bits)
    crc_extracted = 0
    for i in range(96, 112):
        crc_extracted = (crc_extracted << 1) | extracted_bits[i]

    # Recompute CRC-16 from the first 96 bits
    payload_bytes = bytearray()
    for i in range(0, 96, 8):
        byte_val = 0
        for b in range(8):
            byte_val = (byte_val << 1) | extracted_bits[i + b]
        payload_bytes.append(byte_val)

    crc_check = zlib.crc32(bytes(payload_bytes)) & 0xFFFF
    checksum_valid = crc_extracted == crc_check

    if not checksum_valid:
        logger.warning("Watermark CRC mismatch: extracted=%04x computed=%04x",
                       crc_extracted, crc_check)
        return None

    logger.info("Watermark extracted: asset=%016x owner=%08x crc_ok=%s",
                asset_int, owner_int, checksum_valid)

    return WatermarkResult(
        asset_id_hash=asset_int,
        owner_id_hash=owner_int,
        checksum_valid=checksum_valid,
        raw_bits=extracted_bits,
    )
