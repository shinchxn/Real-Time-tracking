"""
Audio Fingerprinting — Chromaprint + Mel-spectrogram CNN
Extracts robust audio signatures to track highlights and synchronized content.
"""
import logging
import numpy as np
import librosa
import chromaprint
from typing import Tuple

logger = logging.getLogger(__name__)

def extract_audio_fingerprint(audio_path: str) -> Tuple[bytes, np.ndarray]:
    """
    Extract dual audio fingerprints:
      1. Chromaprint (AcoustID compatible)
      2. Mel-spectrogram Mean Vector (CNN-ready feature)
    """
    try:
        # Load audio
        y, sr = librosa.load(audio_path, sr=22050)
        
        # 1. Chromaprint
        # Convert to 16-bit PCM for pychromaprint
        y_int16 = (y * 32767).astype(np.int16)
        duration, fp_hash = chromaprint.decode_fingerprint(
            chromaprint.encode_fingerprint(y_int16.tobytes(), sr, 1)
        )
        
        # 2. Mel-spectrogram signature
        mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)
        mel_db = librosa.power_to_db(mel, ref=np.max)
        
        # Aggregate to a fixed-size vector (mean across time)
        mel_vec = np.mean(mel_db, axis=1) # [128]
        
        # Normalize
        mel_vec = (mel_vec - np.mean(mel_vec)) / (np.std(mel_vec) + 1e-8)
        
        return fp_hash, mel_vec
        
    except Exception as exc:
        logger.error(f"Failed to extract audio fingerprint: {exc}")
        return b"", np.zeros(128, dtype=np.float32)

def compare_audio_fingerprints(mel_a: np.ndarray, mel_b: np.ndarray) -> float:
    """Cosine similarity of mel-spectrogram vectors."""
    from scipy.spatial.distance import cosine
    dist = cosine(mel_a, mel_b)
    return 1.0 - np.clip(dist, 0, 1)
