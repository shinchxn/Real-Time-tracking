import numpy as np
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean

class TemporalHashSequence:
    """
    Manages THS (Temporal Hash Sequence) for video matching.
    """
    def __init__(self, sequence: np.ndarray):
        self.sequence = sequence  # shape (N, hash_dim)
        
    def match(self, other_sequence: np.ndarray, threshold: float = 0.85) -> dict:
        """
        Uses DTW (Dynamic Time Warping) to align and match sequences.
        """
        # DTW distance
        distance, path = fastdtw(self.sequence, other_sequence, dist=euclidean)
        
        # Normalize distance relative to sequence length
        max_len = max(len(self.sequence), len(other_sequence))
        if max_len == 0:
            return {"match": False, "score": 0.0}
            
        norm_dist = distance / max_len
        # Convert distance to similarity score
        score = 1.0 - (norm_dist / 100.0) # heuristic normalization
        score = max(0.0, min(1.0, score))
        
        return {
            "match": score >= threshold,
            "score": float(score),
            "distance": float(distance),
            "path_length": len(path)
        }
