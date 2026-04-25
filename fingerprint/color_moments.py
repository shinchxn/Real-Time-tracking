import numpy as np
from scipy.stats import skew
from PIL import Image

def extract_color_moments(image: Image.Image) -> np.ndarray:
    """
    9-dim float32. Mean, std, skewness per HSV channel.
    """
    img_hsv = image.convert('HSV')
    hsv_array = np.array(img_hsv, dtype=np.float32)
    
    H = hsv_array[:, :, 0].flatten()
    S = hsv_array[:, :, 1].flatten()
    V = hsv_array[:, :, 2].flatten()
    
    moments = []
    for channel in (H, S, V):
        moments.append(np.mean(channel))
        moments.append(np.std(channel))
        channel_skew = skew(channel)
        moments.append(channel_skew if not np.isnan(channel_skew) else 0.0)
        
    vec = np.array(moments, dtype=np.float32)
    
    # L2 normalize
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
        
    return vec
