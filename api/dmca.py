"""
DMCA API Route — Content DNA Apex v6.0
POST /api/v1/dmca/{sighting_id} — trigger DMCA package generation.
"""
from __future__ import annotations

from fastapi import APIRouter, Path, Request, Security
from fastapi.responses import JSONResponse

from auth.api_key import get_current_org
from auth.rate_limiter import limiter, LIMIT_DMCA

router = APIRouter(prefix="/api/v1")


@router.post("/dmca/{sighting_id}")
@limiter.limit(LIMIT_DMCA)
async def trigger_dmca(
    request: Request,
    sighting_id: str = Path(..., description="UUID of the confirmed sighting"),
    org: dict = Security(get_current_org),
) -> JSONResponse:
    """
    Trigger DMCA evidence bundle generation for a confirmed sighting.

    Queues a Celery task that:
      1. Generates a forensic evidence report (Markdown/PDF)
      2. Saves it to the evidence store
      3. Updates the sighting record (dmca_generated=TRUE, evidence_path)

    Returns 202 Accepted immediately — check sighting record for completion.
    """
    try:
        from tasks.fingerprint_tasks import generate_dmca
        task = generate_dmca.apply_async(args=[sighting_id], queue="dmca")
        return JSONResponse(
            status_code=202,
            content={
                "status": "queued",
                "sighting_id": sighting_id,
                "task_id": task.id,
                "message": "DMCA bundle generation queued. Check sighting record for evidence_path.",
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to queue DMCA task", "detail": str(e)},
        )
