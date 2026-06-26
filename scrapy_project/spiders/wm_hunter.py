import scrapy
from scrapy_project.items import ContentMediaItem

class WatermarkHunterSpider(scrapy.Spider):
    name = "wm_hunter"
    
    async def start(self):
        async for url in self.load_targets():
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        for img in response.css('img::attr(src)').getall():
            # Watermark Extract Pipeline will catch this
            yield ContentMediaItem(
                source_url=response.url,
                media_url=response.urljoin(img),
                platform="wm_hunter",
                domain=response.url.split('/')[2]
            )
