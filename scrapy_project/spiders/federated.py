from scrapy_redis.spiders import RedisSpider
from scrapy_project.items import ContentMediaItem

class FederatedOrgSpider(RedisSpider):
    name = "federated"
    redis_key = "vyntra:federated_urls"

    def parse(self, response):
        for img in response.css('img::attr(src)').getall():
            yield ContentMediaItem(
                source_url=response.url,
                media_url=response.urljoin(img),
                platform="federated",
                domain=response.url.split('/')[2]
            )
