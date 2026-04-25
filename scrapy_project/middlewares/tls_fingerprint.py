import random
class TLSFingerprintMiddleware:
    def process_request(self, request, spider):
        # Defeats Cloudflare, Akamai (mock changing context)
        request.meta['tls_fingerprint'] = f"ja3_{random.randint(1000, 9999)}"
