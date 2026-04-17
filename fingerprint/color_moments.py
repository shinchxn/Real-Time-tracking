"""
Layer 3 — Color Moment Descriptor
Extract mean, std, skewness per HSV channel → float32[9] vector.
Robust against geometric transforms; catches near-duplicates.
"""
import logging
from typing import Union

import cv2
import numpy as np
from PIL import Image
from scipy import stats as sp_stats

logger = logging.getLogger(__name__)


async def extract_color_moments(image: Union[Image.Image, np.ndarray]) -> np.ndarray:
    """
    Compute color moment descriptor for the given image.

    Steps:
        1. Convert to HSV.
        2. For each channel compute mean, std, skewness.
        3. Concatenate into a float32[9] vector.

    Returns:
        np.ndarray of shape (9,), dtype float32.
    """
    if isinstance(image, Image.Image):
        image = np.array(image.convert("RGB"))

    # BGR ← RGB  (cv2 convention)
    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float64)

    moments = []
    for ch in range(3):
        channel = hsv[:, :, ch].flatten()
        mean = np.mean(channel)
        std = np.std(channel) + 1e-8
        skew = float(sp_stats.skew(channel))
        moments.extend([mean, std, skew])

    vec = np.array(moments, dtype=np.float32)
    logger.debug("Color moments: %s", vec)
    return vec
