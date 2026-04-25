"""
LSB Steganographic Fingerprint — Content DNA Apex v7.0
Embeds a 256-bit fingerprint into the least significant bit (LSB) 
of pseudo-randomly selected pixels in the blue channel.
"""
import numpy as np
from typing import Optional

def embed_lsb_fingerprint(img_array: np.ndarray, fingerprint_bits: str, asset_id: str) -> np.ndarray:
    """
    Embeds bits into the LSB of 256 pseudo-random pixels in the blue channel.
    fingerprint_bits: binary string of length 256.
    """
    if len(fingerprint_bits) != 256:
        raise ValueError("Fingerprint must be 256 bits")
        
    out = img_array.copy()
    h, w, c = out.shape
    if c < 3: # Need RGB
        return out
        
    # Seed RNG with asset_id prefix
    seed = int(asset_id[:8], 16)
    rng = np.random.default_rng(seed)
    
    # Generate 256 unique positions
    total_pixels = h * w
    indices = rng.choice(total_pixels, size=256, replace=False)
    
    for i, idx in enumerate(indices):
        y = idx // w
        x = idx % w
        
        bit = int(fingerprint_bits[i])
        
        # Clear LSB of blue channel (channel 2)
        out[y, x, 2] = (out[y, x, 2] & 0xFE) | bit
        
    return out

def extract_lsb_fingerprint(img_array: np.ndarray, asset_id: str) -> Optional[str]:
    """
    Extracts 256 bits from pseudo-random positions.
    Returns binary string.
    """
    h, w, c = img_array.shape
    if c < 3:
        return None
        
    seed = int(asset_id[:8], 16)
    rng = np.random.default_rng(seed)
    
    total_pixels = h * w
    indices = rng.choice(total_pixels, size=256, replace=False)
    
    bits = ""
    for idx in indices:
        y = idx // w
        x = idx % w
        
        bit = img_array[y, x, 2] & 1
        bits += str(bit)
        
    return bits
