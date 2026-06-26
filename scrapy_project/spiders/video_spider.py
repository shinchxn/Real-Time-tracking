import scrapy
from scrapy_project.items import ContentMediaItem

class VideoSpider(scrapy.Spider):
    name = "video_spider"
    
    async def start(self):
        async for url in self.load_targets():
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        # Extract video URLs
        for vid in response.css('video source::attr(src)').getall():
            yield ContentMediaItem(
                source_url=response.url,
                media_url=response.urljoin(vid),
                platform="video_platform",
                media_type="video",
                domain="example.com"
            )
