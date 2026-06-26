"""
Content DNA Apex — Main API Gateway (Full Power Prototype)
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from auth.api_key import get_current_org
from auth.rate_limiter import limiter, RateLimitExceeded, _rate_limit_exceeded_handler
from storage.db_client import get_pool, close_pool, get_custody_chain
from detection.faiss_index import FAISSIndex
from viral.spread_graph import SpreadGraphManager

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── FAISS index ────────────────────────────────────────────────────────
    app.state.faiss_index = FAISSIndex.load_or_create(
        clip_dim=settings.CLIP_EMBEDDING_DIM,
        index_dir=settings.FAISS_INDEX_DIR,
    )
    app.state.faiss_index.start_periodic_persist(interval=settings.FAISS_PERSIST_INTERVAL)
    logger.info("[Startup] FAISS ready — %d vectors", app.state.faiss_index.total_vectors)

    # ── Viral spread graph (in-memory) ────────────────────────────────────
    app.state.spread_graph = SpreadGraphManager()
    logger.info("[Startup] Viral spread graph initialized")

    # ── Database pool (non-fatal) ─────────────────────────────────────────
    try:
        await get_pool()
        logger.info("[Startup] Database pool ready")
    except Exception as e:
        logger.warning("[Startup] DB unavailable — running in lite mode: %s", e)

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────
    app.state.faiss_index.stop_periodic_persist()
    app.state.faiss_index.save()
    try:
        await close_pool()
    except Exception:
        pass
    logger.info("[Shutdown] Clean shutdown complete")


app = FastAPI(
    title="Content DNA Apex",
    description="6-layer forensic DNA tracking + AI detection + watermarking + blockchain",
    version="7.1-prototype",
    lifespan=lifespan,
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.state.limiter = limiter

# ── Mount All Routers ─────────────────────────────────────────────────────────
from api.upload       import router as upload_router
from api.detect       import router as detect_router
from api.sightings    import router as sightings_router
from api.dmca         import router as dmca_router
from api.ai_routes    import router as ai_router
from api.watermark    import router as watermark_router
from api.viral_routes import router as viral_router
from api.blockchain   import router as blockchain_router
from api.alerts       import router as alerts_router

app.include_router(upload_router,      prefix="/api/v1", tags=["Registration"])
app.include_router(detect_router,      prefix="/api/v1", tags=["Detection"])
app.include_router(sightings_router,                     tags=["Sightings"])
app.include_router(dmca_router,                          tags=["DMCA"])
app.include_router(ai_router,          prefix="/api/v1", tags=["AI Detection"])
app.include_router(watermark_router,   prefix="/api/v1", tags=["Watermarking"])
app.include_router(viral_router,       prefix="/api/v1", tags=["Viral Spread"])
app.include_router(blockchain_router,  prefix="/api/v1", tags=["Blockchain"])
app.include_router(alerts_router,      prefix="/api/v1", tags=["Alerts"])

# ── Static Frontend ───────────────────────────────────────────────────────────
if os.path.isdir("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse("frontend/index.html")


# ── Well-Known Public Keys ────────────────────────────────────────────────────
@app.get("/.well-known/sports-media-keys/{org_id}.pem", include_in_schema=False)
async def get_public_key(org_id: str):
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            pem = await conn.fetchval(
                "SELECT public_key_pem FROM organizations WHERE org_id = $1::uuid", org_id
            )
        if not pem:
            raise HTTPException(status_code=404)
        return Response(content=pem, media_type="application/x-pem-file")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")


# ── Custody Chain ─────────────────────────────────────────────────────────────
@app.get("/api/v1/assets/{asset_id}/custody", tags=["Registration"])
async def get_custody(asset_id: str, org: dict = Security(get_current_org)):
    try:
        chain = await get_custody_chain(asset_id)
        return {"asset_id": asset_id, "chain": chain}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/api/v1/health", tags=["System"])
async def health_check():
    faiss = getattr(app.state, "faiss_index", None)
    spread = getattr(app.state, "spread_graph", None)

    db_ok = False
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if db_ok else "lite_mode",
        "version": "7.1-prototype",
        "faiss": {
            "vectors": faiss.total_vectors if faiss else 0,
            "trained": faiss.is_trained if faiss else False,
            "dim": settings.CLIP_EMBEDDING_DIM,
        },
        "spread_graph": {
            "nodes": spread.graph.number_of_nodes() if spread else 0,
            "edges": spread.graph.number_of_edges() if spread else 0,
        },
        "database": "ok" if db_ok else "unavailable",
        "features": [
            "6-layer DNA fingerprinting",
            "DCT + DWT + LSB + XMP watermarking",
            "AI deepfake detection",
            "AI diffusion detection",
            "viral spread tracking",
            "DMCA generation",
            "blockchain anchoring",
            "asset verification",
        ],
    }
