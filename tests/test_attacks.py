"""
Test Suite: Full Robustness Attack Matrix (8 attack types)

Each test:
  1. Uploads an original image.
  2. Applies a specific attack transform.
  3. Runs the detection pipeline.
  4. Asserts fusion_score meets the minimum threshold.

Minimum precision: 0.87, minimum recall: 0.83
"""
import asyncio
import io
import os
import sys
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

# Ensure content-dna is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from detection.faiss_index import FAISSIndex
from detection.detector import detect_pipeline, extract_all_fingerprints
from fingerprint.phash import extract_phashes

# ── Test asset generation ────────────────────────────────────────────

def _create_test_image(size: tuple = (512, 512), seed: int = 42) -> Image.Image:
    """Create a reproducible test image with varied features."""
    rng = np.random.RandomState(seed)
    img = rng.randint(0, 255, (*size, 3), dtype=np.uint8)

    # Add some structure (gradients, shapes) so fingerprints work
    for y in range(size[0]):
        for x in range(size[1]):
            img[y, x, 0] = int(255 * (x / size[1]))       # red gradient
            img[y, x, 1] = int(255 * (y / size[0]))       # green gradient
            img[y, x, 2] = rng.randint(100, 200)          # blue noise

    # Draw some circles
    cv_img = img.copy()
    cv2.circle(cv_img, (256, 256), 80, (255, 0, 0), -1)
    cv2.circle(cv_img, (128, 384), 60, (0, 255, 0), -1)
    cv2.rectangle(cv_img, (300, 300), (450, 450), (0, 0, 255), -1)

    return Image.fromarray(cv_img)


# ── Attack transforms ───────────────────────────────────────────────

def crop_attack(img: Image.Image, pct: float = 0.35) -> Image.Image:
    """Crop up to `pct` from edges."""
    w, h = img.size
    left = int(w * pct * 0.5)
    top = int(h * pct * 0.5)
    right = w - int(w * pct * 0.5)
    bottom = h - int(h * pct * 0.5)
    return img.crop((left, top, right, bottom))


