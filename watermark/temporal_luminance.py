"""
Temporal Luminance Watermark — Content DNA Apex v7.1
Modulates average frame luminance at imperceptible frequency.
Survives screen recording, phone camera, and analog re-recording.
"""
import numpy as np
import hashlib
from typing import List, Optional
from dataclasses import dataclass
import subprocess
import io

@dataclass
class TemporalWatermarkConfig:
    fps: int = 25
    embed_frequency_hz: float = 3.5
    amplitude: float = 0.008
    payload_bits: int = 64
    symbol_duration_frames: int = 15
    carrier_frequency_hz: float = 12.0

class TemporalLuminanceEmbedder:
    def embed_frame_sequence(self, frames: List[np.ndarray], asset_id: str, stream_id: str) -> List[np.ndarray]:
        payload = self._build_payload(asset_id, stream_id)
        config = TemporalWatermarkConfig()
        out_frames = []

        for frame_idx, frame in enumerate(frames):
            bit_index = (frame_idx // config.symbol_duration_frames) % len(payload)
            bit = payload[bit_index]

            phase = 0 if bit == '1' else np.pi
            t = frame_idx / config.fps
            modulation = config.amplitude * np.sin(
                2 * np.pi * config.carrier_frequency_hz * t + phase
            )

            modified = np.clip(
                frame.astype(np.float32) * (1.0 + modulation),
                0, 255
            ).astype(np.uint8)
            out_frames.append(modified)

        return out_frames

    def _build_payload(self, asset_id: str, stream_id: str) -> str:
        asset_hash = int(hashlib.sha256(asset_id.encode()).hexdigest()[:8], 16)
        stream_hash = int(hashlib.sha256(stream_id.encode()).hexdigest()[:8], 16)
        combined = (asset_hash << 32) | stream_hash
        return format(combined, '064b')

class TemporalLuminanceExtractor:
    def extract_from_video(self, video_path: str) -> Dict[str, Any]:
        luminance_series = self._extract_luminance_series(video_path)
        if len(luminance_series) < 15: return {"valid": False}
        
        filtered = self._bandpass_filter(luminance_series, low=10.0, high=14.0)
        bits = self._demodulate_psk(filtered)
        
        # In real life: decode bits to asset_id and stream_id
        return {"valid": True, "bits": bits}

    def _extract_luminance_series(self, video_path: str) -> np.ndarray:
        cmd = [
            'ffmpeg', '-i', video_path,
            '-vf', 'scale=32:32,format=gray',
            '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1'
        ]
        result = subprocess.run(cmd, capture_output=True)
        if not result.stdout: return np.array([])
        raw = np.frombuffer(result.stdout, dtype=np.uint8)
        frames = raw.reshape(-1, 32, 32)
        return frames.mean(axis=(1, 2))

    def _bandpass_filter(self, signal: np.ndarray, low: float, high: float, sample_rate: float = 25.0) -> np.ndarray:
        from scipy.signal import butter, filtfilt
        nyq = sample_rate / 2
        b, a = butter(4, [low/nyq, high/nyq], btype='band')
        return filtfilt(b, a, signal)

    def _demodulate_psk(self, filtered: np.ndarray) -> str:
        config = TemporalWatermarkConfig()
        bits = []
        for i in range(0, len(filtered) - config.symbol_duration_frames, config.symbol_duration_frames):
            symbol = filtered[i:i + config.symbol_duration_frames]
            bits.append('1' if symbol.mean() > 0 else '0')
        return ''.join(bits)
