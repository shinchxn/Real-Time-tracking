"""
Layer 4 — Edge Gradient Fingerprint (HOG descriptor)
Resize → Canny → 128-bin HOG descriptor.
Survives color grading and watermark overlays.
"""
import logging
from typing import Union

import cv2
import numpy as np
from PIL import Image
from skimage.feature import hog as sk_hog

logger = logging.getLogger(__name__)

_HOG_SIZE = 256
_HOG_ORIENTATIONS = 8
_HOG_PIXELS_PER_CELL = (16, 16)
_HOG_CELLS_PER_BLOCK = (2, 2)


async def extract_hog_descriptor(image: Union[Image.Image, np.ndarray]) -> np.ndarray:
    """
    Extract a 128-bin HOG descriptor from the image.

    Steps:
        1. Resize to 256×256.
        2. Convert to grayscale.
        3. Apply Canny edge detection.
        4. Compute HOG descriptor (128 bins).

    Returns:
        np.ndarray of shape (128,), dtype float32.
    """
    if isinstance(image, Image.Image):
        image = np.array(image.convert("RGB"))

    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    resized = cv2.resize(gray, (_HOG_SIZE, _HOG_SIZE), interpolation=cv2.INTER_AREA)

    # Canny edge map
    edges = cv2.Canny(resized, 50, 150)

    # HOG on the edge map
    descriptor = sk_hog(
        edges,
        orientations=_HOG_ORIENTATIONS,
        pixels_per_cell=_HOG_PIXELS_PER_CELL,
        cells_per_block=_HOG_CELLS_PER_BLOCK,
        block_norm="L2-Hys",
        feature_vector=True,
    )

    vec = np.array(descriptor, dtype=np.float32)

    # Ensure exactly 128 dims — truncate or pad
    if vec.shape[0] > 128:
        vec = vec[:128]
    elif vec.shape[0] < 128:
        vec = np.pad(vec, (0, 128 - vec.shape[0]))

    logger.debug("HOG descriptor shape: %s", vec.shape)
    return vec
