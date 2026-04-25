import numpy as np
from config import settings

def calculate_fusion_score(
    clip_dist: float,      # cosine distance or similarity (assuming we work with inner product / similarity)
    spatial_dist: float,
    dct_dist: float,
    phash_dist: float,     # hamming distance
    hog_dist: float,
    color_dist: float
) -> float:
    """
    Apex fusion formula. We assume inputs are similarity scores (0.0 to 1.0),
    except phash_dist which is absolute Hamming distance.
    """
    # Normalize phash: max usually 64, phash_norm = 1 - (phash_dist / 64)
    # The prompt formula: 0.20 * (1 - hamming_norm(phash)) -> assuming hamming_norm = dist / 64
    phash_sim = 1.0 - (phash_dist / 64.0)

    score = (
        settings.WEIGHT_CLIP * clip_dist +
        settings.WEIGHT_PHASH * phash_sim +
        settings.WEIGHT_HOG * hog_dist +
        settings.WEIGHT_COLOR * color_dist +
        settings.WEIGHT_DCT_FREQ * dct_dist +
        settings.WEIGHT_SPATIAL * spatial_dist
    )
    
    return float(score)

def classify_severity(score: float) -> str:
    if score >= settings.THRESHOLD_CRITICAL:
        return "CRITICAL"
    elif score >= settings.THRESHOLD_HIGH:
        return "HIGH"
    elif score >= settings.THRESHOLD_MEDIUM:
        return "MEDIUM"
    elif score >= settings.THRESHOLD_WATCH:
        return "WATCH"
    else:
        return "NONE"
