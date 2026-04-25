"""
Google Alert RSS Spider — Content DNA Apex v6.0
Polls configurable Google Alert RSS feeds, follows linked pages,
extracts all <img> and <video> tags, and emits MediaItem for each.
"""
import io
import logging
from datetime import datetime, timezone
from typing import List
from urllib.parse import urlparse

import scrapy

from scrapy_project.items import MediaItem

logger = logging.getLogger(__name__)

# Default Google Alert RSS feeds (replace with org-specific alert URLs)
# Format: https://www.google.com/alerts/feeds/{USER_ID}/{ALERT_ID}
DEFAULT_ALERT_FEEDS: List[str] = []


class GoogleAlertSpider(scrapy.Spider):
    """
    Polls Google Alert RSS feeds to discover sports content being shared.
    For each alert entry, visits the linked page and extracts all media.
    Emits MediaItem for each discovered image or video.

    Usage:
        scrapy crawl google_alert -a feeds="https://google.com/alerts/feeds/xxx/yyy,..."
    """
    name = "google_alert"
    custom_settings = {
        "HTTPCACHE_ENABLED": True,
        "HTTPCACHE_EXPIRATION_SECS": 3600,  # Cache RSS for 1h (faster than 24h for news)
    }

    def __init__(self, feeds: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        raw_feeds = feeds.strip().split(",") if feeds.strip() else []
        self.feed_urls: List[str] = [f.strip() for f in raw_feeds if f.strip()] or DEFAULT_ALERT_FEEDS

        if not self.feed_urls:
            logger.warning("[GoogleAlert] No RSS feed URLs configured. "
                           "Set GOOGLE_ALERT_FEEDS env var or pass -a feeds=... argument.")

    def start_requests(self):
        for feed_url in self.feed_urls:
            yield scrapy.Request(
                url=feed_url,
                callback=self._parse_rss,
                headers={"Accept": "application/rss+xml, application/atom+xml, text/xml, */*"},
                meta={"feed_url": feed_url},
            )

    def _parse_rss(self, response):
        """Parse RSS/Atom feed using feedparser, follow each article link."""
        try:
            import feedparser
        except ImportError:
            logger.error("[GoogleAlert] feedparser not installed. Run: pip install feedparser")
            return

        feed = feedparser.parse(response.text)
        logger.info("[GoogleAlert] Feed: %s — %d entries", response.url, len(feed.entries))

        for entry in feed.entries:
            link = entry.get("link", "")
            if not link:
                continue

            yield scrapy.Request(
                url=link,
                callback=self._parse_article,
                meta={
                    "feed_url": response.url,
                    "entry_title": entry.get("title", ""),
                    "published": entry.get("published", ""),
                },
                errback=self._handle_error,
            )

    def _parse_article(self, response):
        """Visit linked article page and extract all media URLs."""
        page_domain = urlparse(response.url).netloc
        detected_at = datetime.now(timezone.utc).isoformat()

        # Extract <img> tags
        for img_url in response.css("img::attr(src), img::attr(data-src), img::attr(data-lazy-src)").getall():
            abs_url = response.urljoin(img_url)
            if not self._is_valid_media_url(abs_url):
                continue

            yield scrapy.Request(
                url=abs_url,
                callback=self._download_image,
                meta={
                    "source_url": response.url,
                    "platform": "web",
                    "domain": page_domain,
                    "media_type": "image",
                    "detected_at": detected_at,
                },
                errback=self._handle_error,
            )

        # Extract <video> and <source> tags
        for vid_url in response.css("video::attr(src), video source::attr(src), "
                                     "source[type*='video']::attr(src)").getall():
            abs_url = response.urljoin(vid_url)
            if not self._is_valid_media_url(abs_url):
                continue

            yield MediaItem(
                source_url=response.url,
                platform="web",
                post_id=abs_url,  # Use URL as post ID for web content
                author_handle=page_domain,
                media_bytes=b"",  # Will be populated by VideoFrameSampler in Celery task
                media_type="video",
                detected_at=detected_at,
                media_url=abs_url,
                domain=page_domain,
            )

    def _download_image(self, response):
        """Download image bytes and emit MediaItem."""
        content_type = response.headers.get("Content-Type", b"").decode("utf-8", errors="ignore")
        if "image" not in content_type and "octet-stream" not in content_type:
            return

        yield MediaItem(
            source_url=response.meta["source_url"],
            platform=response.meta["platform"],
            post_id=response.url,
            author_handle=response.meta["domain"],
            media_bytes=response.body,
            media_type=response.meta["media_type"],
            detected_at=response.meta["detected_at"],
            media_url=response.url,
            domain=response.meta["domain"],
        )

    def _handle_error(self, failure):
        logger.warning("[GoogleAlert] Request failed: %s — %s", failure.request.url, failure.value)

    @staticmethod
    def _is_valid_media_url(url: str) -> bool:
        """Filter out tracking pixels, icons, and SVGs."""
        lower = url.lower()
        skip_ext = (".svg", ".ico", ".gif", ".webp")
        if any(lower.endswith(ext) for ext in skip_ext):
            return False
        if "1x1" in lower or "pixel" in lower or "tracking" in lower:
            return False
        parsed = urlparse(url)
        return bool(parsed.scheme in ("http", "https") and parsed.netloc)
