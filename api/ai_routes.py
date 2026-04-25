from fastapi import APIRouter
router = APIRouter()

@router.post("/ai/detect-generated")
async def detect_generated(): return {"status": "ok"}
@router.post("/ai/detect-manipulation")
async def detect_manipulation(): return {"status": "ok"}
@router.post("/ai/detect-clone")
async def detect_clone(): return {"status": "ok"}
