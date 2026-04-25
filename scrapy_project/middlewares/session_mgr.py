class SessionMiddleware:
    def process_request(self, request, spider):
        domain = request.url.split('/')[2]
        request.meta['cookiejar'] = domain
