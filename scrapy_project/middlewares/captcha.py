class CaptchaMiddleware:
    def process_response(self, request, response, spider):
        # Detect captcha
        if b"cf-turnstile" in response.body or b"g-recaptcha" in response.body:
            spider.logger.info("Captcha detected. Solving via 2Captcha API...")
            # token = solve_captcha(request.url)
            # request.meta['captcha_solved'] = token
            return request
        return response
