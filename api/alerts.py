"""
GET /alerts — Paginated violations log.
GET /asset/{id} — Retrieve full asset record.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class ViolationRecord(BaseModel):
    id: str
    asset_id: str
    source: str
    fusion_score: float
    severity: str
    clip_score: float
    phash_dist: int
    transform: str
    detected_at: str


class AlertsResponse(BaseModel):
    total: int
    violations: List[ViolationRecord]


class AssetRecord(BaseModel):
    id: str
    owner_id: str
    title: str
    file_path: str
    phash: str
    dhash: str
    ahash: str
    watermarked: bool
    created_at: str


def _get_deps():
    from main import app_state
    return app_state["faiss_index"], app_state["supabase"]


@router.get("/alerts", response_model=AlertsResponse)
async def get_alerts(
    severity: Optional[str] = Query(None, description="Filter: CRITICAL, HIGH, MEDIUM"),
    owner_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Paginated violations log, filterable by severity / owner / date."""
    _, supabase = _get_deps()

    try:
        rows = await supabase.list_violations(
            severity=severity,
            owner_id=owner_id,
            limit=limit,
            offset=offset,
        )

        violations = []
        for r in rows:
            violations.append(ViolationRecord(
                id=str(r.get("id", "")),
                asset_id=str(r.get("asset_id", "")),
                source=str(r.get("source", "")),
                fusion_score=float(r.get("fusion_score", 0)),
                severity=str(r.get("severity", "")),
                clip_score=float(r.get("clip_score", 0)),
                phash_dist=int(r.get("phash_dist", 0)),
                transform=str(r.get("transform", "")),
                detected_at=str(r.get("detected_at", "")),
            ))

        return AlertsResponse(total=len(violations), violations=violations)

    except Exception as exc:
        logger.exception("Failed to retrieve alerts")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/asset/{asset_id}", response_model=AssetRecord)
async def get_asset(asset_id: str):
    """Retrieve full asset record including all stored fingerprints."""
    _, supabase = _get_deps()

    try:
        asset = await supabase.get_asset(asset_id)
        if asset is None:
            raise HTTPException(status_code=404, detail=f"Asset {asset_id} not found")

        return AssetRecord(
            id=str(asset.get("id", "")),
            owner_id=str(asset.get("owner_id", "")),
            title=str(asset.get("title", "")),
            file_path=str(asset.get("file_path", "")),
            phash=str(asset.get("phash", "")),
            dhash=str(asset.get("dhash", "")),
            ahash=str(asset.get("ahash", "")),
            watermarked=bool(asset.get("watermarked", False)),
            created_at=str(asset.get("created_at", "")),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to retrieve asset")
        raise HTTPException(status_code=500, detail=str(exc))