def compress_attack(img: Image.Image, quality: int = 30) -> Image.Image:
    """JPEG re-encode at low quality."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def resize_attack(img: Image.Image, target: int = 128) -> Image.Image:
    """Downscale to small dimension."""
    return img.resize((target, target), Image.Resampling.LANCZOS)


def filter_attack(img: Image.Image) -> Image.Image:
    """Apply blur + brightness + hue shift."""
    img = img.filter(ImageFilter.GaussianBlur(radius=2))
    img = ImageEnhance.Brightness(img).enhance(1.4)
    # Hue shift via HSV
    arr = np.array(img)
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
    hsv[:, :, 0] = (hsv[:, :, 0].astype(int) + 20) % 180
    arr = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    return Image.fromarray(arr)


def watermark_overlay_attack(img: Image.Image) -> Image.Image:
    """Add a text watermark overlay covering ~20% of image."""
    arr = np.array(img).copy()
    h, w = arr.shape[:2]
    cv2.putText(arr, "SAMPLE", (w // 4, h // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 3.0, (255, 255, 255), 8)
    cv2.putText(arr, "WATERMARK", (w // 6, h // 2 + 80),
                cv2.FONT_HERSHEY_SIMPLEX, 2.0, (200, 200, 200), 5)
    return Image.fromarray(arr)


def screenshot_attack(img: Image.Image) -> Image.Image:
    """Simulate screenshot: slight blur + noise + border."""
    arr = np.array(img).astype(np.float32)
    noise = np.random.normal(0, 5, arr.shape).astype(np.float32)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr)
    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
    # Add black border (simulating screenshot)
    w, h = img.size
    bordered = Image.new("RGB", (w + 20, h + 20), (0, 0, 0))
    bordered.paste(img, (10, 10))
    return bordered


def flip_rotate_attack(img: Image.Image) -> Image.Image:
    """Horizontal flip + 10° rotation."""
    img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    img = img.rotate(10, expand=True, fillcolor=(0, 0, 0))
    return img


def social_media_attack(img: Image.Image) -> Image.Image:
    """Simulate social media processing: resize + compress + slight crop."""
    img = img.resize((1080, 1080), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=72)
    buf.seek(0)
    img = Image.open(buf).convert("RGB")
    w, h = img.size
    img = img.crop((10, 10, w - 10, h - 10))
    return img


# ── Test class ───────────────────────────────────────────────────────

class TestAttackRobustness(unittest.TestCase):
    """Robustness test suite for the 8-attack matrix."""

    @classmethod
    def setUpClass(cls):
        """Create test image, build FAISS index with it."""
        cls.original = _create_test_image(seed=42)
        cls.faiss_index = FAISSIndex(
            clip_dim=settings.CLIP_EMBEDDING_DIM,
            index_dir="./tests/temp/faiss_test",
        )

        # Ingest original
        loop = asyncio.new_event_loop()
        dna_pkg = loop.run_until_complete(
            extract_all_fingerprints(cls.original)
        )
        clip_vec, phashes, hog_vec, color_vec, dct_vec, spatial_vec = dna_pkg["global"]
        
        cls.faiss_index.add(
            clip_vec=clip_vec,
            hog_vec=hog_vec,
            color_vec=color_vec,
            dct_vec=dct_vec,
            spatial_vec=spatial_vec,
            asset_id="test-original-001",
            phash=phashes.phash,
            metadata={"filename": "test_original.png"},
        )
        cls.loop = loop

    def _run_detect(self, attacked_image: Image.Image) -> float:
        """Run detection and return best fusion score."""
        result = self.loop.run_until_complete(
            detect_pipeline(
                image=attacked_image,
                faiss_index=self.faiss_index,
                query_id="test-query",
                k=5,
            )
        )
        if result.best_match:
            return result.best_match.fusion_score
        return 0.0

    def test_01_crop_attack(self):
        """Detect after up to 35% crop."""
        attacked = crop_attack(self.original, pct=0.35)
        score = self._run_detect(attacked)
        print(f"  crop_attack         → fusion_score = {score:.4f}")
        self.assertGreaterEqual(score, 0.72, f"Crop attack failed: {score}")

    def test_02_compress_attack(self):
        """Detect after JPEG Q=30."""
        attacked = compress_attack(self.original, quality=30)
        score = self._run_detect(attacked)
        print(f"  compress_attack     → fusion_score = {score:.4f}")
        self.assertGreaterEqual(score, 0.72, f"Compress attack failed: {score}")

    def test_03_resize_attack(self):
        """Detect after downscale to 128×128."""
        attacked = resize_attack(self.original, target=128)
        score = self._run_detect(attacked)
        print(f"  resize_attack       → fusion_score = {score:.4f}")
        self.assertGreaterEqual(score, 0.72, f"Resize attack failed: {score}")

    def test_04_filter_attack(self):
        """Detect after blur + brightness + hue shift."""
        attacked = filter_attack(self.original)
        score = self._run_detect(attacked)
        print(f"  filter_attack       → fusion_score = {score:.4f}")
        self.assertGreaterEqual(score, 0.72, f"Filter attack failed: {score}")

    def test_05_watermark_overlay_attack(self):
        """Detect after text overlay covering ~20%."""
        attacked = watermark_overlay_attack(self.original)
        score = self._run_detect(attacked)
        print(f"  watermark_attack    → fusion_score = {score:.4f}")
        self.assertGreaterEqual(score, 0.72, f"Watermark overlay failed: {score}")

    def test_06_screenshot_attack(self):
        """Detect after simulated screenshot."""
        attacked = screenshot_attack(self.original)
        score = self._run_detect(attacked)
        print(f"  screenshot_attack   → fusion_score = {score:.4f}")
        self.assertGreaterEqual(score, 0.72, f"Screenshot attack failed: {score}")

    def test_07_flip_rotate_attack(self):
        """Detect after horizontal flip + 10° rotation."""
        attacked = flip_rotate_attack(self.original)
        score = self._run_detect(attacked)
        print(f"  flip_rotate_attack  → fusion_score = {score:.4f}")
        self.assertGreaterEqual(score, 0.60, f"Flip/rotate failed: {score}")

    def test_08_social_media_attack(self):
        """Detect after Instagram/Twitter/TikTok auto-processing."""
        attacked = social_media_attack(self.original)
        score = self._run_detect(attacked)
        print(f"  social_media_attack → fusion_score = {score:.4f}")
        self.assertGreaterEqual(score, 0.72, f"Social media attack failed: {score}")

    def test_09_combined_crop_and_filter(self):
        """The ultimate acceptance test: 35% crop + Instagram filter + re-upload."""
        attacked = crop_attack(self.original, pct=0.35)
        attacked = filter_attack(attacked)
        attacked = compress_attack(attacked, quality=60)
        score = self._run_detect(attacked)
        print(f"  combined_attack     → fusion_score = {score:.4f}")
        self.assertGreaterEqual(score, 0.60,
                                f"Combined crop+filter+compress failed: {score}")

    @classmethod
    def tearDownClass(cls):
        cls.loop.close()
        import shutil
        shutil.rmtree("./tests/temp/faiss_test", ignore_errors=True)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Content DNA — Robustness Attack Matrix Test Suite")
    print("=" * 60 + "\n")
    unittest.main(verbosity=2)
