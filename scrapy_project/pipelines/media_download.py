import os
from scrapy.pipelines.images import ImagesPipeline
from scrapy import Request

class MediaDownloadPipeline(ImagesPipeline):
    def get_media_requests(self, item, info):
        if item.get('media_url'):
            yield Request(item['media_url'])

    def item_completed(self, results, item, info):
        image_paths = [x['path'] for ok, x in results if ok]
        if image_paths:
            item['local_path'] = os.path.join(self.store.basedir, image_paths[0])
        return item
