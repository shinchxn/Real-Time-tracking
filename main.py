"""
Content DNA — FastAPI Application Entry Point

Lifespan management, CORS, router registration, health endpoint.
Brings together all 12 architectural layers into a single runnable server.
"""
import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-28s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("content-dna")

# ── Shared application state (populated during lifespan) ─────────────
app_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("=" * 70)
    logger.info("  Content DNA — Universal Tracking System  v%s", settings.API_VERSION)
    logger.info("=" * 70)

    # ── Import v3 components ─────────────────────────────────────────
    from detection.faiss_index import FAISSIndex
    from db.supabase_client import SupabaseClient
    from detection.zk_proofs import ProofManager

    # ── FAISS Index ──────────────────────────────────────────────────
    faiss_index = FAISSIndex(
        clip_dim=settings.CLIP_EMBEDDING_DIM,
        hog_dim=128,
        color_dim=9,
        dct_dim=128,      # v3
        spatial_dim=256,  # v3
        nlist=settings.FAISS_NLIST,
        nprobe=settings.FAISS_NPROBE,
        index_dir=settings.FAISS_INDEX_DIR,
    )
    faiss_index.load()
    faiss_index.start_periodic_persist(interval=settings.FAISS_PERSIST_INTERVAL)
    logger.info("✓ FAISS index ready  (%d vectors)", faiss_index.total_vectors)

    # ── Supabase / SQLite ────────────────────────────────────────────
    supabase = SupabaseClient()
    sb_ok = await supabase.ping()
    if sb_ok:
        logger.info("✓ Supabase connection OK")
        synced = await supabase.sync_pending()
        if synced:
            logger.info("  ↳ synced %d pending records", synced)
    else:
        logger.warning("⚠ Supabase unavailable — using SQLite fallback at %s",
                        settings.SQLITE_PATH)

    # ── CLIP pre-load (optional warm-up) ─────────────────────────────
    try:
        from fingerprint.clip_embedder import _load_clip
        _load_clip(settings.DEVICE, settings.CLIP_MODEL)
        logger.info("✓ CLIP %s loaded on %s", settings.CLIP_MODEL, settings.DEVICE)
    except Exception:
        logger.warning("⚠ CLIP local model not available — will use NVIDIA fallback")

    # ── Populate shared state ────────────────────────────────────────
    app.state.faiss_index = faiss_index
    app.state.supabase = supabase
    app.state.proof_manager = ProofManager(settings.ZK_PROOF_DIR) # v3

    logger.info("=" * 70)
    logger.info("  System READY — accepting requests on port 8000")
    logger.info("=" * 70)

    yield  # ← application runs here

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("Shutting down …")
    faiss_index.stop_periodic_persist()
    faiss_index.save()
    logger.info("✓ FAISS index persisted")
    logger.info("Goodbye.")


# ── FastAPI app ──────────────────────────────────────────────────────
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description=(
        "AI-powered media fingerprinting, tracking, and violation detection. "
        "4-layer Content DNA (CLIP + pHash + Color Moments + HOG), "
        "FAISS vector search, DCT watermarking, real-time alerts."
    ),
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ────────────────────────────────────────────────
from api.upload import router as upload_router
from api.detect import router as detect_router
from api.alerts import router as alerts_router
from api.watermark import router as watermark_router

app.include_router(upload_router, tags=["Upload"])
app.include_router(detect_router, tags=["Detection"])
app.include_router(alerts_router, tags=["Alerts"])
app.include_router(watermark_router, tags=["Watermark"])


# ── Health & root endpoints ──────────────────────────────────────────

@app.get("/health")
async def health():
    """System health check (v3 Apex)."""
    fi = getattr(app.state, "faiss_index", None)
    sb = getattr(app.state, "supabase", None)

    faiss_stats = fi.get_stats() if fi else {}
    sb_ok = await sb.ping() if sb else False
    
    # v3 features status
    features = ["6-layer DNA", "DCT Freq", "CLIP Spatial", "THS", "ZK Proofs"]

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "3.0.0-apex",
        "faiss": faiss_stats,
        "supabase": "connected" if sb_ok else "disconnected",
        "device": settings.DEVICE,
        "features": features
    }


@app.get("/")
async def root():
    return {
        "service": "Content DNA — Universal Tracking System",
        "version": settings.API_VERSION,
        "docs": "/docs",
        "health": "/health",
    }


# ── Direct execution ────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=settings.DEBUG,
    )
