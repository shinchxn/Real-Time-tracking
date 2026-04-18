"""
Video Temporal Hash Sequence (THS) & DTW Alignment
Extracts a sequence of fingerprints over time to detect short clips in long videos.
Uses FastDTW for robust alignment against speed changes and frame dropping.
"""
import logging
import numpy as np
from moviepy.editor import VideoFileClip
from typing import List, Tuple
from fastdtw import fastdtw
from scipy.spatial.distance import cosine

from fingerprint.phash import extract_phashes
from fingerprint.clip_embedder import get_clip_embedding
from config import settings

logger = logging.getLogger(__name__)

async def extract_video_ths(video_path: str) -> List[np.ndarray]:
    """
    Extract a sequence of CLIP embeddings (THS) from a video.
    """
    ths = []
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration
        
        # Sample frames at settings.VIDEO_FPS (default 1 fps)
        for t in np.arange(0, duration, 1.0 / settings.VIDEO_FPS):
            frame = clip.get_frame(t)
            from PIL import Image
            img = Image.fromarray(frame)
            
            # For efficiency in THS, we use CLIP
            # (In production, maybe use a lighter model)
            embedding = await get_clip_embedding(img, device=settings.DEVICE)
            ths.append(embedding)
            
        clip.close()
    except Exception as exc:
        logger.error(f"Failed to extract video THS: {exc}")
        
    return ths

def compare_video_ths(query_ths: List[np.ndarray], target_ths: List[np.ndarray]) -> float:
    """
    Compare two Temporal Hash Sequences using Dynamic Time Warping.
    Returns a similarity score [0, 1].
    """
    if not query_ths or not target_ths:
        return 0.0
    
    # DTW distance (lower is better)
    distance, path = fastdtw(query_ths, target_ths, dist=cosine)
    
    # Normalize distance by path length
    norm_dist = distance / len(path)
    
    # Convert distance to similarity
    similarity = 1.0 - np.clip(norm_dist, 0, 1)
    
    return float(similarity)
