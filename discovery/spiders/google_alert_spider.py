"""
Google Alert Spider — Content DNA Apex v7.0
Polls RSS feeds for alerts and extracts media from linked pages.
"""
import scrapy
import feedparser
import logging

logger = logging.getLogger(__name__)

class GoogleAlertSpider(scrapy.Spider):
    name = 'google_alert'

    def __init__(self, rss_urls: str = None, *args, **kwargs):
        super(GoogleAlertSpider, self).__init__(*args, **kwargs)
        self.rss_urls = rss_urls.split(',') if rss_urls else []

    def start_requests(self):
        for rss_url in self.rss_urls:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries:
                yield scrapy.Request(
                    entry.link,
                    callback=self.parse_page,
                    meta={'source_rss': rss_url, 'title': entry.title}
                )

    def parse_page(self, response):
        """
        Extract all img and video tags from the page.
        """
        images = response.css('img::attr(src)').getall()
        videos = response.css('video::attr(src)').getall()
        videos += response.css('video source::attr(src)').getall()
        
        for img_url in images:
            yield {
                'source_url': response.url,
                'media_url': response.urljoin(img_url),
                'platform': 'web_google_alert',
                'media_type': 'image'
            }
            
        for video_url in videos:
            yield {
                'source_url': response.url,
                'media_url': response.urljoin(video_url),
                'platform': 'web_google_alert',
                'media_type': 'video'
            }
