BOT_NAME = "core_crawler"

SPIDER_MODULES = ["core_crawler.spiders"]
NEWSPIDER_MODULE = "core_crawler.spiders"

# --- Twisted Async Engine ---
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# --- scrapy-redis distributed scaling ---
SCHEDULER = "scrapy_redis.scheduler.Scheduler"
DUPEFILTER_CLASS = "scrapy_redis.dupefilter.RFPDupeFilter"
REDIS_URL = "redis://127.0.0.1:6379"
SCHEDULER_PERSIST = True

# --- Scrapy Playwright ---
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

# --- 12-middleware anti-bot stack ---
DOWNLOADER_MIDDLEWARES = {
    "core_crawler.middlewares.ToSComplianceMiddleware": 100,
    "core_crawler.middlewares.TLSFingerprintMiddleware": 200,
    "core_crawler.middlewares.ProxyEscalationMiddleware": 300,
    "core_crawler.middlewares.CaptchaSolverMiddleware": 400,
}

# --- 9-stage item pipeline ---
ITEM_PIPELINES = {
    "core_crawler.pipelines.MediaDownloadPipeline": 100,
    "core_crawler.pipelines.PlatformSimulationPipeline": 200,
    "core_crawler.pipelines.DNAExtractionPipeline": 300,
    "core_crawler.pipelines.FAISSDetectionPipeline": 400,
    "core_crawler.pipelines.WatermarkExtractionPipeline": 500,
    "core_crawler.pipelines.AlertFirePipeline": 600,
    "core_crawler.pipelines.SupabaseStoragePipeline": 700,
    "core_crawler.pipelines.KafkaIntegrationPipeline": 800,
}

ROBOTSTXT_OBEY = False
CONCURRENT_REQUESTS = 100
LOG_LEVEL = "INFO"

# Add project root to path for pipeline imports
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
