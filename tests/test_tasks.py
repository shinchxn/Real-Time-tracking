"""
Celery Task Tests — Content DNA Apex v7.1
FIX 22: Tests for all background tasks (existence, execution, structure).
"""
import base64
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from PIL import Image
import io


def make_test_image_b64(width=100, height=100, color=(255, 0, 0)) -> str:
    """Create a minimal valid JPEG as base64 string."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode()


# ── Task existence checks ─────────────────────────────────────────────────────

def test_fingerprint_and_match_task_exists():
    from background_tasks import fingerprint_and_match
    assert callable(fingerprint_and_match)


def test_run_dork_sweep_task_exists():
    from background_tasks import run_dork_sweep
    assert callable(run_dork_sweep)


def test_crawl_platform_task_exists():
    from background_tasks import crawl_platform
    assert callable(crawl_platform)


def test_deep_rescan_task_exists():
    from background_tasks import deep_rescan
    assert callable(deep_rescan)


def test_anchor_to_blockchain_task_exists():
    from background_tasks import anchor_to_blockchain
    assert callable(anchor_to_blockchain)


def test_generate_dmca_task_exists():
    from background_tasks import generate_dmca
    assert callable(generate_dmca)


# ── Task registration check ──────────────────────────────────────────────────

def test_all_tasks_registered_in_celery():
    """All tasks must be registered with the celery app."""
    from celery_app import celery_app
    registered = celery_app.tasks.keys()
    expected = [
        'background_tasks.fingerprint_and_match',
        'background_tasks.anchor_to_blockchain',
        'background_tasks.generate_dmca',
        'background_tasks.run_dork_sweep',
        'background_tasks.crawl_platform',
        'background_tasks.deep_rescan',
    ]
    for task_name in expected:
        assert task_name in registered, f"Task not registered: {task_name}"


# ── JSON serialization check ──────────────────────────────────────────────────

def test_celery_uses_json_serializer():
    """FIX 13: Verify celery_app uses JSON, not pickle."""
    from celery_app import celery_app
    assert celery_app.conf.task_serializer == 'json'
    assert 'json' in celery_app.conf.accept_content
    assert 'pickle' not in celery_app.conf.accept_content


# ── fingerprint_and_match execution ──────────────────────────────────────────

def test_fingerprint_and_match_runs_without_crash():
    """fingerprint_and_match should not crash on a valid image."""
    from background_tasks import fingerprint_and_match

    media_b64 = make_test_image_b64()

    with patch("detection.faiss_index.FAISSIndex") as mock_faiss_cls, \
         patch("background_tasks.asyncio.run") as mock_run, \
         patch("watermark.dct_extract.extract_watermark", return_value={}), \
         patch("background_tasks._get_clip") as mock_clip:

        import numpy as np
        import torch

        mock_faiss_cls.return_value.search.return_value = []
        mock_run.return_value = None

        # Mock CLIP model
        mock_model = MagicMock()
        mock_processor = MagicMock()
        mock_vec = torch.zeros(1, 512)
        mock_model.get_image_features.return_value = mock_vec
        mock_processor.return_value = {"pixel_values": torch.zeros(1, 3, 224, 224)}
        mock_clip.return_value = (mock_model, mock_processor)

        # Should not raise
        fingerprint_and_match.run(media_b64, "https://example.com", "web")


def test_fingerprint_accepts_base64_string():
    """FIX 13: Task must accept a string (base64), not bytes."""
    from background_tasks import fingerprint_and_match
    import inspect
    sig = inspect.signature(fingerprint_and_match.run)
    params = list(sig.parameters.keys())
    # First param after self should accept base64 string
    assert "media_bytes_b64" in params


# ── No deprecated asyncio patterns ───────────────────────────────────────────

def test_no_get_event_loop_in_background_tasks():
    """FIX 7: background_tasks.py must not use asyncio.get_event_loop()."""
    import ast
    import os

    src_path = os.path.join(os.path.dirname(__file__), "..", "background_tasks.py")
    with open(src_path) as f:
        source = f.read()

    assert "get_event_loop()" not in source, \
        "asyncio.get_event_loop() found in background_tasks.py — use asyncio.run() instead"


def test_no_hardcoded_private_key():
    """FIX 11: background_tasks.py must not contain hardcoded private key."""
    import os

    src_path = os.path.join(os.path.dirname(__file__), "..", "background_tasks.py")
    with open(src_path) as f:
        source = f.read()

    assert "0x_user_key_" not in source, "Hardcoded private key found in background_tasks.py"


def test_no_mock_features_in_background_tasks():
    """FIX 8: background_tasks.py must not have mock CLIP features."""
    import os

    src_path = os.path.join(os.path.dirname(__file__), "..", "background_tasks.py")
    with open(src_path) as f:
        source = f.read()

    assert '[0.1]*512' not in source, "Mock CLIP features found in background_tasks.py"
