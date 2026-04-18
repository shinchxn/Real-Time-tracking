"""
Platform Transform Simulator
Simulates platform-specific processing (compression, resizing, filtering) 
to improve match rates on social media content.
"""
import cv2
import numpy as np
from PIL import Image, ImageEnhance

def simulate_instagram(image: Image.Image) -> Image.Image:
    """Simulate Instagram's pipeline: 1080x1350 resize + high JPEG compression."""
    # Resize
    img = image.resize((1080, 1350), Image.Resampling.LANCZOS) if image.width > 1080 else image
    
    # Slight saturation increase
    converter = ImageEnhance.Color(img)
    img = converter.enhance(1.1)
    
    # Save as low-q JPEG and reload
    from io import BytesIO
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=65)
    buf.seek(0)
    return Image.open(buf)

def simulate_tiktok(image: Image.Image) -> Image.Image:
    """Simulate TikTok's vertical crop + standard compression."""
    w, h = image.size
    aspect = 9/16
    if w/h > aspect:
        # Too wide, crop sides
        new_w = h * aspect
        left = (w - new_w) / 2
        image = image.crop((left, 0, left + new_w, h))
    
    # Save as mid-q JPEG
    from io import BytesIO
    buf = BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=75)
    buf.seek(0)
    return Image.open(buf)

def apply_simulators(image: Image.Image, platforms=None) -> list:
    """Apply all simulators and return a list of variants."""
    if platforms is None:
        platforms = ["instagram", "tiktok"]
    
    variants = [image] # Original
    if "instagram" in platforms:
        variants.append(simulate_instagram(image))
    if "tiktok" in platforms:
        variants.append(simulate_tiktok(image))
        
    return variants
