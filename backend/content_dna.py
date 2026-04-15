"""
Content DNA Generator: Extract visual embeddings and perceptual hash
"""
import io
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Union
import cv2
from PIL import Image
import torch
import clip
from config import settings
import logging

logger = logging.getLogger(__name__)


class ContentDNAGenerator:
    """Generate Content DNA (visual embedding + perceptual hash)"""
    
    def __init__(self):
        """Initialize CLIP model and device"""
        self.device = settings.DEVICE
        self.clip_model_name = settings.CLIP_MODEL
        
        logger.info(f"Loading CLIP model: {self.clip_model_name} on {self.device}")
        self.model, self.preprocess = clip.load(self.clip_model_name, device=self.device)
        self.model.eval()
        
    def extract_visual_embedding(self, image: Union[Image.Image, np.ndarray]) -> np.ndarray:
        """
        Extract visual embedding using CLIP
        
        Args:
            image: PIL Image or numpy array (RGB)
            
        Returns:
            np.ndarray: 512-dim or 768-dim embedding vector (normalized)
        """
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        
        # Preprocess image for CLIP
        image_tensor = self.preprocess(image).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            image_features = self.model.encode_image(image_tensor)
            # Normalize embedding
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        
        return image_features.cpu().numpy().flatten()
    
    def compute_phash(self, image: Union[Image.Image, np.ndarray]) -> str:
        """
        Compute perceptual hash (pHash) for image
        
        Args:
            image: PIL Image or numpy array (RGB)
            
        Returns:
            str: 64-character hex string (64-bit hash)
        """
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)
        
        # Resize to small size
        size = settings.PHASH_SIZE
        image = image.convert("L")  # Grayscale
        image = image.resize((size, size), Image.Resampling.LANCZOS)
        
        # Compute DCT
        pixels = np.array(image, dtype=np.float32)
        dct = cv2.dct(pixels)
        
        # Get average of top-left 8x8
        dct_reduced = dct[:8, :8]
        avg = dct_reduced.mean()
        
        # Create binary hash
        hash_bits = (dct_reduced > avg).flatten()
        hash_int = sum(bit << i for i, bit in enumerate(hash_bits))
        
        return format(hash_int, '016x')  # 64-bit hex
    
    def extract_content_dna(self, image_path: str) -> dict:
        """
        Extract complete Content DNA for an image
        
        Args:
            image_path: Path to image file
            
        Returns:
            dict: {
                'embedding': np.ndarray,
                'phash': str,
                'shape': tuple,
                'format': str
            }
        """
        try:
            # Load image
            image = Image.open(image_path)
            original_format = image.format
            original_shape = image.size  # (width, height)
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Extract features
            embedding = self.extract_visual_embedding(image)
            phash = self.compute_phash(image)
            
            logger.info(f"Extracted DNA from {Path(image_path).name}: phash={phash}")
            
            return {
                'embedding': embedding,
                'phash': phash,
                'shape': original_shape,
                'format': original_format or 'UNKNOWN'
            }
        except Exception as e:
            logger.error(f"Error extracting Content DNA from {image_path}: {e}")
            raise
    
    def extract_video_dna(self, video_path: str) -> dict:
        """
        Extract Content DNA from video (sample frames)
        
        Args:
            video_path: Path to video file
            
        Returns:
            dict: {
                'embeddings': list of np.ndarray,
                'phashes': list of str,
                'frame_count': int,
                'fps': float,
                'duration': float
            }
        """
        try:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            
            embeddings = []
            phashes = []
            
            frame_interval = settings.VIDEO_FRAME_INTERVAL
            frame_count = 0
            
            while cap.isOpened() and len(embeddings) < settings.VIDEO_MAX_FRAMES:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Sample every N frames
                if frame_count % frame_interval == 0:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_pil = Image.fromarray(frame_rgb)
                    
                    embedding = self.extract_visual_embedding(frame_pil)
                    phash = self.compute_phash(frame_pil)
                    
                    embeddings.append(embedding)
                    phashes.append(phash)
                
                frame_count += 1
            
            cap.release()
            logger.info(f"Extracted {len(embeddings)} frames from video")
            
            return {
                'embeddings': embeddings,
                'phashes': phashes,
                'frame_count': len(embeddings),
                'fps': fps,
                'duration': duration,
                'total_frames': total_frames
            }
        except Exception as e:
            logger.error(f"Error extracting video DNA from {video_path}: {e}")
            raise
