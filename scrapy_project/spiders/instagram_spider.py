"""
Instagram Sports Spider — Content DNA Apex v6.0
Uses instagrapi for authenticated API-level access (no scraping).
Iterates recent posts from sports hashtags within a 48-hour window.
"""
import io
import logging
from datetime import datetime, timezone, timedelta
from typing import List

import scrapy
from scrapy import signals
from scrapy.exceptions import CloseSpider

from scrapy_project.items import MediaItem

logger = logging.getLogger(__name__)

# Default seed hashtags for sports tracking
DEFAULT_HASHTAGS: List[str] = [
    "sportshighlights",
    "nba",
    "fifa",
    "ipl",
    "nfl",
    "premierleague",
]


class InstagramSportsSpider(scrapy.Spider):
    """
    Authenticated Instagram spider using instagrapi.
    Targets sports hashtags to find recent media posts (last 48 hours).
    Emits MediaItem for every post thumbnail or video frame.

    Usage:
        scrapy crawl instagram_sports -s INSTAGRAM_USERNAME=user -s INSTAGRAM_PASSWORD=pass
        # Or with custom hashtags:
        scrapy crawl instagram_sports -a hashtags="sportshighlights,nba,cricket"
    """
    name = "instagram_sports"
    custom_settings = {
        # Instagram session is managed by instagrapi, not Scrapy downloader
        "DOWNLOAD_HANDLERS": {},
        "HTTPCACHE_ENABLED": False,  # Not applicable for instagrapi
    }

    def __init__(self, hashtags: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        raw_tags = hashtags.strip().split(",") if hashtags.strip() else []
        self.hashtag_list: List[str] = [t.lstrip("#").strip() for t in raw_tags if t.strip()] or DEFAULT_HASHTAGS
        self._client = None

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider._spider_opened, signal=signals.spider_opened)
        return spider

    def _spider_opened(self, spider):
        """Authenticate with Instagram using instagrapi on spider open."""
        try:
            from instagrapi import Client
            from instagrapi.exceptions import LoginRequired, BadPassword
            import os

            username = self.settings.get("INSTAGRAM_USERNAME") or os.getenv("INSTAGRAM_USERNAME", "")
            password = self.settings.get("INSTAGRAM_PASSWORD") or os.getenv("INSTAGRAM_PASSWORD", "")

            if not username or not password:
                logger.error("[Instagram] No credentials set. Set INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD env vars.")
                return

            self._client = Client()

            # Try loading encrypted session from env (Fernet-encrypted JSON)
            enc_session = os.getenv("INSTAGRAM_SESSION_ENC", "")
            if enc_session:
                try:
                    from cryptography.fernet import Fernet
                    fernet_key = os.getenv("FERNET_KEY", "").encode()
                    if fernet_key:
                        f = Fernet(fernet_key)
                        session_json = f.decrypt(enc_session.encode()).decode()
                        self._client.set_settings_from_json(session_json)
                        self._client.get_timeline_feed()  # validate session
                        logger.info("[Instagram] Session loaded from encrypted store.")
                        return
                except Exception as e:
                    logger.warning("[Instagram] Cached session invalid (%s). Re-logging in.", e)

            self._client.login(username, password)
            logger.info("[Instagram] Authenticated as %s", username)

        except ImportError:
            logger.error("[Instagram] instagrapi not installed. Run: pip install instagrapi")
            self._client = None
        except Exception as e:
            logger.error("[Instagram] Login failed: %s", e)
            self._client = None

    def start_requests(self):
        """Entry point — yields dummy requests to trigger Scrapy's machinery."""
        for hashtag in self.hashtag_list:
            yield scrapy.Request(
                url=f"https://www.instagram.com/explore/tags/{hashtag}/",
                callback=self._parse_hashtag,
                cb_kwargs={"hashtag": hashtag},
                dont_filter=True,
                meta={"handle_httpstatus_all": True},  # instagrapi handles auth
            )

    def _parse_hashtag(self, response, hashtag: str):
        """
        Uses instagrapi to fetch recent hashtag posts (last 48h).
        The Scrapy response is ignored — instagrapi makes its own requests.
        """
        if not self._client:
            logger.warning("[Instagram] No authenticated client. Skipping hashtag: #%s", hashtag)
            return

        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

        try:
            # Fetch recent posts for hashtag (up to 50)
            medias = self._client.hashtag_medias_recent(hashtag, amount=50)
        except Exception as e:
            logger.error("[Instagram] Failed to fetch #%s: %s", hashtag, e)
            return

        for media in medias:
            try:
                # Filter by time window
                taken_at = media.taken_at
                if taken_at.tzinfo is None:
                    taken_at = taken_at.replace(tzinfo=timezone.utc)
                if taken_at < cutoff:
                    continue

                # Download thumbnail (or first frame for videos)
                media_bytes = self._download_media_bytes(media)
                if not media_bytes:
                    continue

                yield MediaItem(
                    source_url=f"https://www.instagram.com/p/{media.code}/",
                    platform="instagram",
                    post_id=str(media.pk),
                    author_handle=media.user.username if media.user else "unknown",
                    media_bytes=media_bytes,
                    media_type="video" if media.media_type == 2 else "image",
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    media_url=str(media.thumbnail_url or media.image_url or ""),
                    domain="instagram.com",
                )

            except Exception as e:
                logger.warning("[Instagram] Error processing media %s: %s", getattr(media, "pk", "?"), e)

    def _download_media_bytes(self, media) -> bytes:
        """Download thumbnail or first frame to bytes buffer."""
        import httpx
        try:
            # Prefer thumbnail_url (works for both photos and videos)
            url = str(media.thumbnail_url or media.image_url or "")
            if not url:
                return b""

            response = httpx.get(url, timeout=15.0, follow_redirects=True)
            response.raise_for_status()
            return response.content

        except Exception as e:
            logger.warning("[Instagram] Download failed for media %s: %s",
                           getattr(media, "pk", "?"), e)
            return b""
