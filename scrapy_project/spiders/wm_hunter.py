import scrapy
from scrapy_project.items import ContentMediaItem

class WatermarkHunterSpider(scrapy.Spider):
    name = "wm_hunter"
    
    def start_requests(self):
        yield scrapy.Request('http://example.com/gallery', self.parse)

    def parse(self, response):
        for img in response.css('img::attr(src)').getall():
            # Watermark Extract Pipeline will catch this
            yield ContentMediaItem(
                source_url=response.url,
                media_url=response.urljoin(img),
                platform="wm_hunter",
                domain=response.url.split('/')[2]
            )
