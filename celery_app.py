"""
Celery Configuration — Content DNA Apex v7.0
Distributed task queue configuration for matching, crawling, and rescan tasks.
"""
from celery import Celery
from celery.schedules import crontab
import os

celery_app = Celery(
    "content_dna",
    broker=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://redis:6379/1")
)

celery_app.conf.update(
    task_serializer='pickle',
    accept_content=['pickle', 'json'],
    result_serializer='pickle',
    timezone='UTC',
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        'background_tasks.fingerprint_and_match': {'queue': 'fingerprint'},
        'background_tasks.deep_rescan': {'queue': 'rescan'},
        'background_tasks.generate_dmca': {'queue': 'dmca'},
        'background_tasks.crawl_platform': {'queue': 'crawl'},
        'background_tasks.run_dork_sweep': {'queue': 'dork'},
        'background_tasks.anchor_to_blockchain': {'queue': 'blockchain'},
    }
)

# Beat Schedule
celery_app.conf.beat_schedule = {
    'crawl-instagram-2h': {
        'task': 'background_tasks.crawl_platform',
        'schedule': crontab(minute=0, hour='*/2'),
        'args': ['instagram', ['#sportshighlights', '#nba', '#ipl']]
    },
    'crawl-web-6h': {
        'task': 'background_tasks.crawl_platform',
        'schedule': crontab(minute=0, hour='*/6'),
        'args': ['web', ['https://www.google.com/alerts/feeds/...']]
    }
}

import background_tasks # Register tasks
