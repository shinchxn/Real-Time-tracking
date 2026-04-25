"""
Scrapy Items — Content DNA Apex v6.0
Defines all item types emitted by platform spiders.
"""
import scrapy
from datetime import datetime, timezone


class MediaItem(scrapy.Item):
    """Primary item emitted by all v6.0 platform spiders."""
    source_url   = scrapy.Field()   # Full URL where media was found
    platform     = scrapy.Field()   # 'instagram' | 'web' | 'google_alert' | 'video'
    post_id      = scrapy.Field()   # Platform-native post/media ID (str)
    author_handle = scrapy.Field()  # @username or page name
    media_bytes  = scrapy.Field()   # Raw image bytes (bytes) for fingerprinting
    media_type   = scrapy.Field()   # 'image' | 'video' | 'thumbnail'
    detected_at  = scrapy.Field()   # ISO-8601 timestamp (str)
    # Optional enrichment fields
    media_url    = scrapy.Field()   # CDN/direct URL to the raw media file
    domain       = scrapy.Field()   # Apex domain of source


class ContentMediaItem(scrapy.Item):
    """Legacy item — kept for backward compatibility with existing pipelines."""
    source_url  = scrapy.Field()
    platform    = scrapy.Field()
    media_url   = scrapy.Field()
    media_type  = scrapy.Field()
    domain      = scrapy.Field()
    dna         = scrapy.Field()   # dict of 6 layers
    local_path  = scrapy.Field()


class ViolationItem(scrapy.Item):
    """Emitted by detection pipeline when a match is confirmed."""
    source_url      = scrapy.Field()
    platform        = scrapy.Field()
    asset_id        = scrapy.Field()
    fusion_score    = scrapy.Field()
    severity        = scrapy.Field()
    watermark_hits  = scrapy.Field()  # list of channels missing/found
    extracted_wm    = scrapy.Field()
    layer_scores    = scrapy.Field()  # JSONB-ready dict per-layer breakdown
    author_handle   = scrapy.Field()
    post_id         = scrapy.Field()
