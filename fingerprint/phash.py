"""
Layer 2 — Perceptual Hashing (pHash + dHash + aHash)
Uses the `imagehash` library; stores each hash as a hex string.
"""
import logging
from dataclasses import dataclass
from typing import Union

import imagehash
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class PerceptualHashes:
    """Container for all three perceptual hashes."""
    phash: str  # 64-bit perceptual hash (hex)
    dhash: str  # 64-bit difference hash (hex)
    ahash: str  # 64-bit average hash (hex)


import asyncio

async def extract_phashes(image: Union[Image.Image, np.ndarray]) -> PerceptualHashes:
    def _compute():
        img = image
        if isinstance(img, np.ndarray):
            img = Image.fromarray(img)

        if img.mode != "RGB":
            img = img.convert("RGB")

        phash = str(imagehash.phash(img, hash_size=8))
        dhash = str(imagehash.dhash(img, hash_size=8))
        ahash = str(imagehash.average_hash(img, hash_size=8))

        logger.debug("Hashes — pHash=%s  dHash=%s  aHash=%s", phash, dhash, ahash)
        return PerceptualHashes(phash=phash, dhash=dhash, ahash=ahash)
        
    return await asyncio.to_thread(_compute)


def hamming_distance(hex_a: str, hex_b: str) -> int:
    """Hamming distance between two hex-encoded hashes."""
    int_a = int(hex_a, 16)
    int_b = int(hex_b, 16)
    xor = int_a ^ int_b
    return bin(xor).count("1")


def hamming_normalised(hex_a: str, hex_b: str, bits: int = 64) -> float:
    """Normalised Hamming distance ∈ [0, 1]."""
    return hamming_distance(hex_a, hex_b) / bits
