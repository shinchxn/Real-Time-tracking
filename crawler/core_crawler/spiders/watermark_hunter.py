import scrapy
from core_crawler.items import IngestedAssetItem

class WatermarkHunterSpider(scrapy.Spider):
    """
    Focused completely on locating and validating Watermarks across massive generic domains.
    Prioritizes deep scanning of entire image assets directly to the pipeline.
    """
    name = "watermark_hunter"

    # In Scrapy-Redis, spiders can listen to a queue
    # redis_key = 'watermark_hunter:start_urls'
    start_urls = ["https://example-image-dump.com"]

    def parse(self, response):
        # Extract images
        for img in response.css('img::attr(src)').getall():
            yield response.follow(img, self.save_media)

        # Follow pagination
        next_page = response.css('a.next-page::attr(href)').get()
        if next_page:
            yield response.follow(next_page, self.parse)

    def save_media(self, response):
        item = IngestedAssetItem()
        item['url'] = response.url
        item['source_platform'] = 'Generic Web'
        item['image_bytes'] = response.body
        # Watermark Extraction Pipeline will implicitly prioritize analyzing this item's bytes
        yield item
