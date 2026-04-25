from fastapi import APIRouter
router = APIRouter()

@router.get("/alerts")
async def get_alerts(): return {"status": "ok"}
@router.get("/alerts/stats")
async def get_alerts_stats(): return {"status": "ok"}
