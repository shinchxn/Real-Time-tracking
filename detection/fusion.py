"""
Fusion Score — Weighted multi-layer similarity.

    score = 0.55 × cosine(clip_vec)
          + 0.25 × (1 − hamming_norm(pHash))
          + 0.12 × cosine(color_moment)
          + 0.08 × cosine(hog_descriptor)
"""
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

from fingerprint.phash import hamming_normalised

logger = logging.getLogger(__name__)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors (both assumed non-zero)."""
    dot = float(np.dot(a, b))
    na = float(np.linalg.norm(a)) + 1e-8
    nb = float(np.linalg.norm(b)) + 1e-8
    return dot / (na * nb)


@dataclass
class FusionResult:
    """Result of multi-layer fusion scoring."""
    fusion_score: float
    clip_score: float
    phash_score: float
    color_score: float
    hog_score: float
    dct_score: float      # v3
    spatial_score: float  # v3
    severity: str         # CRITICAL | HIGH | MEDIUM | MISS
    candidate_asset_id: str
    candidate_index_id: int


def compute_fusion_score(
    query_clip: np.ndarray,
    query_phash: str,
    query_color: np.ndarray,
    query_hog: np.ndarray,
    query_dct: np.ndarray,      # v3
    query_spatial: np.ndarray,  # v3
    cand_clip: np.ndarray,
    cand_phash: str,
    cand_color: np.ndarray,
    cand_hog: np.ndarray,
    cand_dct: np.ndarray,       # v3
    cand_spatial: np.ndarray,   # v3
    cand_asset_id: str,
    cand_index_id: int,
    w_clip: float = 0.40,
    w_phash: float = 0.15,
    w_color: float = 0.10,
    w_hog: float = 0.05,
    w_dct: float = 0.15,        # v3
    w_spatial: float = 0.15,    # v3
    t_critical: float = 0.96,
    t_high: float = 0.88,
    t_medium: float = 0.75,
) -> FusionResult:
    """
    Compute weighted fusion score between a query and one candidate.
    """
    clip_sim = _cosine(query_clip, cand_clip)
    phash_sim = 1.0 - hamming_normalised(query_phash, cand_phash, bits=64)
    color_sim = _cosine(query_color, cand_color)
    hog_sim = _cosine(query_hog, cand_hog)
    dct_sim = _cosine(query_dct, cand_dct)          # v3
    spatial_sim = _cosine(query_spatial, cand_spatial) # v3

    score = (
        w_clip * clip_sim
        + w_phash * phash_sim
        + w_color * color_sim
        + w_hog * hog_sim
        + w_dct * dct_sim
        + w_spatial * spatial_sim
    )

    if score >= t_critical:
        severity = "CRITICAL"
    elif score >= t_high:
        severity = "HIGH"
    elif score >= t_medium:
        severity = "MEDIUM"
    else:
        severity = "MISS"

    return FusionResult(
        fusion_score=float(score),
        clip_score=float(clip_sim),
        phash_score=float(phash_sim),
        color_score=float(color_sim),
        hog_score=float(hog_sim),
        dct_score=float(dct_sim),
        spatial_score=float(spatial_sim),
        severity=severity,
        candidate_asset_id=cand_asset_id,
        candidate_index_id=cand_index_id,
    )


def classify_severity(
    score: float,
    t_critical: float = 0.94,
    t_high: float = 0.85,
    t_medium: float = 0.72,
) -> str:
    """Map a fusion score to a severity label."""
    if score >= t_critical:
        return "CRITICAL"
    elif score >= t_high:
        return "HIGH"
    elif score >= t_medium:
        return "MEDIUM"
    return "MISS"
