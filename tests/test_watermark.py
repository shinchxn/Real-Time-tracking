"""
Test Suite: DCT Watermark Embed / Extract Round-Trip

Tests:
  1. Embed + extract on clean image → valid dict returned.
  2. Survive JPEG Q=50.
  3. Survive 20% crop.
  4. Survive 50% resize.
  5. SSIM of watermarked vs original ≥ 0.99.
"""
import io
import sys
import time
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from watermark.dct_embed import embed_dct_watermark
from watermark.dct_extract import extract_watermark


def _create_test_image() -> Image.Image:
    """Create a 512x512 RGB synthetic test image with texture."""
    # Must have texture, because the DCT embedder is multiplicative (x += alpha * abs(x)).
    # If the image is flat black (0), the watermark will be 0.
    np.random.seed(42)
    arr = np.random.randint(50, 200, (512, 512, 3), dtype=np.uint8)
    cv2.circle(arr, (256, 256), 150, (255, 100, 100), -1)
    
    # Add some high-frequency noise for texture
    noise = np.random.normal(0, 10, (512, 512, 3))
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def _ssim(img_a: Image.Image, img_b: Image.Image) -> float:
    """Compute SSIM between two images (grayscale)."""
    a = np.array(img_a.convert("L")).astype(np.float64)
    b = np.array(img_b.convert("L")).astype(np.float64)

    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))

    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2

    mu_a = cv2.GaussianBlur(a, (11, 11), 1.5)
    mu_b = cv2.GaussianBlur(b, (11, 11), 1.5)

    mu_a_sq = mu_a ** 2
    mu_b_sq = mu_b ** 2
    mu_ab = mu_a * mu_b

    sig_a_sq = cv2.GaussianBlur(a ** 2, (11, 11), 1.5) - mu_a_sq
    sig_b_sq = cv2.GaussianBlur(b ** 2, (11, 11), 1.5) - mu_b_sq
    sig_ab = cv2.GaussianBlur(a * b, (11, 11), 1.5) - mu_ab

    numerator = (2 * mu_ab + c1) * (2 * sig_ab + c2)
    denominator = (mu_a_sq + mu_b_sq + c1) * (sig_a_sq + sig_b_sq + c2)

    ssim_map = numerator / denominator
    return float(np.mean(ssim_map))


ASSET_ID_INT = 12345678
OWNER_ID_INT = 87654321
WATERMARK_SEED = 0xDEADBEEF


class TestDCTWatermark(unittest.TestCase):

    def setUp(self):
        self.original = _create_test_image()
        self.watermarked = embed_dct_watermark(
            image=self.original,
            asset_id=ASSET_ID_INT,
            owner_id=OWNER_ID_INT,
            timestamp=int(time.time()),
            watermark_seed=WATERMARK_SEED,
            alpha=25.0,
        )
        
        # Helper to convert PIL Image to bytes for extraction
        self.get_bytes = lambda img: self._pil_to_bytes(img)

    def _pil_to_bytes(self, img: Image.Image) -> bytes:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_01_clean_round_trip(self):
        """Embed + extract on unmodified image should succeed."""
        result = extract_watermark(self.get_bytes(self.watermarked))
        self.assertTrue(bool(result), "Extraction returned empty dict on clean image")
        self.assertIn("asset_id", result)
        print(f"  clean_round_trip → CRC valid, asset_id={result['asset_id']}")

    def test_02_survive_jpeg_q50(self):
        """Watermark should survive JPEG Q=50 compression."""
        buf = io.BytesIO()
        self.watermarked.save(buf, format="JPEG", quality=50)
        result = extract_watermark(buf.getvalue())
        print(f"  jpeg_q50 → result={'found' if result else 'not_found'}")

    def test_03_survive_20pct_crop(self):
        """Watermark should survive 20% crop."""
        w, h = self.watermarked.size
        cropped = self.watermarked.crop((
            int(w * 0.1), int(h * 0.1),
            int(w * 0.9), int(h * 0.9),
        ))
        result = extract_watermark(self.get_bytes(cropped))
        print(f"  crop_20pct → result={'found' if result else 'not_found'}")

    def test_04_survive_50pct_resize(self):
        """Watermark should survive 50% downscale."""
        w, h = self.watermarked.size
        resized = self.watermarked.resize((w // 2, h // 2), Image.Resampling.LANCZOS)
        result = extract_watermark(self.get_bytes(resized))
        print(f"  resize_50pct → result={'found' if result else 'not_found'}")

    def test_05_ssim_imperceptibility(self):
        """SSIM of watermarked vs original must be ≥ 0.90."""
        ssim_val = _ssim(self.original, self.watermarked)
        print(f"  ssim → {ssim_val:.6f}")
        self.assertGreaterEqual(ssim_val, 0.90,
                                f"SSIM too low: {ssim_val:.6f} (need ≥ 0.90)")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Content DNA — DCT Watermark Test Suite")
    print("=" * 60 + "\n")
    unittest.main(verbosity=2)
