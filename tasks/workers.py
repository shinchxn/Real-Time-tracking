from tasks.celery_app import app
import httpx
from config import settings

@app.task(bind=True, max_retries=3)
def process_critical_alert(self, violation_id: str, payload: dict):
    """
    Handles CRITICAL severities: webhook, DMCA generation, Slack alert.
    """
    try:
        if settings.ALERT_WEBHOOK_URL:
            httpx.post(settings.ALERT_WEBHOOK_URL, json=payload, timeout=5.0)
            
        if settings.DMCA_AUTOMATION_ENABLED:
            from viral.dmca_generator import DMCAEvidenceGenerator
            gen = DMCAEvidenceGenerator("./data/dmca")
            gen.generate_package(violation_id, {"owner_id": "system"}, payload, {}, {})
            
    except Exception as exc:
        raise self.retry(exc=exc)

@app.task
def background_crawl_task(url: str):
    """Trigger scrapy remotely"""
    pass
