"""
Detection Pipeline — Content DNA Apex v6.0
Bridges Scrapy items to Celery tasks for non-blocking fingerprint processing.
Replaces the blocking loop.run_until_complete() pattern.
"""
import logging

from scrapy.exceptions import DropItem

logger = logging.getLogger(__name__)


class DetectionPipeline:
    """
    Dispatches MediaItem fingerprinting to Celery workers asynchronously.
    This decouples crawl speed from processing speed entirely.

    The actual detection logic runs in tasks.fingerprint_tasks.fingerprint_and_match
    which: extracts 6-layer DNA → FAISS search → fusion score → DB log.
    """

    def process_item(self, item, spider):
        # Skip if already cache-hit deduped or no media bytes
        if item.get("cache_hit"):
            return item

        media_bytes = item.get("media_bytes", b"")
        source_url = item.get("source_url", "")
        platform = item.get("platform", "unknown")
        media_url = item.get("media_url", "")

        # For video items (bytes not downloaded inline), dispatch via media_url
        if not media_bytes and media_url and item.get("media_type") == "video":
            try:
                from tasks.fingerprint_tasks import process_video_url
                process_video_url.delay(media_url, source_url, platform)
                logger.debug("[DetectionPipeline] Queued video task: %s", media_url[:80])
            except Exception as e:
                logger.warning("[DetectionPipeline] Failed to queue video task: %s", e)
            return item

        if not media_bytes:
            raise DropItem(f"No media_bytes in item from {source_url}")

        # Fire-and-forget: Celery handles all blocking I/O
        try:
            from tasks.fingerprint_tasks import fingerprint_and_match
            fingerprint_and_match.delay(
                bytes(media_bytes),
                source_url,
                platform,
                author_handle=item.get("author_handle", ""),
                post_id=item.get("post_id", ""),
            )
            logger.debug("[DetectionPipeline] Queued fingerprint task: %s", source_url[:80])
        except Exception as e:
            logger.error("[DetectionPipeline] Failed to queue Celery task: %s", e)

        return item
