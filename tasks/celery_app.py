"""
Celery Application — Content DNA Apex
"""
import os
from celery import Celery

app = Celery(
    "contentdna",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_RESULT_URL", "redis://localhost:6379/1"),
    include=["tasks.fingerprint_tasks"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    enable_utc=True,
    result_expires=86400,
    task_routes={
        "tasks.fingerprint_tasks.fingerprint_and_match": {"queue": "fingerprint"},
        "tasks.fingerprint_tasks.deep_rescan":           {"queue": "rescan"},
        "tasks.fingerprint_tasks.generate_dmca":         {"queue": "dmca"},
        "tasks.fingerprint_tasks.anchor_to_blockchain":  {"queue": "blockchain"},
    },
)
