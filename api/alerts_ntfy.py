"""
Alerts via ntfy.sh — Content DNA Apex v8.0
Open-source, self-hosted push notifications. Zero cost.
No account needed for the ntfy.sh public server.

Self-host:  docker run -p 80:80 binwiederhier/ntfy
Docs:       https://ntfy.sh
"""
import httpx
import os
import logging

logger = logging.getLogger(__name__)

NTFY_URL = os.getenv("NTFY_URL", "https://ntfy.sh")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "contentdna-alerts")
NTFY_TOKEN = os.getenv("NTFY_TOKEN", "")  # only needed for self-hosted with auth


async def send_alert(
    title: str,
    message: str,
    priority: str = "default",
    tags: list = None,
):
    """
    Send a push notification via ntfy.
    priority: min | low | default | high | urgent
    Subscribe to alerts by installing the ntfy app and subscribing to NTFY_TOPIC.
    """
    headers = {
        "Title": title,
        "Priority": priority,
        "Tags": ",".join(tags or ["warning"]),
    }
    if NTFY_TOKEN:
        headers["Authorization"] = f"Bearer {NTFY_TOKEN}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{NTFY_URL}/{NTFY_TOPIC}",
                content=message,
                headers=headers,
            )
        logger.info("ntfy alert sent: %s", title)
    except Exception as e:
        logger.warning("ntfy alert failed (non-critical): %s", e)


async def send_violation_alert(
    asset_id: str,
    source_url: str,
    score: float,
    severity: str,
):
    """
    Send a pre-formatted violation alert for a detected content match.
    Severity maps to ntfy priority levels.
    """
    priority_map = {
        "CRITICAL": "urgent",
        "HIGH": "high",
        "MEDIUM": "default",
        "WATCH": "low",
    }
    tags = [
        "rotating_light" if severity == "CRITICAL" else "warning",
        "content-dna",
    ]
    await send_alert(
        title=f"[{severity}] Content violation detected",
        message=(
            f"Asset: {asset_id}\n"
            f"URL:   {source_url}\n"
            f"Score: {score:.3f}"
        ),
        priority=priority_map.get(severity, "default"),
        tags=tags,
    )
