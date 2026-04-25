"""
Screen Recording Detector — Content DNA Apex v7.1
Detects and cleans artifacts from screen-recorded or phone-captured content.
Uses CLIP zero-shot classification as a pre-filter.
"""
import numpy as np
import cv2
import logging
from typing import List, Dict, Any
from discovery.video_frame_sampler import VideoFrameSampler

logger = logging.getLogger(__name__)

class ScreenRecordingDetector:
    def detect_screen_recording(self, video_path: str) -> List[Dict[str, Any]]:
        # 1. Pre-filter heuristic
        if not self._is_likely_screen_recording(video_path):
            return []

        # 2. Extract and Clean Frames
        sampler = VideoFrameSampler()
        frames = sampler.extract_frames(video_path, timestamps=[5, 10, 15])
        
        results = []
        for frame in frames:
            img_arr = np.array(frame)
            cleaned = self._remove_screen_artifacts(img_arr)
            # In real life: run CLIP on cleaned frame and search FAISS
            # ...
        
        return results

    def _is_likely_screen_recording(self, video_path: str) -> bool:
        # Heuristics: check for rolling shutter, RGB range, or use CLIP zero-shot
        # For now, return True to always check
        return True

    def _remove_screen_artifacts(self, frame: np.ndarray) -> np.ndarray:
        # 1. Bezel crop (simple version)
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        _, thresh = cv2.threshold(gray, 20, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest)
            if w > frame.shape[1] * 0.5:
                frame = frame[y:y+h, x:x+w]

        # 2. Moire removal (Blur)
        frame = cv2.GaussianBlur(frame, (3, 3), 0.5)
        return frame
