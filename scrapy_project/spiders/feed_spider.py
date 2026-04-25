from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor
from scrapy_project.items import ContentMediaItem

class FeedSpider(CrawlSpider):
    name = "feed_spider"
    start_urls = ['http://example.com/rss']
    
    rules = (
        Rule(LinkExtractor(allow=r'items/'), callback='parse_item', follow=True),
    )

    def parse_item(self, response):
        for img in response.css('img::attr(src)').getall():
            yield ContentMediaItem(
                source_url=response.url,
                media_url=response.urljoin(img),
                platform="feed",
                domain=response.url.split('/')[2]
            )
