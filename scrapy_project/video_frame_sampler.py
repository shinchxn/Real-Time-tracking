"""
Video Frame Sampler — Content DNA Apex v6.0
Extracts keyframes from video URLs using ffmpeg subprocess calls.
Returns PIL Image objects for the 6-layer DNA fingerprinting pipeline.
"""
import io
import logging
import os
import subprocess
import tempfile
from typing import List, Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)

# Timestamps (seconds) to extract frames at
DEFAULT_TIMESTAMPS: List[int] = [0, 5, 15, 30]


def _check_ffmpeg() -> bool:
    """Check if ffmpeg binary is available on PATH."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


_FFMPEG_AVAILABLE: Optional[bool] = None


def _ffmpeg_available() -> bool:
    global _FFMPEG_AVAILABLE
    if _FFMPEG_AVAILABLE is None:
        _FFMPEG_AVAILABLE = _check_ffmpeg()
        if not _FFMPEG_AVAILABLE:
            logger.warning(
                "[VideoFrameSampler] ffmpeg not found on PATH. "
                "Video fingerprinting will be skipped. "
                "Install: apt-get install -y ffmpeg  OR  brew install ffmpeg"
            )
    return _FFMPEG_AVAILABLE


def get_video_duration(video_url: str, timeout: int = 15) -> Optional[float]:
    """
    Use ffprobe to get video duration in seconds.
    Returns None if ffprobe unavailable or call fails.
    """
    if not _ffmpeg_available():
        return None
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_url,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass
    return None


class VideoFrameSampler:
    """
    Extracts keyframes from a video URL at specified timestamps using ffmpeg.

    Args:
        timestamps: List of seconds to extract. Defaults to [0, 5, 15, 30].
        quality: JPEG quality for frame extraction (1-31, lower = higher quality).
        timeout: Subprocess timeout in seconds per frame.

    Example:
        sampler = VideoFrameSampler()
        frames = sampler.extract(video_url)
        # frames is a list of (timestamp, PIL.Image) tuples
    """

    def __init__(
        self,
        timestamps: List[int] = None,
        quality: int = 2,
        timeout: int = 30,
    ):
        self.timestamps = timestamps or DEFAULT_TIMESTAMPS
        self.quality = quality
        self.timeout = timeout

    def extract(self, video_url: str) -> List[Tuple[int, Image.Image]]:
        """
        Extract frames at self.timestamps from video_url.

        Returns:
            List of (timestamp_seconds, PIL.Image) tuples.
            Empty list if ffmpeg unavailable or extraction fails.
        """
        if not _ffmpeg_available():
            logger.warning("[VideoFrameSampler] Skipping video (ffmpeg unavailable): %s", video_url)
            return []

        frames: List[Tuple[int, Image.Image]] = []

        with tempfile.TemporaryDirectory(prefix="vfs_") as tmpdir:
            for ts in self.timestamps:
                frame_path = os.path.join(tmpdir, f"frame_{ts:04d}.jpg")
                success = self._extract_frame(video_url, ts, frame_path)
                if success:
                    try:
                        img = Image.open(frame_path).convert("RGB")
                        # Copy to memory buffer before temp dir is cleaned up
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG")
                        buf.seek(0)
                        frames.append((ts, Image.open(buf).convert("RGB")))
                    except Exception as e:
                        logger.warning("[VideoFrameSampler] Failed to open frame t=%ds: %s", ts, e)

        logger.info("[VideoFrameSampler] Extracted %d/%d frames from %s",
                    len(frames), len(self.timestamps), video_url[:80])
        return frames

    def extract_images_only(self, video_url: str) -> List[Image.Image]:
        """
        Convenience method — returns only PIL Images (no timestamps).
        Used by the video detection pipeline.
        """
        return [img for _, img in self.extract(video_url)]

    def _extract_frame(self, video_url: str, timestamp_sec: int, output_path: str) -> bool:
        """
        Run ffmpeg to extract a single frame at the given timestamp.
        Returns True on success.
        """
        cmd = [
            "ffmpeg",
            "-ss", str(timestamp_sec),   # Seek BEFORE input for fast seeking
            "-i", video_url,
            "-frames:v", "1",            # Extract exactly 1 frame
            "-q:v", str(self.quality),   # JPEG quality
            "-vf", "scale=640:-1",       # Resize to 640px wide (aspect-preserved)
            "-y",                        # Overwrite output
            output_path,
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.timeout,
            )
            if result.returncode == 0 and os.path.exists(output_path):
                return True
            else:
                logger.debug(
                    "[VideoFrameSampler] ffmpeg exit %d at t=%ds: %s",
                    result.returncode,
                    timestamp_sec,
                    result.stderr[-300:].decode("utf-8", errors="ignore"),
                )
                return False
        except subprocess.TimeoutExpired:
            logger.warning("[VideoFrameSampler] ffmpeg timed out at t=%ds for: %s", timestamp_sec, video_url[:80])
            return False
        except FileNotFoundError:
            logger.error("[VideoFrameSampler] ffmpeg binary not found.")
            return False
