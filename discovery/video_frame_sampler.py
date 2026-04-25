"""
Video Frame Sampler — Content DNA Apex v7.0
Uses ffmpeg subprocess to extract keyframes from a video URL.
"""
import subprocess
import logging
import io
from PIL import Image
from typing import List

logger = logging.getLogger(__name__)

class VideoFrameSampler:
    def extract_frames(self, video_url: str, timestamps: List[int] = [0, 5, 15, 30]) -> List[Image.Image]:
        """
        Use ffmpeg to capture one frame at each timestamp.
        """
        frames = []
        for t in timestamps:
            try:
                # ffmpeg -ss {t} -i {url} -vframes 1 -f image2pipe -
                cmd = [
                    'ffmpeg',
                    '-ss', str(t),
                    '-i', video_url,
                    '-vframes', '1',
                    '-f', 'image2pipe',
                    '-vcodec', 'png',
                    '-'
                ]
                result = subprocess.run(cmd, capture_output=True, check=True)
                if result.stdout:
                    img = Image.open(io.BytesIO(result.stdout)).convert("RGB")
                    frames.append(img)
            except Exception as e:
                logger.warning(f"Failed to extract frame at {t}s from {video_url}: {e}")
                
        return frames

def get_video_duration(video_url: str) -> float:
    """Use ffprobe to get video duration."""
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', video_url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0
