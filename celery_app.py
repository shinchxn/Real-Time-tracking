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
        'tasks.fingerprint_and_match': {'queue': 'fingerprint'},
        'tasks.deep_rescan': {'queue': 'rescan'},
        'tasks.generate_dmca': {'queue': 'dmca'},
        'tasks.crawl_platform': {'queue': 'crawl'},
        'tasks.run_dork_sweep': {'queue': 'dork'},
    }
)

# Beat Schedule
celery_app.conf.beat_schedule = {
    'crawl-instagram-2h': {
        'task': 'tasks.crawl_platform',
        'schedule': crontab(minute=0, hour='*/2'),
        'args': ['instagram', ['#sportshighlights', '#nba', '#ipl']]
    },
    'crawl-web-6h': {
        'task': 'tasks.crawl_platform',
        'schedule': crontab(minute=0, hour='*/6'),
        'args': ['web', ['https://www.google.com/alerts/feeds/...']]
    },
    'dork-sweep-daily': {
        'task': 'tasks.run_dork_sweep_all',
        'schedule': crontab(hour=3, minute=0)
    },
    'deep-rescan-weekly': {
        'task': 'tasks.deep_rescan_all',
        'schedule': crontab(day_of_week=0, hour=2)
    },
}
