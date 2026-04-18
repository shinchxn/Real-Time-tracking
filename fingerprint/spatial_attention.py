"""
Layer 6 — CLIP Spatial Attention Map
Extracts localized semantic features from the CLIP transformer's spatial tokens.
Designed to detect partial crops and collage attacks.
"""
import logging
import torch
import numpy as np
from PIL import Image
from typing import Optional

logger = logging.getLogger(__name__)

# Re-use globals from clip_embedder if possible, or manage independently
_clip_model = None
_clip_preprocess = None
_clip_device = "cpu"

def _load_clip_spatial(device: str, model_name: str = "ViT-L/14"):
    global _clip_model, _clip_preprocess, _clip_device
    if _clip_model is not None:
        return _clip_model, _clip_preprocess
    import clip
    model, preprocess = clip.load(model_name, device=device)
    _clip_model = model
    _clip_preprocess = preprocess
    _clip_device = device
    return model, preprocess

async def extract_clip_spatial_attention(
    image: Image.Image,
    device: str = "cpu",
    model_name: str = "ViT-L/14"
) -> np.ndarray:
    """
    Extract a 256-dim spatial attention signature.
    
    Instead of the global pool ([CLS] token), we extract the spatial grid tokens
    and aggregate them into a fixed-size signature that captures 'where' things are.
    """
    try:
        model, preprocess = _load_clip_spatial(device, model_name)
        input_tensor = preprocess(image).unsqueeze(0).to(_clip_device)
        
        with torch.no_grad():
            # Get patch embeddings (spatial tokens)
            # For ViT-L/14, patches are 14x14. Image is 224x224. 
            # 224/14 = 16 patches per side -> 256 patches.
            
            # Accessing internal ViT blocks to get spatial features
            visual = model.visual
            x = visual.conv1(input_tensor.type(visual.conv1.weight.dtype)) # shape [1, 1024, 16, 16]
            x = x.reshape(x.shape[0], x.shape[1], -1)  # shape [1, 1024, 256]
            x = x.permute(0, 2, 1)  # shape [1, 256, 1024]
            
            # Use the class token concept but keep the grid
            x = torch.cat([visual.class_embedding.to(x.dtype) + torch.zeros(x.shape[0], 1, x.shape[-1], dtype=x.dtype, device=x.device), x], dim=1)  # [1, 257, 1024]
            x = x + visual.positional_embedding.to(x.dtype)
            x = visual.ln_pre(x)

            x = x.permute(1, 0, 2)  # NLD -> LND
            x = visual.transformer(x)
            x = x.permute(1, 0, 2)  # LND -> NLD
            
            # x is [1, 257, 1024]. Index 0 is [CLS]. 1-256 are spatial.
            spatial_tokens = x[0, 1:, :] # [256, 1024]
            
            # Project or pool to 256 dims for storage efficiency
            # We'll take the mean across the feature dimension in 4x4 blocks to get 16x16=256 dims
            # and then L2 normalize.
            
            # Simple version: Take the mean of the 1024-d vector to get 1 value per patch
            # resulting in a 256-d vector.
            spatial_sig = spatial_tokens.mean(dim=-1).cpu().numpy().astype(np.float32) # [256]
            
            # L2 Normalize
            norm = np.linalg.norm(spatial_sig) + 1e-8
            spatial_sig = spatial_sig / norm
            
            return spatial_sig
            
    except Exception as exc:
        logger.error(f"Failed to extract CLIP spatial attention: {exc}")
        # Return zeros as fallback
        return np.zeros(256, dtype=np.float32)
