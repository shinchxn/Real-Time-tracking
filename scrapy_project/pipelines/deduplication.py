from scrapy.exceptions import DropItem

class DeduplicationPipeline:
    def __init__(self):
        self.seen = set()
        
    def process_item(self, item, spider):
        uid = item.get('media_url')
        if uid in self.seen:
            raise DropItem("Duplicate item")
        self.seen.add(uid)
        return item
