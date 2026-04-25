import asyncio
import base64
import numpy as np
import io
from PIL import Image
from httpx import AsyncClient
from config import settings
import logging

try:
    from transformers import CLIPProcessor, CLIPModel
    import torch
except ImportError:
    pass

logger = logging.getLogger(__name__)

local_model = None
local_processor = None

def _encode_base64(image: Image.Image) -> str:
    buf = io.BytesIO()
    img_rgb = image.convert('RGB')
    # Resize to standard to avoid size limit
    img_rgb.thumbnail((512, 512))
    img_rgb.save(buf, format='JPEG', quality=85)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def _load_clip(device: str = "cpu", model_name: str = "openai/clip-vit-large-patch14"):
    global local_model, local_processor
    if local_model is None:
        logger.info(f"Loading local CLIP model: {model_name} on {device}")
        local_model = CLIPModel.from_pretrained(model_name).to(device)
        local_processor = CLIPProcessor.from_pretrained(model_name)

def _init_local():
    _load_clip(settings.DEVICE, settings.CLIP_MODEL)

async def get_clip_embedding(
    image: Image.Image,
    device: str = "cpu",
    model_name: str = "openai/clip-vit-large-patch14",
    nvidia_api_key: str = "",
    nvidia_api_url: str = ""
) -> np.ndarray:
    """Extract 768-dim CLIP embedding asynchronously. Try NVIDIA, fallback to local."""
    vec = None
    if nvidia_api_key:
        try:
            b64_img = _encode_base64(image)
            async with AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    nvidia_api_url or settings.NVIDIA_API_URL,
                    headers={
                        "Authorization": f"Bearer {nvidia_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": settings.NVIDIA_MODEL,
                        "input": [f"data:image/jpeg;base64,{b64_img}"]
                    }
                )
                resp.raise_for_status()
                data = resp.json()
                vec = np.array(data['data'][0]['embedding'], dtype=np.float32)
        except Exception as e:
            logger.warning(f"NVIDIA API failed: {e}. Falling back to local CLIP.")
    
    if vec is None:
        try:
            # Fallback to local CPU/GPU calculation block
            _init_local()
            # Run local CPU bound operation in executor to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            vec = await loop.run_in_executor(None, _local_inference, image)
        except Exception as e:
            logger.error(f"Local CLIP model failed to load or run: {e}. Generating zero-vector fallback.")
            from config import settings as s
            vec = np.zeros((s.CLIP_EMBEDDING_DIM,), dtype=np.float32)
    
    # L2 correct and normalize
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec

def _local_inference(image: Image.Image) -> np.ndarray:
    img_rgb = image.convert('RGB')
    inputs = local_processor(images=img_rgb, return_tensors="pt").to(settings.DEVICE)
    with torch.no_grad():
        image_features = local_model.get_image_features(**inputs)
    return image_features.cpu().numpy()[0].astype(np.float32)
