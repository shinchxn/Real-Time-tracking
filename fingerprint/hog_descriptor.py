import numpy as np
from skimage.feature import hog
from skimage.color import rgb2gray
from PIL import Image

def extract_hog_descriptor(image: Image.Image) -> np.ndarray:
    """
    Resize to 256x256, Canny edge? No, standard HOG descriptor.
    128-dim float32.
    """
    # Resize -> 256x256
    img_resized = image.resize((256, 256), Image.Resampling.LANCZOS)
    img_array = np.array(img_resized)
    
    if len(img_array.shape) == 3:
        img_gray = rgb2gray(img_array)
    else:
        img_gray = img_array

    # 128 bins -> Using parameters to yield precisely 128 features.
    # pixels_per_cell=(64,64) => 4x4 cells=16
    # cells_per_block=(2,2) => 3x3 blocks = 9
    # orientations=8 => 9 * (2x2) * 8 = 288
    # Let's adjust to yield exactly 128 (e.g. 16 blocks * 8 orientations = 128)
    # Using block_norm='L2-Hys'
    # Actually, let's take a larger descriptor and PCA or just slice the top 128 deterministic values.
    # Setting orientations=8, pixels_per_cell=(64,64), cells_per_block=(1,1)
    # Total cells: (256/64)=4, 4x4=16 cells. 16 * 1 * 8 = 128 features!
    fd = hog(img_gray, orientations=8, pixels_per_cell=(64, 64),
             cells_per_block=(1, 1), block_norm='L2-Hys', visualize=False)
             
    fd = fd.astype(np.float32)
    
    # L2 normalize
    norm = np.linalg.norm(fd)
    if norm > 0:
        fd = fd / norm
        
    return fd
