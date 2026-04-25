import numpy as np
import pywt
import cv2
from PIL import Image
import struct

def embed_dwt_watermark(image: Image.Image, asset_id: int, owner_id: int, timestamp: int) -> Image.Image:
    """
    2-level Haar wavelet decomposition.
    Embed redundant payload in LL2 sub-band.
    """
    img_arr = np.array(image.convert("RGB"))
    ycbcr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2YCrCb)
    Y = np.float32(ycbcr[:, :, 0])
    
    # 2-level 2D DWT
    coeffs2 = pywt.wavedec2(Y, 'haar', level=2)
    LL2, (LH2, HL2, HH2), (LH1, HL1, HH1) = coeffs2
    
    checksum = (asset_id ^ owner_id ^ timestamp) & 0xFFFF
    payload_fmt = f">Q I I H"
    packed = struct.pack(payload_fmt,
                         asset_id & 0xFFFFFFFFFFFFFFFF,
                         owner_id & 0xFFFFFFFF,
                         timestamp & 0xFFFFFFFF,
                         checksum)
    bits = np.unpackbits(np.frombuffer(packed, dtype=np.uint8))
    
    # Redundant embedding in LL2
    alpha = 5.0 # Embed strength for LL
    h, w = LL2.shape
    idx = 0
    total_bits = len(bits)
    
    # Spread repeatedly
    for i in range(h):
        for j in range(w):
            val = 1 if bits[idx % total_bits] == 1 else -1
            LL2[i, j] += alpha * val
            idx += 1
            
    coeffs2[0] = LL2
    Y_watermarked = pywt.waverec2(coeffs2, 'haar')
    Y_watermarked = np.clip(Y_watermarked, 0, 255)
    
    ycbcr[:, :, 0] = Y_watermarked.astype(np.uint8)
    out_rgb = cv2.cvtColor(ycbcr, cv2.COLOR_YCrCb2RGB)
    
    # resize if wavrec2 output shape mismatch by 1 px due to padding (odd sizes)
    if out_rgb.shape[:2] != img_arr.shape[:2]:
        out_rgb = cv2.resize(out_rgb, (img_arr.shape[1], img_arr.shape[0]))
        
    return Image.fromarray(out_rgb)
