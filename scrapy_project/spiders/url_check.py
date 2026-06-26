import scrapy
from scrapy_project.items import ContentMediaItem

class URLCheckSpider(scrapy.Spider):
    name = "url_check"
    
    def __init__(self, target_url=None, *args, **kwargs):
        super(URLCheckSpider, self).__init__(*args, **kwargs)
        self.target_url = target_url

    async def start(self):
        async for url in self.load_targets():
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        for img in response.css('img::attr(src)').getall():
            yield ContentMediaItem(
                source_url=response.url,
                media_url=response.urljoin(img),
                platform="url_check",
                domain=response.url.split('/')[2]
            )
