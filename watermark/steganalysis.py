import numpy as np
from scipy.stats import chisquare
from PIL import Image

def run_steganalysis(image: Image.Image) -> dict:
    """
    Tests if image contains detectable steganography.
    RS-analysis or chi-square test on LSB.
    """
    img_gray = np.array(image.convert("L"))
    
    # Simple chi-square on pairs of values (PoV)
    # Count occurrences of 2i and 2i+1
    hist, _ = np.histogram(img_gray.flatten(), bins=256, range=(0, 256))
    
    expected = []
    observed = []
    
    for i in range(128):
        h2i = hist[2*i]
        h2i1 = hist[2*i + 1]
        avg = (h2i + h2i1) / 2.0
        if avg > 5:  # avoid low count bins for chi-square
            expected.append(avg)
            expected.append(avg)
            observed.append(h2i)
            observed.append(h2i1)
            
    if not expected:
        return {"detectable": False, "p_value": 1.0}
        
    chi_val, p_val = chisquare(f_obs=observed, f_exp=expected)
    
    # If p-value < 0.05, it means the distribution deviates from expected normal pairing,
    # suggesting LSB matching was used. Our DCT/DWT shouldn't affect LSB directly like this,
    # so we expect it to NOT be statistically detectable here.
    return {
        "detectable": p_val < 0.05,
        "p_value": float(p_val)
    }
