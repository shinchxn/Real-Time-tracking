import random
class HeaderRandomizerMiddleware:
    def process_request(self, request, spider):
        request.headers['Accept-Language'] = random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.5"])
        request.headers['DNT'] = "1"
