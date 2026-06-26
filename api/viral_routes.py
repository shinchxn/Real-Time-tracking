"""
Viral Spread Routes — Content DNA Apex
Real-time content spread tracking via NetworkX graph
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/viral/{asset_id}")
async def viral_graph(asset_id: str, request: Request):
    """Get viral spread graph metrics for an asset."""
    try:
        sg = request.app.state.spread_graph
        metrics = sg.get_metrics(asset_id)
        if not metrics:
            return JSONResponse({"asset_id": asset_id, "viral_depth": 0,
                                  "viral_width": 0, "platforms": {}, "total_sightings": 0})
        return JSONResponse({"asset_id": asset_id, **metrics})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/viral/{asset_id}/timeline")
async def viral_timeline(asset_id: str, request: Request):
    """Get chronological sighting timeline for an asset."""
    try:
        sg = request.app.state.spread_graph
        graph = sg.graph
        if asset_id not in graph:
            return JSONResponse({"asset_id": asset_id, "timeline": []})
        sightings = [
            {
                "sighting_id": n,
                "platform": graph.nodes[n].get("platform", "unknown"),
                "url": graph.nodes[n].get("url", ""),
                "score": graph.nodes[n].get("score", 0),
                "detected_at": str(graph.nodes[n].get("detected_at", "")),
            }
            for n in graph.successors(asset_id)
            if graph.nodes[n].get("type") == "Sighting"
        ]
        sightings.sort(key=lambda x: x["detected_at"])
        return JSONResponse({"asset_id": asset_id, "timeline": sightings})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/viral/{asset_id}/platforms")
async def viral_platforms(asset_id: str, request: Request):
    """Get per-platform breakdown of sightings."""
    try:
        metrics = request.app.state.spread_graph.get_metrics(asset_id)
        return JSONResponse({
            "asset_id": asset_id,
            "platforms": metrics.get("platforms", {}),
            "total": metrics.get("total_sightings", 0),
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dmca/generate/{sighting_id}")
async def dmca_generate(sighting_id: str, request: Request):
    """Generate DMCA notice HTML for a sighting."""
    try:
        from viral.dmca_generator import DMCAGenerator
        generator = DMCAGenerator()
        # Demo data for prototype
        asset = {"asset_id": "demo", "filename": "asset.png", "dna_hash": "abc123", "ipfs_cid": ""}
        sighting = {"source_url": f"https://example.com/infringing/{sighting_id}",
                    "platform": "web", "detected_at": "2025-01-01T00:00:00Z"}
        org = {"org_name": "Content Owner"}
        html = generator.generate_notice(asset, sighting, org, fusion_score=0.95)
        return JSONResponse({"sighting_id": sighting_id, "dmca_html": html,
                              "status": "generated"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
