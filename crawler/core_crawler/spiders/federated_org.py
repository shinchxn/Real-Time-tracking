import scrapy
from scrapy_redis.spiders import RedisSpider
from core_crawler.items import IngestedAssetItem

class FederatedOrgSpider(RedisSpider):
    """
    Distributed Scrapy-Redis Spider for Org Tracking.
    Lets multiple rights-holder organizations share a single Redis queue
    without sharing their assets. Built for multi-tenant SaaS scaling.
    """
    name = "federated_org"
    redis_key = "federated_org:start_urls"
    
    # Message format in Redis: '{"url":"http://...", "meta":{"owner_id":"org-1"}}'

    def make_request_from_data(self, data):
        """Override to parse JSON jobs from Redis Queue containing tenant info."""
        import json
        payload = json.loads(data)
        url = payload.get('url')
        meta = payload.get('meta', {})
        return scrapy.Request(url, meta=meta, dont_filter=True, callback=self.parse)

    def parse(self, response):
        for img in response.css('img::attr(src)').getall():
            yield response.follow(img, meta=response.meta, callback=self.save_media)

    def save_media(self, response):
        item = IngestedAssetItem()
        item['url'] = response.url
        item['source_platform'] = 'Federated Network'
        item['image_bytes'] = response.body
        # Ensure tenant isolation via owner_id
        item['owner_id'] = response.meta.get('owner_id', 'unknown_org')
        yield item
