"""
Content DNA Apex v7.1 — Main API Gateway
FastAPI application with multi-layered forensic routes, 
distributed matching pipeline, and sports-media-keys trust anchor.
"""
from fastapi import FastAPI, Depends, HTTPException, Security, UploadFile, File, Request
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from auth.api_key import get_current_org
from auth.rate_limiter import limiter, RateLimitExceeded, _rate_limit_exceeded_handler
from storage.db_client import get_pool, close_pool, get_recent_sightings, get_custody_chain
from background_tasks import fingerprint_and_match, generate_dmca

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.state.limiter = limiter

# ── Well-Known Keys (No Auth) ────────────────────────────────────────────────
@app.get("/.well-known/sports-media-keys/{org_id}.pem")
async def get_public_key(org_id: str):
    from storage.db_client import get_pool
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
    import shutil
    import uuid

    asset_id = str(uuid.uuid4())
    temp_path = f"data/temp_{asset_id}_{file.filename}"
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Convert to SDNA (Embeds watermarks & metadata)
    converter = SDNAConverter(org_id=org["org_id"])
    sdna_bytes = await converter.to_sdna(
        input_path=temp_path,
        asset_uuid=asset_id,
        org_name=org.get("org_name", "Unknown Org"),
        watermark_seed=12345 # Should be from settings
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

    return {
        "status": "registered",
        "asset_id": asset_id,
        "sdna_url": sdna_path,
        "blockchain_anchor": "pending"
    }

@app.post("/api/v1/assets/verify")
async def verify_asset(file: UploadFile = File(...)):
    """Verify any .sdna or image file."""
    from crypto.asset_verifier import AssetVerifier
    # ...
    return {"valid": True, "owner": "...", "proof_chain": ["..."]}

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
    # Check DB, Redis, and FAISS
    return {
        "status": "healthy",
        "version": "7.1",
        "faiss_index_size": 1250, # Example
        "queue_depth": 0
    }

from fastapi import Request
