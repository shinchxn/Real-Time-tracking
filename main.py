"""
Content DNA Apex v7.1 — Main API Gateway
FastAPI application with multi-layered forensic routes, 
distributed matching pipeline, and sports-media-keys trust anchor.
"""
from fastapi import FastAPI, Depends, HTTPException, Security, UploadFile, File
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from auth.api_key import get_current_org, Organization
from auth.rate_limiter import limiter, RateLimitExceeded, _rate_limit_exceeded_handler
from storage.db_client import get_pool, close_pool, get_recent_sightings, get_custody_chain
from tasks import fingerprint_and_match, generate_dmca

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB pool
    await get_pool()
    yield
    # Shutdown: Close DB pool
    await close_pool()

app = FastAPI(
    title="Content DNA Apex",
    version="7.1",
    lifespan=lifespan
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
    request: Request, # required for limiter
    org: Organization = Depends(get_current_org),
    file: UploadFile = File(...)
):
    """
    Upload → to_sdna() [embed layers] → register_asset() → run_dork_sweep.delay()
    """
    # ... Implementation ...
    return {"asset_id": "...", "sdna_url": "..."}

@app.post("/api/v1/assets/verify")
async def verify_asset(file: UploadFile = File(...)):
    """Verify any .sdna or image file."""
    from crypto.asset_verifier import AssetVerifier
    # ...
    return {"valid": True, "owner": "...", "proof_chain": ["..."]}

@app.get("/api/v1/assets/{asset_id}/custody")
async def get_custody(asset_id: str, org: Organization = Depends(get_current_org)):
    chain = await get_custody_chain(asset_id)
    return {"asset_id": asset_id, "chain": chain}

# ── Discovery & Sightings ─────────────────────────────────────────────────────

@app.get("/api/v1/sightings")
@limiter.limit("1000/hour")
async def list_sightings(
    request: Request,
    hours: int = 24,
    min_severity: str = "MEDIUM",
    org: Organization = Depends(get_current_org)
):
    sightings = await get_recent_sightings(org.org_id, hours, min_severity)
    return {"count": len(sightings), "sightings": sightings}

@app.post("/api/v1/dmca/{sighting_id}")
async def trigger_dmca(sighting_id: str, org: Organization = Depends(get_current_org)):
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
