import numpy as np
import scipy.fftpack
from PIL import Image

def extract_dct_frequency_signature(image: Image.Image) -> np.ndarray:
    """
    Extract 512-dim float32 DCT frequency signature.
    32x32 DCT coefficient block, low+mid frequencies.
    """
    img_gray = image.convert('L')
    img_resized = img_gray.resize((32, 32), Image.Resampling.LANCZOS)
    img_array = np.array(img_resized, dtype=np.float32)
    
    # 2D DCT
    dct_2d = scipy.fftpack.dct(
        scipy.fftpack.dct(img_array.T, norm='ortho').T, 
        norm='ortho'
    )
    
    # Extract zigzag or just low-frequency block 
    # To get exactly 512 dims, let's take upper-left triangle or similar.
    # A simple deterministic approach: take alternating mid frequencies.
    # We will flatten and take the first 512 coefficients.
    flattened = dct_2d.flatten()
    
    # Zero high-freq
    # The higher indices correlate to higher frequencies
    # Since 32x32 = 1024, we take the top 512 structurally.
    
    sig = flattened[:512].astype(np.float32)
    
    # L2 normalize
    norm = np.linalg.norm(sig)
    if norm > 0:
        sig = sig / norm
    
    return sig
