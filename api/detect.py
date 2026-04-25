import io
from fastapi import APIRouter, UploadFile, File, Request, HTTPException, Query
from PIL import Image

from detection.detector import detect_pipeline, fetch_and_validate_url

router = APIRouter()

@router.post("/detect")
async def detect(request: Request, file: UploadFile = File(...)):
    """
    Forensic Detection Pipeline (v5.1 Apex)
    Analyzes an uploaded image for DNA matches in the global index.
    """
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        faiss_index = request.app.state.faiss_index
        result = await detect_pipeline(image, faiss_index)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")

@router.post("/check-url")
async def check_url(request: Request, url: str = Query(...)):
    """
    Forensic analysis of a remote asset by URL.
    """
    try:
        image = await fetch_and_validate_url(url)
        faiss_index = request.app.state.faiss_index
        result = await detect_pipeline(image, faiss_index)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"URL Analysis failed: {str(e)}")

@router.get("/asset/{id}")
async def get_asset(id: str):
    return {"status": "ok", "id": id, "metadata": {}}
