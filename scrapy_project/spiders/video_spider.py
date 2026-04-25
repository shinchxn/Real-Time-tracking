import scrapy
from scrapy_project.items import ContentMediaItem

class VideoSpider(scrapy.Spider):
    name = "video_spider"
    
    def start_requests(self):
        yield scrapy.Request('http://example.com/video', self.parse)

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
