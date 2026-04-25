from scrapy.exceptions import IgnoreRequest
class ResponseValidatorMiddleware:
    def process_response(self, request, response, spider):
        if len(response.body) < 100:
            raise IgnoreRequest("Response too small")
        return response
