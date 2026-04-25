class RotatingProxyMiddleware:
    def process_request(self, request, spider):
        tier = request.meta.get('proxy_tier', 0)
        request.meta['proxy'] = f"http://proxy_tier{tier}.example.com:8080"
        
    def process_response(self, request, response, spider):
        if response.status in [403, 429]:
            # Escalate
            request.meta['proxy_tier'] = min(request.meta.get('proxy_tier', 0) + 1, 2)
            return request
        return response
