from fastapi import APIRouter
from fastapi.responses import HTMLResponse
router = APIRouter()

@router.post("/webhooks/inbound/{partner_id}")
async def inbound_webhook(partner_id: str): return {"status": "ok"}
@router.post("/webhooks/outbound/register")
async def outbound_register(): return {"status": "ok"}
@router.post("/partners/register")
async def partners_register(): return {"status": "ok"}
@router.get("/partners/{id}/stats")
async def partners_stats(id: str): return {"status": "ok"}
@router.post("/webhooks/register")
async def webhooks_register(): return {"status": "ok"}
@router.get("/webhooks")
async def webhooks_list(): return {"status": "ok"}
