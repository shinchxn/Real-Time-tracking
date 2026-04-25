import os
from pathlib import Path

tree = [
    "fingerprint", "watermark", "detection", "video", "audio", "ai_detection",
    "blockchain", "viral", "scrapy_project/spiders", "scrapy_project/middlewares",
    "scrapy_project/pipelines", "scrapy_project/extensions", "extension/popup",
    "api", "db", "tasks", "dashboard", "tests"
]

base = Path("d:/Real-Time Tracking")
for d in tree:
    p = base / d
    p.mkdir(parents=True, exist_ok=True)
    if not str(d).startswith("dashboard") and not str(d).startswith("extension"):
        (p / "__init__.py").touch()
print("Directories created.")
