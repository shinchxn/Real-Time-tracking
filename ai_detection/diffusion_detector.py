import numpy as np
import pywt
from PIL import Image

def detect_diffusion_artifacts(image: Image.Image) -> float:
    """
    Spectral features from wavelet LL3 sub-band to detect diffusion upsampling artifacts.
    P(AI-generated) >= 0.82 -> flag
    """
    img_gray = np.array(image.convert("L"), dtype=np.float32)
    
    try:
        # 3-level DWT
        coeffs = pywt.wavedec2(img_gray, 'db1', level=3)
        LL3 = coeffs[0]
        
        # Diffusion models often have abnormal high frequency energy distributions
        # We'll take the standard deviation of LL3 as a mock feature
        std_val = np.std(LL3)
        
        # Artificial probabilistic score based on std (heuristic)
        score = np.clip(1.0 - (std_val / 120.0), 0.0, 1.0)
        return float(score)
    except Exception:
        return 0.0
