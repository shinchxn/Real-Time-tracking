"""
Celery Application — Content DNA Apex v6.0
Broker: Redis /0
Result backend: Redis /1
Serializer: pickle (required for numpy arrays in fingerprint tasks)
"""
import os
from celery import Celery

app = Celery(
    "contentdna_v6",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_RESULT_URL", "redis://localhost:6379/1"),
    include=[
        "tasks.fingerprint_tasks",
        "tasks.beat_schedule",
    ],
)

app.conf.update(
    # Serialization — pickle required for numpy arrays
    task_serializer="pickle",
    result_serializer="pickle",
    accept_content=["pickle"],

    # Reliability
    task_acks_late=True,             # Prevent task loss on worker crash
    task_reject_on_worker_lost=True, # Requeue if worker dies mid-task
    worker_prefetch_multiplier=1,    # Fair distribution for long tasks

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Result expiry
    result_expires=86400,  # 24 hours

    # Task routing
    task_routes={
        "tasks.fingerprint_tasks.fingerprint_and_match": {"queue": "fingerprint"},
        "tasks.fingerprint_tasks.process_video_url":     {"queue": "fingerprint"},
        "tasks.fingerprint_tasks.deep_rescan":           {"queue": "rescan"},
        "tasks.fingerprint_tasks.generate_dmca":         {"queue": "dmca"},
        "tasks.fingerprint_tasks.persist_sighting":      {"queue": "storage"},
        "tasks.beat_schedule.crawl_platform":            {"queue": "crawl"},
    },

    # Queue definitions
    task_queues={
        "fingerprint": {"exchange": "fingerprint", "routing_key": "fingerprint"},
        "rescan":      {"exchange": "rescan",      "routing_key": "rescan"},
        "dmca":        {"exchange": "dmca",        "routing_key": "dmca"},
        "storage":     {"exchange": "storage",     "routing_key": "storage"},
        "crawl":       {"exchange": "crawl",       "routing_key": "crawl"},
    },
    task_default_queue="fingerprint",

    # Worker settings
    worker_max_tasks_per_child=500,   # Restart workers periodically to prevent memory leaks
)
