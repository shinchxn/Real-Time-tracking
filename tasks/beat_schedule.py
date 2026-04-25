"""
Celery Beat Schedule + BroadcastWindowManager — Content DNA Apex v6.0
Configures periodic crawl tasks and dynamically adjusts intervals
during active sports broadcast windows.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from celery.schedules import crontab
from tasks.celery_app import app

logger = logging.getLogger(__name__)

# ── Default seed configuration ────────────────────────────────────────────────

HASHTAG_LIST = [
    "sportshighlights", "nba", "fifa", "ipl",
    "nfl", "premierleague", "cricket", "uefaliga",
]

GOOGLE_ALERT_FEEDS = os.getenv("GOOGLE_ALERT_FEEDS", "").split(",")

# ── Static Beat Schedule ──────────────────────────────────────────────────────

app.conf.beat_schedule = {
    # Instagram sweep: every 2 hours
    "instagram-sweep-2h": {
        "task": "tasks.beat_schedule.crawl_platform",
        "schedule": crontab(minute=0, hour="*/2"),
        "args": ["instagram", HASHTAG_LIST],
        "options": {"queue": "crawl"},
    },
    # Google Alert RSS sweep: every 6 hours
    "google-alert-sweep-6h": {
        "task": "tasks.beat_schedule.crawl_platform",
        "schedule": crontab(minute=30, hour="*/6"),
        "args": ["web", GOOGLE_ALERT_FEEDS],
        "options": {"queue": "crawl"},
    },
    # Full deep rescan: every 24 hours (3 AM UTC)
    "deep-rescan-24h": {
        "task": "tasks.beat_schedule.run_deep_rescan_sweep",
        "schedule": crontab(minute=0, hour=3),
        "options": {"queue": "rescan"},
    },
    # Broadcast window check: every 15 minutes (adjusts crawl intervals)
    "broadcast-window-check-15m": {
        "task": "tasks.beat_schedule.check_broadcast_windows",
        "schedule": crontab(minute="*/15"),
        "options": {"queue": "crawl"},
    },
}


# ── Celery Tasks (Beat-triggered) ─────────────────────────────────────────────

@app.task(name="tasks.beat_schedule.crawl_platform")
def crawl_platform(platform: str, seed_keywords: List[str]) -> Dict:
    """
    Triggers the appropriate Scrapy spider for a scheduled platform sweep.
    Uses CrawlerRunner in a subprocess to avoid Twisted reactor conflicts.
    """
    import subprocess
    import sys

    logger.info("[Beat] Crawl triggered: platform=%s keywords=%d", platform, len(seed_keywords))

    spider_map = {
        "instagram": "instagram_sports",
        "web": "google_alert",
    }
    spider_name = spider_map.get(platform)
    if not spider_name:
        logger.warning("[Beat] Unknown platform: %s", platform)
        return {"status": "unknown_platform", "platform": platform}

    # Build spider arguments
    args = [sys.executable, "-m", "scrapy", "crawl", spider_name]
    if platform == "instagram" and seed_keywords:
        args += ["-a", f"hashtags={','.join(seed_keywords)}"]
    elif platform == "web" and seed_keywords:
        args += ["-a", f"feeds={','.join(seed_keywords)}"]

    try:
        result = subprocess.Popen(
            args,
            cwd=os.getcwd(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("[Beat] Spider %s launched (PID=%d)", spider_name, result.pid)
        return {"status": "launched", "platform": platform, "spider": spider_name, "pid": result.pid}
    except Exception as e:
        logger.error("[Beat] Failed to launch spider %s: %s", spider_name, e)
        return {"status": "error", "error": str(e)}


@app.task(name="tasks.beat_schedule.run_deep_rescan_sweep")
def run_deep_rescan_sweep() -> Dict:
    """
    Queues deep_rescan tasks for all assets with HIGH/CRITICAL sightings in the past week.
    """
    import asyncio
    from storage.db_client import get_high_severity_assets_for_rescan
    from tasks.fingerprint_tasks import deep_rescan

    try:
        asset_ids = asyncio.run(get_high_severity_assets_for_rescan(hours=168))
        logger.info("[Beat] Deep rescan sweep: %d assets queued", len(asset_ids))
        for asset_id in asset_ids:
            deep_rescan.apply_async(args=[asset_id], queue="rescan")
        return {"status": "queued", "count": len(asset_ids)}
    except Exception as e:
        logger.error("[Beat] Deep rescan sweep failed: %s", e)
        return {"status": "error", "error": str(e)}


@app.task(name="tasks.beat_schedule.check_broadcast_windows")
def check_broadcast_windows() -> Dict:
    """
    Reads active broadcast windows from DB and triggers high-frequency crawls
    (every 15 minutes) for currently live events.
    """
    manager = BroadcastWindowManager()
    active = manager.get_active_windows_sync()

    if not active:
        return {"status": "no_active_windows"}

    triggered = []
    for window in active:
        meta = window.get("metadata", {})
        league = meta.get("league", "unknown")
        # Derive hashtags from league/event
        hashtags = _league_to_hashtags(league, meta)
        logger.info("[BroadcastWindow] LIVE: %s — triggering 15-min sweep", league)
        crawl_platform.apply_async(args=["instagram", hashtags], queue="crawl")
        triggered.append(league)

    return {"status": "triggered", "active_windows": triggered}


def _league_to_hashtags(league: str, meta: Dict) -> List[str]:
    """Map league name to crawl hashtags."""
    base_map = {
        "IPL": ["ipl", "iplt20", "cricket"],
        "NBA": ["nba", "basketball", "nbahighlights"],
        "NFL": ["nfl", "football", "nflhighlights"],
        "FIFA": ["fifa", "football", "fifaworldcup"],
        "Premier League": ["premierleague", "epl", "football"],
        "UEFA": ["uefaliga", "championsleague", "football"],
    }
    for key, tags in base_map.items():
        if key.lower() in league.lower():
            return tags
    return ["sportshighlights"]  # fallback


# ── BroadcastWindowManager ────────────────────────────────────────────────────

class BroadcastWindowManager:
    """
    Reads upcoming/active broadcast windows from the DB and provides
    dynamic schedule management for Celery Beat.

    A "broadcast window" is stored in registered_assets.metadata JSONB:
    {
        "broadcast_window": "2025-04-20T14:00:00Z / 2025-04-20T18:30:00Z",
        "embargo_until": "2025-04-21T00:00:00Z",
        "league": "IPL"
    }
    """

    def get_active_windows_sync(self) -> List[Dict]:
        """Synchronously fetch currently active broadcast windows."""
        import asyncio
        try:
            return asyncio.run(self._get_active_windows_async())
        except Exception as e:
            logger.error("[BroadcastWindowManager] Failed to fetch windows: %s", e)
            return []

    async def _get_active_windows_async(self) -> List[Dict]:
        from storage.db_client import get_upcoming_broadcast_windows
        now = datetime.now(timezone.utc)
        all_windows = await get_upcoming_broadcast_windows()
        active = []
        for window in all_windows:
            meta = window.get("metadata", {})
            bw_str = meta.get("broadcast_window", "")
            if not bw_str:
                continue
            try:
                start_str, end_str = bw_str.split(" / ")
                start = datetime.fromisoformat(start_str.rstrip("Z")).replace(tzinfo=timezone.utc)
                end = datetime.fromisoformat(end_str.rstrip("Z")).replace(tzinfo=timezone.utc)
                if start <= now <= end:
                    active.append(window)
            except (ValueError, AttributeError):
                continue
        return active

    @staticmethod
    def is_within_embargo(embargo_until_str: Optional[str]) -> bool:
        """Check if current time is within an embargo window."""
        if not embargo_until_str:
            return False
        try:
            embargo = datetime.fromisoformat(embargo_until_str.rstrip("Z")).replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) < embargo
        except (ValueError, AttributeError):
            return False
