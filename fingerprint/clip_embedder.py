"""
Layer 1 — Semantic Embedding via CLIP ViT-L/14 (768-dim)
Fallback: NVIDIA NV-Embed-v2 via HTTP API
"""
import io
import logging
from typing import Optional

import httpx
import numpy as np
import torch
from PIL import Image

logger = logging.getLogger(__name__)

# Lazy-loaded globals
_clip_model = None
_clip_preprocess = None
_clip_device: str = "cpu"


def _load_clip(device: str, model_name: str = "ViT-L/14") -> None:
    """Load CLIP model once into module-level globals."""
    global _clip_model, _clip_preprocess, _clip_device
    if _clip_model is not None:
        return
    import clip  # local import — optional dependency at module level
    logger.info("Loading CLIP %s on %s …", model_name, device)
    _clip_model, _clip_preprocess = clip.load(model_name, device=device)
    _clip_model.eval()
    _clip_device = device
    logger.info("CLIP model ready.")


async def extract_clip_embedding(
    image: Image.Image,
    device: str = "cpu",
    model_name: str = "ViT-L/14",
) -> np.ndarray:
    """
    Extract a 768-dim L2-normalised CLIP embedding.

    Returns:
        np.ndarray of shape (768,), dtype float32.
    """
    try:
        _load_clip(device, model_name)
        tensor = _clip_preprocess(image).unsqueeze(0).to(_clip_device)
        with torch.no_grad():
            features = _clip_model.encode_image(tensor)
            features = features / features.norm(dim=-1, keepdim=True)
        vec = features.cpu().numpy().astype(np.float32).flatten()
        return vec
    except Exception:
        logger.exception("Local CLIP failed — falling back to NVIDIA API")
        raise


async def extract_clip_nvidia_fallback(
    image: Image.Image,
    api_key: str,
    api_url: str = "https://integrate.api.nvidia.com/v1/embeddings",
    model: str = "nvidia/nv-embedv2",
) -> np.ndarray:
    """
    Fallback: call NVIDIA NV-Embed-v2 API when local CLIP is unavailable.

    Returns:
        np.ndarray of shape (768,), dtype float32.
    """
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    import base64
    encoded = base64.b64encode(img_bytes).decode()

    payload = {
        "input": [encoded],
        "model": model,
        "encoding_format": "float",
        "input_type": "image",
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(api_url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    embedding = np.array(data["data"][0]["embedding"], dtype=np.float32)
    # L2-normalise
    norm = np.linalg.norm(embedding) + 1e-8
    embedding = embedding / norm
    # Ensure 768-dim — pad or truncate if the API returns a different dim
    if embedding.shape[0] < 768:
        embedding = np.pad(embedding, (0, 768 - embedding.shape[0]))
    elif embedding.shape[0] > 768:
        embedding = embedding[:768]
    return embedding


async def get_clip_embedding(
    image: Image.Image,
    device: str = "cpu",
    model_name: str = "ViT-L/14",
    nvidia_api_key: str = "",
    nvidia_api_url: str = "",
) -> np.ndarray:
    """
    Top-level helper — tries local CLIP first, then NVIDIA fallback.
    """
    try:
        return await extract_clip_embedding(image, device, model_name)
    except Exception:
        if nvidia_api_key:
            logger.warning("Using NVIDIA embedding API as fallback")
            return await extract_clip_nvidia_fallback(
                image, nvidia_api_key, nvidia_api_url or
                "https://integrate.api.nvidia.com/v1/embeddings",
            )
        raise
