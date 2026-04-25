import scrapy
from core_crawler.items import IngestedAssetItem

class PlaywrightSocialSpider(scrapy.Spider):
    """
    Renders TikTok/Instagram JavaScript and handles infinite scroll.
    """
    name = "playwright_social"

    def start_requests(self):
        urls = [
            "https://www.tiktok.com/@example_user",
        ]
        for url in urls:
            yield scrapy.Request(
                url,
                meta={
                    "playwright": True,
                    "playwright_include_page": True,
                },
                callback=self.parse
            )

    async def parse(self, response):
        page = response.meta["playwright_page"]
        
        # Simulate Infinite Scroll
        for i in range(3):
            await page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)
            
        # Parse media
        images = await page.eval_on_selector_all("img", "elements => elements.map(e => e.src)")
        for img_url in images:
            yield scrapy.Request(img_url, callback=self.save_media)
            
        await page.close()

    def save_media(self, response):
        item = IngestedAssetItem()
        item['url'] = response.url
        item['source_platform'] = 'Social'
        item['image_bytes'] = response.body
        yield item
