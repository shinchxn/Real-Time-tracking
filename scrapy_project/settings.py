BOT_NAME = 'vyntra_apex'

SPIDER_MODULES = ['scrapy_project.spiders']
NEWSPIDER_MODULE = 'scrapy_project.spiders'

# Scrapy overrides
CONCURRENT_REQUESTS = 32
CONCURRENT_REQUESTS_PER_DOMAIN = 8
DOWNLOAD_DELAY = 0.5
RANDOMIZE_DOWNLOAD_DELAY = True
ROBOTSTXT_OBEY = False  # Sports rights enforcement — intentional
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 60.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 8.0
RETRY_TIMES = 5
RETRY_HTTP_CODES = [429, 500, 502, 503, 520, 524]

# Playwright
DOWNLOAD_HANDLERS = {
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "http":  "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
PLAYWRIGHT_BROWSER_TYPE = "chromium"
PLAYWRIGHT_LAUNCH_OPTIONS = {"headless": True, "args": ["--no-sandbox"]}
PLAYWRIGHT_CONTEXTS = {"stealth": {"ignore_https_errors": True}}

# Redis Dist (Optimized with Vyntra DSA)
SCHEDULER                = "scrapy_project.dsa_components.VyntraScheduler"
DUPEFILTER_CLASS         = "scrapy_project.dsa_components.BloomDupeFilter"
SCHEDULER_PRIORITY_QUEUE = "scrapy_project.dsa_components.HeapPriorityQueue"
REDIS_URL = "redis://localhost:6379/2" # Upstash equivalent
SCHEDULER_PERSIST = True

# DSA Tunables
BLOOM_CAPACITY = 200_000_000
BLOOM_ERROR_RATE = 0.0005
LRU_CACHE_CAPACITY = 100_000

ITEM_PIPELINES = {
    'scrapy_project.dsa_components.LRUFingerprintPipeline': 50, # Early caching
    'scrapy_project.pipelines.validation.ValidationPipeline': 100,
    'scrapy_project.pipelines.deduplication.DeduplicationPipeline': 200,
    'scrapy_project.pipelines.media_download.MediaDownloadPipeline': 300,
    'scrapy_project.pipelines.platform_sim.PlatformSimPipeline': 400,
    'scrapy_project.pipelines.dna_fingerprint.DNAFingerPrintPipeline': 500,
    'scrapy_project.pipelines.detection.DetectionPipeline': 600,
    'scrapy_project.pipelines.watermark_extract.WatermarkExtractPipeline': 700,
    'scrapy_project.pipelines.alert.AlertPipeline': 800,
    'scrapy_project.pipelines.storage.StoragePipeline': 900,
    'scrapy_project.dsa_components.LRUCachePopulatorPipeline': 950,
}

DOWNLOADER_MIDDLEWARES = {
    'scrapy_project.dsa_components.ConsistentHashMiddleware': 50, # Routing
    'scrapy_project.dsa_components.TrieDomainMiddleware': 150,    # Governance
    'scrapy_project.middlewares.tls_fingerprint.TLSFingerprintMiddleware': 100,
    'scrapy_project.middlewares.rotating_proxy.RotatingProxyMiddleware': 200,
    'scrapy_project.middlewares.stealth_ua.StealthUserAgentMiddleware': 300,
    'scrapy_project.middlewares.header_random.HeaderRandomizerMiddleware': 350,
    'scrapy_project.middlewares.session_mgr.SessionMiddleware': 400,
    'scrapy_project.middlewares.captcha.CaptchaMiddleware': 450,
    'scrapy_project.middlewares.rate_watchdog.RateLimitWatchdogMiddleware': 550,
    'scrapy_project.middlewares.platform_sim.PlatformSimulatorMiddleware': 600,
    'scrapy_project.middlewares.response_validator.ResponseValidatorMiddleware': 650,
    'scrapy_project.middlewares.tos_compliance.ToSComplianceMiddleware': 700,
    'scrapy_project.middlewares.bloom_dupe.BloomFilterDupeMiddleware': 900,
}

EXTENSIONS = {
    'scrapy_project.extensions.prometheus_stats.PrometheusStatsExtension': 500,
}

# HTTP Cache (24-hour TTL to avoid redundant re-crawls)
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 86400
HTTPCACHE_DIR = 'data/httpcache'
HTTPCACHE_IGNORE_HTTP_CODES = [301, 302, 404, 500, 502, 503]
HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# Image Pipeline
IMAGES_STORE = './data/media'
