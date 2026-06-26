"""DNA Pipeline — thin async wrapper over correct module names."""
import asyncio
from PIL import Image
import numpy as np
from fingerprint.clip_embedder import get_clip_embedding
from fingerprint.spatial_attention import extract_clip_spatial_attention
from fingerprint.dct_freq import extract_dct_frequency_signature
from fingerprint.phash import extract_phashes
from fingerprint.hog import extract_hog_descriptor
from fingerprint.color_moments import extract_color_moments
from config import settings


async def extract_6_layer_dna(image: Image.Image) -> dict:
    """Run all 6 DNA layers in parallel via asyncio.gather()."""
    (clip_vec, phashes, hog_vec,
     color_vec, dct_vec, spatial_vec) = await asyncio.gather(
        get_clip_embedding(
            image, device=settings.DEVICE, model_name=settings.CLIP_MODEL
        ),
        extract_phashes(image),
        asyncio.to_thread(extract_hog_descriptor, image),
        asyncio.to_thread(extract_color_moments, image),
        asyncio.to_thread(extract_dct_frequency_signature, image),
        extract_clip_spatial_attention(image, device=settings.DEVICE),
    )
    return {
        "clip":    clip_vec,
        "phash":   str(phashes.phash),
        "dhash":   str(phashes.dhash),
        "ahash":   str(phashes.ahash),
        "hog":     hog_vec,
        "color":   color_vec,
        "dct":     dct_vec,
        "spatial": spatial_vec,
    }
