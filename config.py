"""
Content DNA — Configuration
Environment variables, thresholds, model settings, storage paths.
"""
import os
import torch
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Application-wide settings loaded from environment / .env file."""

    # ── API ──────────────────────────────────────────────────────────
    API_TITLE: str = "Content DNA — Universal Tracking System"
    API_VERSION: str = "2.0.0"
    DEBUG: bool = False

    # ── CLIP Model ───────────────────────────────────────────────────
    CLIP_MODEL: str = "ViT-L/14"
    CLIP_EMBEDDING_DIM: int = 768
    USE_CUDA: bool = True
    DEVICE: str = ""  # auto-detected below

    # ── NVIDIA Fallback ──────────────────────────────────────────────
    NVIDIA_API_KEY: str = ""
    NVIDIA_API_URL: str = "https://integrate.api.nvidia.com/v1/embeddings"
    NVIDIA_MODEL: str = "nvidia/nv-embedv2"

    # ── FAISS ────────────────────────────────────────────────────────
    FAISS_INDEX_DIR: str = str(BASE_DIR / "data" / "faiss")
    FAISS_CLIP_INDEX: str = "clip_ivf.index"
    FAISS_HOG_INDEX: str = "hog_flat.index"
    FAISS_NLIST: int = 256
    FAISS_NPROBE: int = 32
    FAISS_PERSIST_INTERVAL: int = 300  # seconds

    # ── Supabase ─────────────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    SUPABASE_BUCKET: str = "content-dna-assets"

    # ── Thresholds ───────────────────────────────────────────────────
    THRESHOLD_CRITICAL: float = 0.94
    THRESHOLD_HIGH: float = 0.85
    THRESHOLD_MEDIUM: float = 0.72

    # ── Fusion Weights ───────────────────────────────────────────────
    WEIGHT_CLIP: float = 0.55
    WEIGHT_PHASH: float = 0.25
    WEIGHT_COLOR: float = 0.12
    WEIGHT_HOG: float = 0.08

    # ── File Upload ──────────────────────────────────────────────────
    UPLOAD_DIR: str = str(BASE_DIR / "data" / "uploads")
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100 MB
    ALLOWED_EXTENSIONS: List[str] = [
        "jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff",
        "mp4", "avi", "mov", "mkv",
    ]

    # ── Video Processing ─────────────────────────────────────────────
    VIDEO_FRAME_INTERVAL: int = 30
    VIDEO_MAX_FRAMES: int = 20

    # ── Watermark ────────────────────────────────────────────────────
    WATERMARK_ALPHA: float = 0.08
    WATERMARK_BLOCK_SIZE: int = 8

    # ── SQLite Fallback ──────────────────────────────────────────────
    SQLITE_PATH: str = str(BASE_DIR / "data" / "fallback.db")

    # ── Alerts ───────────────────────────────────────────────────────
    ALERT_WEBHOOK_URL: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# ── Auto-detect device ───────────────────────────────────────────────
if not settings.DEVICE:
    if settings.USE_CUDA and torch.cuda.is_available():
        settings.DEVICE = "cuda"
    else:
        settings.DEVICE = "cpu"

# ── Ensure directories ──────────────────────────────────────────────
for _d in [settings.UPLOAD_DIR, settings.FAISS_INDEX_DIR,
           str(Path(settings.SQLITE_PATH).parent)]:
    os.makedirs(_d, exist_ok=True)
