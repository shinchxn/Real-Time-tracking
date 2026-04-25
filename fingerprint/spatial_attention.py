import asyncio
import numpy as np
import logging
from PIL import Image
import torch
from config import settings

logger = logging.getLogger(__name__)

async def extract_clip_spatial_attention(image: Image.Image, device: str = None) -> np.ndarray:
    """
    Extract 196-dim float32 representing 14x14 saliency grid from CLIP.
    For this we need local CLIP. We extract patch embeddings.
    """
    from fingerprint.clip_embedder import _init_local, local_model, local_processor
    
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _local_spatial, image, device)
    except Exception as e:
        logger.error(f"Failed to extract spatial attention (model missing?): {e}. Fallback to zero-vector.")
        return np.zeros((196,), dtype=np.float32)

def _local_spatial(image: Image.Image, device: str = None) -> np.ndarray:
    from fingerprint.clip_embedder import _init_local, local_model, local_processor
    _init_local()
    
    target_device = device or settings.DEVICE
    img_rgb = image.convert('RGB')
    inputs = local_processor(images=img_rgb, return_tensors="pt").to(target_device)
    
    with torch.no_grad():
        # Get vision model outputs, which contains hidden_states if configured, 
        # or we approximate saliency via patch projection.
        # As an approximation for the 14x14 grid (196 total patches), 
        # if ViT-L/14 is used, image size 224 / 14 = 16 patches per side, actually it is 224/14 = 16x16 = 256.
        # Wait, the prompt specified 196-dim (which implies 14x14 grid). 14x14*16 = 224.
        # ViT-Base uses 14x14 patches (patch size 16 -> 224/16 = 14).
        # We will extract standard patch-level norm as saliency and resize to 196-dim.
        outputs = local_model.vision_model(inputs.pixel_values, output_hidden_states=True)
        # Last hidden state: (batch_size, sequence_length, hidden_size)
        last_hidden = outputs.last_hidden_state[0, 1:, :] # discard CLS token
        
        # Calculate L2 norm across hidden size to get saliency per patch
        saliency = torch.norm(last_hidden, dim=-1).cpu().numpy()
        
        # Resample to 196 if needed
        if saliency.shape[0] != 196:
            # Interpolate to 14x14
            side = int(np.sqrt(saliency.shape[0]))
            grid = saliency.reshape(1, 1, side, side)
            grid_tensor = torch.tensor(grid, dtype=torch.float32)
            import torch.nn.functional as F
            resized = F.interpolate(grid_tensor, size=(14, 14), mode='bicubic', align_corners=False)
            saliency = resized.numpy().flatten()
            
    # L2 normalize
    norm = np.linalg.norm(saliency)
    if norm > 0:
        saliency = saliency / norm
    return saliency.astype(np.float32)
