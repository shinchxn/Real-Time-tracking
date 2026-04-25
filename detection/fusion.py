"""
Fusion Score — Content DNA Apex v6.0
Weighted multi-layer similarity with sports-specific embargo-aware severity boost.

Score = 0.40 × cosine(CLIP)
      + 0.15 × (1 − hamming_norm(pHash))
      + 0.15 × cosine(DCT_freq)
      + 0.15 × cosine(spatial)
      + 0.10 × cosine(color_moment)
      + 0.05 × cosine(HOG)

Embargo rule: if now < embargo_until → severity upgraded one level.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
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


# ── Severity ladder ───────────────────────────────────────────────────────────
_SEVERITY_LADDER = ["MISS", "LOW", "MEDIUM", "HIGH", "CRITICAL"]


def _upgrade_severity(severity: str) -> str:
    """Upgrade severity by one level (MEDIUM → HIGH, HIGH → CRITICAL, etc.)."""
    try:
        idx = _SEVERITY_LADDER.index(severity)
        return _SEVERITY_LADDER[min(idx + 1, len(_SEVERITY_LADDER) - 1)]
    except ValueError:
        return severity


def _is_within_embargo(embargo_until: Optional[str]) -> bool:
    """Return True if current UTC time is before the embargo deadline."""
    if not embargo_until:
        return False
    try:
        deadline = datetime.fromisoformat(
            embargo_until.rstrip("Z")
        ).replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < deadline
    except (ValueError, AttributeError):
        return False


# ── Data classes ──────────────────────────────────────────────────────────────
@dataclass
class FusionResult:
    """Result of multi-layer fusion scoring — v6.0."""
    fusion_score: float
    clip_score: float
    phash_score: float
    color_score: float
    hog_score: float
    dct_score: float
    spatial_score: float
    severity: str             # CRITICAL | HIGH | MEDIUM | LOW | MISS
    candidate_asset_id: str
    candidate_index_id: int
    embargo_violation: bool = False  # True if detected within embargo window
    original_severity: str = ""     # Severity before embargo boost


# ── Main fusion function ──────────────────────────────────────────────────────
def compute_fusion_score(
    query_clip: np.ndarray,
    query_phash: str,
    query_color: np.ndarray,
    query_hog: np.ndarray,
    query_dct: np.ndarray,
    query_spatial: np.ndarray,
    cand_clip: np.ndarray,
    cand_phash: str,
    cand_color: np.ndarray,
    cand_hog: np.ndarray,
    cand_dct: np.ndarray,
    cand_spatial: np.ndarray,
    cand_asset_id: str,
    cand_index_id: int,
    w_clip: float = 0.40,
    w_phash: float = 0.15,
    w_color: float = 0.10,
    w_hog: float = 0.05,
    w_dct: float = 0.15,
    w_spatial: float = 0.15,
    t_critical: float = 0.96,
    t_high: float = 0.88,
    t_medium: float = 0.75,
    # Sports metadata (optional) ─────────────────────────────────────────────
    embargo_until: Optional[str] = None,
    broadcast_window: Optional[str] = None,
) -> FusionResult:
    """
    Compute weighted fusion score between a query and one candidate.

    Sports-specific behaviour (v6.0):
    - If embargo_until is set and now < embargo_until:
        → severity is upgraded one level (MEDIUM→HIGH, HIGH→CRITICAL)
        → embargo_violation flag is set to True on the result
    """
    # ── Per-layer similarities ────────────────────────────────────────────────
    clip_sim    = _cosine(query_clip, cand_clip)
    phash_sim   = 1.0 - hamming_normalised(query_phash, cand_phash, bits=64)
    color_sim   = _cosine(query_color, cand_color)
    hog_sim     = _cosine(query_hog, cand_hog)
    dct_sim     = _cosine(query_dct, cand_dct)
    spatial_sim = _cosine(query_spatial, cand_spatial)

    # ── Weighted sum ──────────────────────────────────────────────────────────
    score = (
        w_clip    * clip_sim
        + w_phash * phash_sim
        + w_color * color_sim
        + w_hog   * hog_sim
        + w_dct   * dct_sim
        + w_spatial * spatial_sim
    )

    # ── Base severity ─────────────────────────────────────────────────────────
    if score >= t_critical:
        severity = "CRITICAL"
    elif score >= t_high:
        severity = "HIGH"
    elif score >= t_medium:
        severity = "MEDIUM"
    else:
        severity = "MISS"

    original_severity = severity
    embargo_violation = False

    # ── Embargo boost (Phase 7) ───────────────────────────────────────────────
    if severity != "MISS" and _is_within_embargo(embargo_until):
        boosted = _upgrade_severity(severity)
        if boosted != severity:
            logger.info(
                "[Fusion] Embargo boost: %s → %s (asset=%s, embargo_until=%s)",
                severity, boosted, cand_asset_id, embargo_until
            )
            severity = boosted
            embargo_violation = True

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
        embargo_violation=embargo_violation,
        original_severity=original_severity,
    )


def classify_severity(
    score: float,
    t_critical: float = 0.94,
    t_high: float = 0.85,
    t_medium: float = 0.72,
) -> str:
    """Map a fusion score to a severity label (no embargo logic — raw score only)."""
    if score >= t_critical:
        return "CRITICAL"
    elif score >= t_high:
        return "HIGH"
    elif score >= t_medium:
        return "MEDIUM"
    return "MISS"
