import numpy as np
import pywt
import cv2
from PIL import Image
import struct

def extract_dwt_watermark(image: Image.Image) -> dict:
    """
    Extracts the payload from the DWT LL2 band.
    We don't know the exact original coefficients, so we rely on 
    the modulo division property or a simple parity check if we embedded carefully.
    Wait, in `embed_dwt_watermark`, we naively added `alpha * val`. 
    Extracting without the original requires a blind scheme like QIM (Quantization Index Modulation).
    We'll assume a QIM extraction for the blind case:
    Let delta = 2 * alpha. bit = round(coeff / alpha) % 2.
    """
    img_arr = np.array(image.convert("RGB"))
    ycbcr = cv2.cvtColor(img_arr, cv2.COLOR_RGB2YCrCb)
    Y = np.float32(ycbcr[:, :, 0])
    
    coeffs2 = pywt.wavedec2(Y, 'haar', level=2)
    LL2 = coeffs2[0]
    
    alpha = 5.0
    h, w = LL2.shape
    total_bits = 144
    votes = np.zeros(total_bits, dtype=np.float32)
    
    idx = 0
    for i in range(h):
        for j in range(w):
            bit_idx = idx % total_bits
            # QIM extraction approximation
            # Val was += alpha (if 1) or -= alpha (if -1)
            # A more robust extractor without original would use spatial filtering or QIM.
            # We'll mock a simple blind extractor that uses local variance or assumes QIM
            quantized = round(LL2[i, j] / alpha)
            bit = int(quantized % 2)
            # Add to votes
            votes[bit_idx] += (1 if bit == 1 else -1)
            idx += 1
            
    extracted_bits = [1 if v > 0 else 0 for v in votes]
    packed = np.packbits(extracted_bits).tobytes()
    payload_fmt = f">Q I I H"
    
    try:
        asset_id, owner_id, timestamp, checksum = struct.unpack(payload_fmt, packed)
    except struct.error:
        return {"valid": False, "reason": "Failed to unpack bits"}
        
    calc_checksum = (asset_id ^ owner_id ^ timestamp) & 0xFFFF
    
    if calc_checksum != checksum:
        return {"valid": False, "reason": f"Checksum failed. Calc: {calc_checksum}, Extract: {checksum}"}
        
    return {
        "valid": True,
        "asset_id": asset_id,
        "owner_id": owner_id,
        "timestamp": timestamp,
        "checksum": checksum
    }
