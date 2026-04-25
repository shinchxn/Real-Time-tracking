from scrapy.exceptions import DropItem

class ValidationPipeline:
    def process_item(self, item, spider):
        if not item.get('media_url'):
            raise DropItem("Missing media url")
        return item
