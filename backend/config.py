"""
Configuration for Digital Asset Protection System
"""
import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """Application settings"""
    
    # API Configuration
    API_TITLE: str = "Digital Asset Protection System"
    API_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # CLIP Model
    CLIP_MODEL: str = "ViT-B/32"
    USE_CUDA: bool = False
    DEVICE: str = "cpu"
    
    # FAISS Settings
    FAISS_INDEX_PATH: str = str(BASE_DIR / "data" / "faiss_index.bin")
    FAISS_METADATA_PATH: str = str(BASE_DIR / "data" / "metadata.json")
    
    # Similarity Threshold
    SIMILARITY_THRESHOLD: float = 0.85
    WARNING_THRESHOLD: float = 0.75
    
    # File Upload
    UPLOAD_DIR: str = str(BASE_DIR / "data" / "uploads")
    MAX_FILE_SIZE: int = 50 * 1024 * 1024
    ALLOWED_EXTENSIONS: List[str] = ["jpg", "jpeg", "png", "gif", "bmp", "webp", "mp4", "avi", "mov"]
    
    # Video Processing
    VIDEO_FRAME_INTERVAL: int = 30
    VIDEO_MAX_FRAMES: int = 10
    
    # Hash Settings
    PHASH_SIZE: int = 8
    
    # Storage
    STORAGE_TYPE: str = "local"
    GCS_BUCKET: str = ""
    
    # Alerts
    ALERT_ENABLED: bool = True
    ALERT_WEBHOOK: str = ""
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra env vars

settings = Settings()

# Set device based on USE_CUDA if needed
if settings.USE_CUDA and settings.DEVICE == "cpu":
    settings.DEVICE = "cuda"

# Create necessary directories
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(settings.FAISS_INDEX_PATH), exist_ok=True)
