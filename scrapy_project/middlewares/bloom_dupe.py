class BloomFilterDupeMiddleware:
    """Deduplication logic is usually in dupefilter, but if implemented as middleware:"""
    def __init__(self):
        self.bloom = set() # Mocking bloom filter
        
    def process_request(self, request, spider):
        if request.url in self.bloom:
            from scrapy.exceptions import IgnoreRequest
            raise IgnoreRequest("Bloom filter dupe")
        self.bloom.add(request.url)
