import scrapy
from scrapy_project.items import ContentMediaItem

class PlaywrightSocialSpider(scrapy.Spider):
    name = "social_playwright"
    
    async def start(self):
        async for url in self.load_targets():
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        for img in response.css('img::attr(src)').getall():
            yield ContentMediaItem(
                source_url=response.url,
                media_url=response.urljoin(img),
                platform="social_spa",
                domain="example.com"
            )
