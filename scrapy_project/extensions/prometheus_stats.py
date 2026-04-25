from scrapy import signals
class PrometheusStatsExtension:
    @classmethod
    def from_crawler(cls, crawler):
        ext = cls()
        crawler.signals.connect(ext.item_scraped, signal=signals.item_scraped)
        return ext
        
    def item_scraped(self, item, spider):
        # Update metrics, send to prom gateway
        pass
