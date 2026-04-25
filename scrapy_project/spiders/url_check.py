import scrapy
from scrapy_project.items import ContentMediaItem

class URLCheckSpider(scrapy.Spider):
    name = "url_check"
    
    def __init__(self, target_url=None, *args, **kwargs):
        super(URLCheckSpider, self).__init__(*args, **kwargs)
        self.target_url = target_url

    def start_requests(self):
        if self.target_url:
            yield scrapy.Request(self.target_url, self.parse)

    def parse(self, response):
        for img in response.css('img::attr(src)').getall():
            yield ContentMediaItem(
                source_url=response.url,
                media_url=response.urljoin(img),
                platform="url_check",
                domain=response.url.split('/')[2]
            )
