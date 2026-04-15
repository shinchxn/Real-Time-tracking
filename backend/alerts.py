"""
Alerts Module: Handle real-time notifications via webhooks
"""
import httpx
import logging
import asyncio
from typing import Dict, Any
from config import settings

logger = logging.getLogger(__name__)

class AlertManager:
    """Manage real-time alerts and notifications"""
    
    def __init__(self):
        self.enabled = settings.ALERT_ENABLED
        self.webhook_url = settings.ALERT_WEBHOOK
        
        if self.enabled and not self.webhook_url:
            logger.warning("Alerts are enabled but ALERT_WEBHOOK is not set.")
            self.enabled = False

    async def send_alert(self, alert_data: Dict[str, Any]):
        """
        Send alert to configured webhook
        
        Args:
            alert_data: Dictionary containing alert details
        """
        if not self.enabled:
            return

        payload = {
            "text": f"🚨 *{alert_data['severity'].upper()} ALERT: Unauthorized Asset Use Detected*",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Digital Asset Protection Alert"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Severity:* {alert_data['severity'].upper()}\n"
                                f"*Message:* {alert_data['message']}\n"
                                f"*Asset ID:* {alert_data['asset_id']}\n"
                                f"*Matched Asset:* {alert_data['matched_asset_id']}\n"
                                f"*Similarity:* {alert_data['similarity_score']:.1%}"
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Timestamp: {alert_data['timestamp']}"
                        }
                    ]
                }
            ]
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.webhook_url, json=payload, timeout=5.0)
                if response.status_code >= 400:
                    logger.error(f"Failed to send webhook alert: {response.status_code} - {response.text}")
                else:
                    logger.info(f"Webhook alert sent successfully (ID: {alert_data['alert_id']})")
        except Exception as e:
            logger.error(f"Error sending webhook alert: {e}")

alert_manager = AlertManager()
