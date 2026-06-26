"""
CLIP Embedder — Content DNA Apex v8.0
Always uses local HuggingFace CLIP. NVIDIA API removed.

Auto-selects model size based on available hardware:
  CPU  → openai/clip-vit-base-patch32   (fast, 512-dim)
  CUDA → openai/clip-vit-large-patch14  (accurate, 768-dim)
"""
import asyncio
import io
import logging

import numpy as np
from PIL import Image

try:
    from transformers import CLIPProcessor, CLIPModel
    import torch
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Module-level cache — loaded once per process / Celery worker
local_model = None
local_processor = None


def _init_local_with_model(model_name: str, device: str):
    """Load (or reload) the CLIP model if the requested model differs from the cached one."""
    global local_model, local_processor
    cached_name = getattr(local_model, "_model_name", None)
    if local_model is None or cached_name != model_name:
        logger.info("Loading CLIP model: %s on %s", model_name, device)
        local_model = CLIPModel.from_pretrained(model_name).to(device)
        local_model._model_name = model_name  # tag so we can detect model changes
        local_processor = CLIPProcessor.from_pretrained(model_name)


def _local_inference(image: Image.Image) -> np.ndarray:
    """Run synchronous CLIP inference. Called from executor to avoid blocking the event loop."""
    from config import settings

    img_rgb = image.convert("RGB")
    inputs = local_processor(images=img_rgb, return_tensors="pt").to(settings.DEVICE)
    with torch.no_grad():
        out = local_model.get_image_features(**inputs)
        # Handle different output types across HF versions
        if hasattr(out, "image_embeds"):
            out = out.image_embeds
        elif hasattr(out, "pooler_output"):
            out = out.pooler_output
        elif not hasattr(out, "cpu") and type(out).__name__ != "Tensor":
            out = out[0]

    return out.cpu().numpy()[0].astype(np.float32)


async def get_clip_embedding(
    image: Image.Image,
    device: str = "cpu",
    model_name: str = None,       # auto-select based on device if None
    nvidia_api_key: str = "",     # IGNORED in v8.0 — always local
    nvidia_api_url: str = "",     # IGNORED in v8.0 — always local
) -> np.ndarray:
    """
    v8.0: Always uses local HuggingFace CLIP. NVIDIA API params kept for
    backward-compatible call sites but are silently ignored.

    Auto-selects model:
      CPU  → clip-vit-base-patch32  (512-dim)
      CUDA → clip-vit-large-patch14 (768-dim)
    """
    from config import settings

    if model_name is None:
        model_name = (
            "openai/clip-vit-large-patch14"
            if settings.DEVICE == "cuda"
            else "openai/clip-vit-base-patch32"
        )

    _init_local_with_model(model_name, device or settings.DEVICE)

    try:
        loop = asyncio.get_running_loop()
        vec = await loop.run_in_executor(None, _local_inference, image)
    except Exception as e:
        logger.error("Local CLIP inference failed: %s — returning zero vector", e)
        dim = 768 if "large" in model_name else 512
        vec = np.zeros((dim,), dtype=np.float32)

    # L2 normalise
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec
