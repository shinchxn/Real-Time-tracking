from scrapy.exceptions import IgnoreRequest
import time

class RateLimitWatchdogMiddleware:
    limits = {}
    
    def process_response(self, request, response, spider):
        if response.status == 429:
            domain = request.url.split('/')[2]
            self.limits[domain] = self.limits.get(domain, 0) + 1
            if self.limits[domain] > 5:
                # Pause spider
                spider.logger.warning(f"Rate limited excessively on {domain}. Pausing.")
                time.sleep(30)
                self.limits[domain] = 0
        return response
