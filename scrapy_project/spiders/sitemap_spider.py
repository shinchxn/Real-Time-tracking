from scrapy.spiders import SitemapSpider
from scrapy_project.items import ContentMediaItem

class SiteMapMediaSpider(SitemapSpider):
    name = "sitemap_spider"
    sitemap_urls = ['http://example.com/sitemap.xml']

    def parse(self, response):
        for img in response.css('img::attr(src)').getall():
            yield ContentMediaItem(
                source_url=response.url,
                media_url=response.urljoin(img),
                platform="sitemap",
                domain=response.url.split('/')[2]
            )
