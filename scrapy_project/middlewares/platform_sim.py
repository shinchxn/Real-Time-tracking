class PlatformSimulatorMiddleware:
    """Usually handles request logic, but we do platform sim in pipeline.
    This middleware might pass metadata."""
    def process_request(self, request, spider):
        if "instagram" in request.url:
            request.meta['platform_sim'] = 'instagram'
        elif "tiktok" in request.url:
            request.meta['platform_sim'] = 'tiktok'
