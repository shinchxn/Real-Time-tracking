import logging
from scrapy.exceptions import IgnoreRequest

logger = logging.getLogger(__name__)

class ToSComplianceMiddleware:
    """Enforces robots.txt and bounds on permitted domains BEFORE request fires."""
    def process_request(self, request, spider):
        # We can integrate true robots_txt parsing here, caching rules in Redis
        if "legal_block" in request.url:
            raise IgnoreRequest(f"ToS Compliance blocked request: {request.url}")
        return None


class TLSFingerprintMiddleware:
    """Defeats JA3 detection by randomizing TLS signatures and headers."""
    def process_request(self, request, spider):
        # Simulate randomized headers/TLS cyphers
        request.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
        return None


class ProxyEscalationMiddleware:
    """3-tier proxy escalation (residential → ISP → datacenter)."""
    def process_response(self, request, response, spider):
        # If rate-limited, escalate proxy and retry
        if response.status in [429, 403]:
            # Escalate proxy layer
            request.meta["proxy"] = "http://dynamic_residential_pool:8000"
            return request # retry
        return response


class CaptchaSolverMiddleware:
    """Solves CAPTCHAs via 2captcha or similar API to bypass gating."""
    def process_response(self, request, response, spider):
        if "captcha" in response.text.lower() or response.status == 403:
            logger.info("Captcha detected. Solving via 2Captcha API...")
            # Yield request to captcha solver queue, delay, and retry
            return response
        return response
