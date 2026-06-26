"""
Unified Asset Verifier — Content DNA Apex v7.1
FIX 24: Rewritten to match the call signature used in main.py:
    verifier = AssetVerifier(public_key_resolver=db_key_resolver)
    ver_res = await verifier.verify_any(media_bytes)
    # ver_res.valid, ver_res.metadata, ver_res.proof_chain,
    # ver_res.layers_detected, ver_res.reason
"""
import io
import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Optional
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Unified result returned by AssetVerifier.verify_any()."""
    valid: bool
    metadata: dict = field(default_factory=dict)
    proof_chain: list = field(default_factory=list)
    layers_detected: list = field(default_factory=list)
    reason: str = ""


class AssetVerifier:
    """
    Multi-layer asset verifier.

    Layer 1: DCT watermark extraction
    Layer 2: FAISS fingerprint search

    Compatible with both the async main.py endpoint and the legacy
    sync background_tasks pipeline (called via asyncio.run).
    """

    def __init__(self, public_key_resolver: Callable = None, aes_key: bytes = None):
        """
        Args:
            public_key_resolver: Async callable (org_id: str) -> str (PEM key).
            aes_key: Legacy parameter — kept for backward compat, not used.
        """
        self.key_resolver = public_key_resolver
        # aes_key kept for backward compat but not used in v7.1

    async def verify_any(self, media_bytes: bytes) -> VerificationResult:
        """
        Attempts to verify an asset across multiple forensic layers.
        Returns VerificationResult with valid flag, metadata, proof_chain, etc.
        """
        layers: list = []
        proof: list = []

        # ── Layer 1: DCT Watermark ────────────────────────────────────────────
        try:
            from watermark.dct_extract import extract_watermark
            wm = extract_watermark(media_bytes)
            if wm and wm.get("asset_id"):
                layers.append("DCT_WATERMARK")
                proof.append(f"Watermark hit: asset_id={wm['asset_id']}")
                return VerificationResult(
                    valid=True,
                    metadata={
                        "asset_id": wm.get("asset_id", ""),
                        "org_name": wm.get("org_name", ""),
                        "registered_at": wm.get("registered_at", ""),
                    },
                    proof_chain=proof,
                    layers_detected=layers
                )
        except Exception as e:
            proof.append(f"DCT watermark check error: {e}")
            logger.debug("[AssetVerifier] DCT layer error: %s", e)

        # ── Layer 2: FAISS Fingerprint ────────────────────────────────────────
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor
            from config import settings
            from detection.faiss_index import FAISSIndex

            img = Image.open(io.BytesIO(media_bytes)).convert("RGB")
            model = CLIPModel.from_pretrained(settings.CLIP_MODEL)
            processor = CLIPProcessor.from_pretrained(settings.CLIP_MODEL)
            inputs = processor(images=img, return_tensors="pt")
            with torch.no_grad():
                vec = model.get_image_features(**inputs)[0].cpu().numpy().astype(np.float32)

            faiss_idx = FAISSIndex()
            matches = faiss_idx.search(vec, k=1)
            if matches and matches[0].get("score", 0) >= settings.MATCH_THRESHOLD:
                best = matches[0]
                layers.append("FAISS_FINGERPRINT")
                proof.append(f"FAISS match: score={best['score']:.4f}")
                return VerificationResult(
                    valid=True,
                    metadata={
                        "asset_id": best.get("asset_id", ""),
                        "org_name": best.get("org_name", ""),
                        "registered_at": best.get("registered_at", ""),
                    },
                    proof_chain=proof,
                    layers_detected=layers
                )
        except Exception as e:
            proof.append(f"FAISS check error: {e}")
            logger.debug("[AssetVerifier] FAISS layer error: %s", e)

        return VerificationResult(
            valid=False,
            reason="No watermark or fingerprint match found",
            layers_detected=layers,
            proof_chain=proof
        )
