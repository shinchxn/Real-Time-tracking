"""
Storage Pipeline — Content DNA Apex v6.0
Routes confirmed sightings to Celery for async DB writes.
Replaces the blocking loop.run_until_complete() pattern.
"""
import logging

logger = logging.getLogger(__name__)


class StoragePipeline:
    """
    Persists ViolationItems to PostgreSQL via Celery async task.
    Only items that have passed the detection pipeline (have severity set)
    are stored. Items below threshold are silently dropped.
    """

    def process_item(self, item, spider):
        severity = item.get("severity")
        asset_id = item.get("asset_id")

        if not severity or severity == "MISS" or not asset_id:
            # No confirmed match — nothing to store
            return item

        try:
            from tasks.fingerprint_tasks import persist_sighting
            persist_sighting.delay(
                asset_id=str(asset_id),
                platform=item.get("platform", "unknown"),
                source_url=item.get("source_url", ""),
                author_handle=item.get("author_handle", ""),
                fusion_score=float(item.get("fusion_score", 0.0)),
                severity=severity,
                layer_scores=item.get("layer_scores") or {},
                post_id=item.get("post_id", ""),
            )
            logger.info("[StoragePipeline] Queued sighting persist: %s [%s] %.3f",
                        item.get("source_url", "")[:60], severity, item.get("fusion_score", 0.0))
        except Exception as e:
            logger.error("[StoragePipeline] Failed to queue persist task: %s", e)

        return item
