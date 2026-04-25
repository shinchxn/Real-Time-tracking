import cv2
from PIL import Image
import numpy as np

def simulate_instagram(image: Image.Image) -> Image.Image:
    """resize->1080x1080 (keep aspect, pad), JPEG Q=78, chroma 4:2:0"""
    img = image.convert("RGB")
    # Resize keeping aspect ratio
    img.thumbnail((1080, 1080), Image.Resampling.LANCZOS)
    
    # Pad to 1080x1080
    padded = Image.new("RGB", (1080, 1080), (0, 0, 0))
    x_offset = (1080 - img.size[0]) // 2
    y_offset = (1080 - img.size[1]) // 2
    padded.paste(img, (x_offset, y_offset))
    
    # Save with Q=78, subsampling=1 (4:2:0)
    import io
    buf = io.BytesIO()
    padded.save(buf, format="JPEG", quality=78, subsampling=1)
    buf.seek(0)
    return Image.open(buf)

def simulate_tiktok(image: Image.Image) -> Image.Image:
    """1080x1920 (pad), H.264 simulation via aggressive JPEG."""
    img = image.convert("RGB")
    img.thumbnail((1080, 1920), Image.Resampling.LANCZOS)
    
    padded = Image.new("RGB", (1080, 1920), (0, 0, 0))
    x_offset = (1080 - img.size[0]) // 2
    y_offset = (1920 - img.size[1]) // 2
    padded.paste(img, (x_offset, y_offset))
    
    buf = io.BytesIO()
    padded.save(buf, format="JPEG", quality=75, subsampling=1)
    buf.seek(0)
    return Image.open(buf)

def simulate_twitter(image: Image.Image) -> Image.Image:
    """resize->1200x675, WebP Q=72, strip ICC"""
    img = image.convert("RGB")
    img.thumbnail((1200, 675), Image.Resampling.LANCZOS)
    
    import io
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=72)
    buf.seek(0)
    return Image.open(buf)
