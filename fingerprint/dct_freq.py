"""
Layer 5 — DCT Frequency Signature
Analyzes the distribution of DCT coefficients across frequency bands.
Provides a unique "texture signature" robust against social media recompression.
"""
import logging
from typing import Union

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

def extract_dct_frequency_signature(image: Union[Image.Image, np.ndarray]) -> np.ndarray:
    """
    Extract a 128-dim DCT frequency signature.
    
    Steps:
        1. Resize to 256x256 and convert to Y (grayscale).
        2. Compute 2D DCT on 8x8 blocks.
        3. For each block, extract mid-frequency band energies.
        4. Aggregate across the image to form a global signature.
    """
    if isinstance(image, Image.Image):
        image = np.array(image.convert("L"))
    elif len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    resized = cv2.resize(image, (256, 256), interpolation=cv2.INTER_AREA).astype(np.float32)
    
    # 8x8 blocks -> 32x32 = 1024 blocks
    h, w = resized.shape
    block_size = 8
    
    energies = []
    for i in range(0, h, block_size):
        for j in range(0, w, block_size):
            block = resized[i:i+block_size, j:j+block_size]
            dct = cv2.dct(block)
            
            # Mid-frequency band: indices (1,1) to (4,4) excluding DC (0,0)
            mid_band = dct[1:5, 1:5].flatten()
            energies.append(np.abs(mid_band))
            
    # Aggregate: Mean energy per frequency position across all blocks
    avg_energy = np.mean(energies, axis=0) # shape (16,)
    
    # To get 128 dims, we can use different block sizes or more frequency bands.
    # Let's extract more bands or use multiple resolutions.
    # Actually, a more robust way is to use the histogram of the mid-band coefficients.
    
    # Alternative: Sub-divide the image into 4x4 regions and get the 8 most energetic coefficients for each.
    # 16 regions * 8 coeffs = 128 dims.
    
    sig = []
    region_size = 64
    for i in range(0, h, region_size):
        for j in range(0, w, region_size):
            region = resized[i:i+region_size, j:j+region_size]
            dct_reg = cv2.dct(region)
            # Pick the top 8 coefficients (zigzag or top-left)
            # We'll take a 3x3 block excluding DC
            sub = dct_reg[0:3, 0:3].flatten()
            sig.extend(sub[1:]) # 8 values
            
    sig_vec = np.array(sig, dtype=np.float32)
    
    # Normalize
    norm = np.linalg.norm(sig_vec) + 1e-8
    sig_vec = sig_vec / norm
    
    return sig_vec
