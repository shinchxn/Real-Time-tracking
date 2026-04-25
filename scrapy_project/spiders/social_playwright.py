import scrapy
from scrapy_project.items import ContentMediaItem

class PlaywrightSocialSpider(scrapy.Spider):
    name = "social_playwright"
    
    def start_requests(self):
        yield scrapy.Request(
            'https://example.com/social',
            meta={
                "playwright": True,
                "playwright_page_methods": [
                    ("wait_for_load_state", "networkidle"),
                    ("evaluate", "window.scrollBy(0, document.body.scrollHeight)"),
                    ("wait_for_timeout", 2000),
                ]
            },
            callback=self.parse
        )

    def parse(self, response):
        for img in response.css('img::attr(src)').getall():
            yield ContentMediaItem(
                source_url=response.url,
                media_url=response.urljoin(img),
                platform="social_spa",
                domain="example.com"
            )
