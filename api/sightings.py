"""
Sightings API Route — Content DNA Apex v6.0
GET /api/v1/sightings — retrieve recent detections for an org.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request, Security
from fastapi.responses import JSONResponse
from typing import List, Optional

from auth.api_key import get_current_org
from auth.rate_limiter import limiter, LIMIT_SIGHTINGS
from storage.db_client import get_recent_sightings

router = APIRouter(prefix="/api/v1")


@router.get("/sightings")
@limiter.limit(LIMIT_SIGHTINGS)
async def list_sightings(
    request: Request,
    hours: int = Query(default=24, ge=1, le=720, description="Lookback window in hours"),
    severity: Optional[str] = Query(
        default="MEDIUM",
        description="Minimum severity filter: CRITICAL | HIGH | MEDIUM | LOW"
    ),
    org: dict = Security(get_current_org),
) -> JSONResponse:
    """
    Retrieve recent content sightings for the authenticated organization.

    Query params:
      - hours: lookback window (1–720h, default 24h)
      - severity: minimum severity threshold (default MEDIUM)

    Returns 200 with list of sighting objects.
    """
    valid_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "MISS"}
    if severity and severity.upper() not in valid_severities:
        return JSONResponse(status_code=400, content={"error": f"Invalid severity: {severity}"})

    sightings = await get_recent_sightings(
        org_id=org["org_id"],
        hours=hours,
        min_severity=(severity or "MEDIUM").upper(),
    )

    return JSONResponse(content={
        "org_id": org["org_id"],
        "hours": hours,
        "min_severity": severity,
        "count": len(sightings),
        "sightings": sightings,
    })
