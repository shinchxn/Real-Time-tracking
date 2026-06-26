"""
Content DNA Apex v7.1 — Main API Gateway
FastAPI application with multi-layered forensic routes,
distributed matching pipeline, and sports-media-keys trust anchor.
"""
import os
import shutil
import tempfile
import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Security, UploadFile, File, Request
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from auth.api_key import get_current_org
from auth.rate_limiter import limiter, RateLimitExceeded, _rate_limit_exceeded_handler
from storage.db_client import get_pool, close_pool, get_recent_sightings, get_custody_chain
from background_tasks import fingerprint_and_match, generate_dmca

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB pool
    try:
        await get_pool()
    except Exception as e:
        logging.warning(f"Could not connect to Database. Running in Lite Mode. Error: {e}")
    yield
    # Shutdown: Close DB pool
    try:
        await close_pool()
    except Exception:
        pass


app = FastAPI(
    title="Content DNA Apex",
    version="7.1",
    lifespan=lifespan
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.state.limiter = limiter

# ── Well-Known Keys (No Auth) ────────────────────────────────────────────────
@app.get("/.well-known/sports-media-keys/{org_id}.pem")
async def get_public_key(org_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        pem = await conn.fetchval("SELECT public_key_pem FROM organizations WHERE org_id = $1::uuid", org_id)
        if not pem:
            raise HTTPException(status_code=404)
        return Response(content=pem, media_type="application/x-pem-file")

# ── Asset Management ──────────────────────────────────────────────────────────

@app.post("/api/v1/assets/register")
@limiter.limit("100/hour")
async def register_asset(
    request: Request,
    org: dict = Depends(get_current_org),
    file: UploadFile = File(...)
):
    """
    1. Save original to storage
    2. Convert/Embed to .sdna
    3. Register in DB
    4. Trigger Blockchain Anchor
    5. Trigger Discovery Dork Sweep
    """
    from formats.sdna_converter import SDNAConverter
    from storage.db_client import create_asset_record

    asset_id = str(uuid.uuid4())

    # FIX 4: Use tempfile and clean up in finally
    os.makedirs("data", exist_ok=True)
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=f"_{file.filename}",
        dir="data"
    ) as tmp:
        shutil.copyfileobj(file.file, tmp)
        temp_path = tmp.name

    try:
        # Convert to SDNA (Embeds watermarks & metadata)
        converter = SDNAConverter(org_id=org["org_id"])
        sdna_bytes = await converter.to_sdna(
            input_path=temp_path,
            asset_uuid=asset_id,
            org_name=org.get("org_name", "Unknown Org"),
            watermark_seed=int(os.environ.get("WATERMARK_SEED", "12345"))  # FIX 3
        )

        sdna_path = f"data/vault/{asset_id}.sdna"
        os.makedirs("data/vault", exist_ok=True)
        with open(sdna_path, "wb") as f:
            f.write(sdna_bytes)

        # Register in DB
        asset_record = await create_asset_record(
            asset_id=asset_id,
            org_id=org["org_id"],
            filename=file.filename,
            sdna_url=sdna_path
        )

        # Trigger Background Tasks
        from background_tasks import run_dork_sweep, anchor_to_blockchain
        anchor_to_blockchain.delay(asset_id)
        run_dork_sweep.delay(asset_id, asset_record)

    finally:
        # FIX 4: Always clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return {
        "status": "registered",
        "asset_id": asset_id,
        "sdna_url": sdna_path,
        "blockchain_anchor": "pending"
    }


@app.post("/api/v1/assets/verify")
async def verify_asset(file: UploadFile = File(...)):
    """Verify any .sdna or image file against registered DNA. Not yet implemented."""
    raise HTTPException(
        status_code=501,
        detail="Verification feature coming in v8"
    )


@app.get("/api/v1/assets/{asset_id}/custody")
async def get_custody(asset_id: str, org: dict = Depends(get_current_org)):
    chain = await get_custody_chain(asset_id)
    return {"asset_id": asset_id, "chain": chain}


# ── Discovery & Sightings ─────────────────────────────────────────────────────

@app.get("/api/v1/sightings")
@limiter.limit("1000/hour")
async def list_sightings(
    request: Request,
    hours: int = 24,
    min_severity: str = "MEDIUM",
    org: dict = Depends(get_current_org)
):
    sightings = await get_recent_sightings(org["org_id"], hours, min_severity)
    return {"count": len(sightings), "sightings": sightings}


@app.post("/api/v1/dmca/{sighting_id}")
async def trigger_dmca(sighting_id: str, org: dict = Depends(get_current_org)):
    generate_dmca.delay(sighting_id)
    return {"status": "enqueued", "sighting_id": sighting_id}


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/v1/health")
async def health_check():
    """FIX 6: Real health check with live FAISS, Celery, and DB status."""
    from detection.faiss_index import FAISSIndex
    from celery_app import celery_app as _celery

    faiss_size = 0
    try:
        index = FAISSIndex()
        faiss_size = index.total_vectors
    except Exception:
        faiss_size = -1

    queue_depth = 0
    try:
        inspector = _celery.control.inspect(timeout=1.0)
        active = inspector.active() or {}
        queue_depth = sum(len(v) for v in active.values())
    except Exception:
        queue_depth = -1

    db_ok = False
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "version": "7.1",
        "faiss_index_size": faiss_size,
        "queue_depth": queue_depth,
        "database": "ok" if db_ok else "unreachable"
    }
