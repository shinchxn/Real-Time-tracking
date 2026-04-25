"""
Video Detector — Content DNA Apex v7.0
Multi-frame aggregate detection for video content.
"""
from dataclasses import dataclass
from typing import List, Dict, Optional
import numpy as np
import logging
from discovery.video_frame_sampler import VideoFrameSampler
from watermark.dct_extract import blind_extract
from detection.fusion import compute_fusion_score

logger = logging.getLogger(__name__)

@dataclass
class VideoSighting:
    asset_id: str
    severity: str
    matched_frame_count: int
    matched_frame_timestamps: List[int]
    video_duration_seconds: int
    proof_type: str

class VideoDetector:
    async def detect_video(self, video_url: str) -> List[VideoSighting]:
        """
        Extract frames and aggregate detection results.
        """
        sampler = VideoFrameSampler()
        timestamps = [0, 5, 15, 30]
        frames = sampler.extract_frames(video_url, timestamps=timestamps)
        
        detections_by_asset = {}
        
        for i, frame in enumerate(frames):
            # 1. Blind Watermark check
            # Convert PIL to bytes
            import io
            buffer = io.BytesIO()
            frame.save(buffer, format='PNG')
            wm_res = blind_extract(buffer.getvalue())
            
            if wm_res:
                asset_id = wm_res.asset_id
                if asset_id not in detections_by_asset:
                    detections_by_asset[asset_id] = {'frames': [], 'proofs': set()}
                detections_by_asset[asset_id]['frames'].append(timestamps[i])
                detections_by_asset[asset_id]['proofs'].add('CRYPTOGRAPHIC_LAYER_MATCH')
            
            # 2. Forensic Visual check (FAISS + Fusion)
            # In a real impl, we'd extract DNA and search FAISS here
            # result = search_index(extract_dna(frame))
            # ...
            
        results = []
        for asset_id, data in detections_by_asset.items():
            frame_count = len(data['frames'])
            severity = 'LOW'
            if frame_count >= 2: severity = 'HIGH'
            if 'CRYPTOGRAPHIC_LAYER_MATCH' in data['proofs']: severity = 'CRITICAL'
            
            results.append(VideoSighting(
                asset_id=asset_id,
                severity=severity,
                matched_frame_count=frame_count,
                matched_frame_timestamps=data['frames'],
                video_duration_seconds=30, # Placeholder
                proof_type=next(iter(data['proofs'])) if data['proofs'] else 'FORENSIC_VISUAL_MATCH'
            ))
            
        return results
