"""
Alerts & Stats Routes — Content DNA Apex
Live threat statistics and alert dashboard data
"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/alerts")
async def get_alerts(request: Request):
    """Get current alert summary from FAISS index."""
    faiss_index = request.app.state.faiss_index
    total_assets = faiss_index.total_vectors
    return JSONResponse({
        "total_assets_registered": total_assets,
        "index_trained": faiss_index.is_trained,
        "status": "active",
    })


@router.get("/alerts/stats")
async def get_alerts_stats(request: Request):
    """Get detailed stats for dashboard display."""
    faiss_index = request.app.state.faiss_index
    spread_graph = request.app.state.spread_graph

    graph_node_count = spread_graph.graph.number_of_nodes()
    graph_edge_count = spread_graph.graph.number_of_edges()

    return JSONResponse({
        "registered_assets": faiss_index.total_vectors,
        "faiss_trained": faiss_index.is_trained,
        "spread_graph": {
            "nodes": graph_node_count,
            "edges": graph_edge_count,
        },
        "watermark_methods": ["DCT", "DWT", "LSB", "XMP"],
        "detection_layers": ["CLIP", "pHash", "DCT_freq", "Spatial", "HOG", "Color"],
        "ai_detectors": ["deepfake_laplacian", "diffusion_wavelet_LL3"],
        "model": "openai/clip-vit-base-patch32",
    })
