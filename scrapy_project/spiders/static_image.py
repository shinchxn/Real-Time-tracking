import scrapy
from scrapy_project.items import ContentMediaItem

class StaticImageSpider(scrapy.Spider):
    name = "static_image"
    
    def start_requests(self):
        yield scrapy.Request('http://example.com', self.parse)

    def parse(self, response):
        for img in response.css('img::attr(src)').getall():
            url = response.urljoin(img)
            yield ContentMediaItem(
                source_url=response.url,
                media_url=url,
                platform="static",
                domain=response.url.split('/')[2]
            )
