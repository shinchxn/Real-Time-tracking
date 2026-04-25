import json
from scrapy.exceptions import IgnoreRequest

class ToSComplianceMiddleware:
    def __init__(self):
        try:
            with open("d:/Real-Time Tracking/permitted_domains.json", "r") as f:
                self.permitted = json.load(f)
        except Exception:
            self.permitted = []
            
    def process_request(self, request, spider):
        domain = request.url.split('/')[2]
        if not any(pd in domain for pd in self.permitted):
            # LEGAL GATE, NEVER DISABLE - block if domain not in allow_list
            raise IgnoreRequest(f"Domain {domain} not in permitted list")
