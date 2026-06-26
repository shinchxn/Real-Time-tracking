import os
import torch
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # ── API ───────────────────────────────────────────────────────────────────
    API_TITLE: str = "Content DNA — Apex Edition"
    API_VERSION: str = "8.0.0"
    DEBUG: bool = False

    # ── PostgreSQL (v6.0 — replaces Supabase) ────────────────────────────────
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/contentdna"
    )

    # ── Legacy Supabase (kept for backward compat — ignored if DATABASE_URL set)
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SQLITE_PATH: str = str(BASE_DIR / "data" / "fallback.db")

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_RESULT_URL: str = os.getenv("REDIS_RESULT_URL", "redis://localhost:6379/1")

    # ── Celery ────────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # ── CORS ─────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list = ["*"]

    # ── FAISS ─────────────────────────────────────────────────────────────────
    FAISS_INDEX_DIR: str = os.getenv(
        "FAISS_INDEX_DIR",
        str(BASE_DIR / "data" / "faiss")
    )
    FAISS_NLIST: int = 512
    FAISS_NPROBE: int = 64
    FAISS_PERSIST_INTERVAL: int = 600  # seconds

    # ── ML & GPU ──────────────────────────────────────────────────────────
    DEVICE: str = "cuda" if torch.cuda.is_available() else "cpu"
    # v8.0: auto-select model size based on device
    CLIP_MODEL: str = os.getenv("CLIP_MODEL", "openai/clip-vit-base-patch32")
    # Auto-detect embedding dim from model name (large=768, base=512)
    CLIP_EMBEDDING_DIM: int = 768 if "large" in os.getenv("CLIP_MODEL", "") else 512

    # ── Detection Thresholds ──────────────────────────────────────────────────
    THRESHOLD_CRITICAL: float = 0.96
    THRESHOLD_HIGH: float = 0.87
    THRESHOLD_MEDIUM: float = 0.74
    THRESHOLD_WATCH: float = 0.60
    MATCH_THRESHOLD: float = float(os.getenv("MATCH_THRESHOLD", "0.92"))

    # ── Fusion Weights (v8.0 tuned — local CLIP proven reliable) ─────────────
    WEIGHT_CLIP: float = 0.45      # increased: most reliable layer
    WEIGHT_PHASH: float = 0.20     # increased: zero cost, very accurate
    WEIGHT_HOG: float = 0.05
    WEIGHT_DCT_FREQ: float = 0.15
    WEIGHT_COLOR: float = 0.05     # decreased: too easily fooled by crops
    WEIGHT_SPATIAL: float = 0.10

    # ── Instagram Credentials ─────────────────────────────────────────────────
    INSTAGRAM_USERNAME: str = os.getenv("INSTAGRAM_USERNAME", "")
    INSTAGRAM_PASSWORD: str = os.getenv("INSTAGRAM_PASSWORD", "")
    INSTAGRAM_SESSION_ENC: str = os.getenv("INSTAGRAM_SESSION_ENC", "")
    FERNET_KEY: str = os.getenv("FERNET_KEY", "")

    # ── Watermark ─────────────────────────────────────────────────────────────
    WATERMARK_MASTER_SEED: int = int(
        os.getenv("WATERMARK_MASTER_SEED", str(0xDEADBEEF)), 0
    )
    import secrets
    WATERMARK_SEED: int = int(os.getenv("WATERMARK_SEED", secrets.randbits(32)))

    # ── Evidence Store ────────────────────────────────────────────────────────
    EVIDENCE_DIR: str = os.getenv("EVIDENCE_DIR", str(BASE_DIR / "data" / "evidence"))

    # ── Blockchain ────────────────────────────────────────────────────────────
    ZK_PROOF_DIR: str = str(BASE_DIR / "data" / "proofs")
    POLYGON_RPC: str = os.getenv("POLYGON_RPC", "https://polygon-rpc.com")
    POLYGON_CHAIN_ID: int = 137

    # ── Blockchain (Vault) ───────────────────────────────────────────────────
    WEB3_RPC_URL: str = os.getenv("WEB3_RPC_URL", "https://polygon-rpc.com")
    CONTRACT_ADDRESS: str = os.getenv("CONTRACT_ADDRESS", "")
    CHAIN_ID: int = int(os.getenv("CHAIN_ID", "137"))
    BLOCKCHAIN_KEY_ENCRYPTION_KEY: str = os.getenv("BLOCKCHAIN_KEY_ENCRYPTION_KEY", "")

    # ── Reverse Image Search (v8.0: local FAISS + SauceNAO free) ─────────────
    SAUCENAO_API_KEY: str = os.getenv("SAUCENAO_API_KEY", "")

    # ── IPFS ─────────────────────────────────────────────────────────────────
    IPFS_GATEWAY: str = os.getenv("IPFS_GATEWAY", "https://ipfs.io/ipfs/")
    IPFS_API_URL: str = os.getenv("IPFS_API_URL", "http://localhost:5001")

    # ── DMCA Evidence ─────────────────────────────────────────────────────────
    DMCA_TEMPLATE_PATH: str = os.getenv(
        "DMCA_TEMPLATE_PATH",
        str(BASE_DIR / "data" / "dmca_template.html")
    )
    DMCA_SENDER_NAME: str = os.getenv("DMCA_SENDER_NAME", "")
    DMCA_SENDER_EMAIL: str = os.getenv("DMCA_SENDER_EMAIL", "")

    # ── Discovery ─────────────────────────────────────────────────────────────
    WEB_CRAWL_TARGETS: list = []

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Ensure all required directories exist
for _d in [
    settings.FAISS_INDEX_DIR,
    settings.ZK_PROOF_DIR,
    settings.EVIDENCE_DIR,
    str(Path(settings.SQLITE_PATH).parent),
]:
    os.makedirs(_d, exist_ok=True)
