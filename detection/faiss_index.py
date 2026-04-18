"""
FAISS Index Manager — IVFFlat for CLIP (768-d), FlatL2 for HOG+Color.

Features:
    - Periodic persistence to disk (every 5 min).
    - Cold-start rebuild from stored embeddings.
    - Thread-safe add / search operations.
"""
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import faiss
import numpy as np

logger = logging.getLogger(__name__)


class FAISSIndex:
    """Manages the primary CLIP IVFFlat index and secondary HOG/Color FlatL2 index."""

    def __init__(
        self,
        clip_dim: int = 768,
        hog_dim: int = 128,
        color_dim: int = 9,
        dct_dim: int = 128,      # New in v3
        spatial_dim: int = 256,  # New in v3
        nlist: int = 512,
        nprobe: int = 64,
        index_dir: str = "./data/faiss",
    ):
        self.clip_dim = clip_dim
        self.hog_dim = hog_dim
        self.color_dim = color_dim
        self.dct_dim = dct_dim
        self.spatial_dim = spatial_dim
        self.nlist = nlist
        self.nprobe = nprobe
        self.index_dir = index_dir
        os.makedirs(index_dir, exist_ok=True)

        self._lock = threading.Lock()

        # Metadata store: faiss_id → { asset_id, phash, dhash, ahash, ... }
        self.metadata: Dict[int, dict] = {}
        self.id_counter: int = 0

        # Vector stores for re-rank
        self.hog_store: Dict[int, np.ndarray] = {}
        self.color_store: Dict[int, np.ndarray] = {}
        self.dct_store: Dict[int, np.ndarray] = {}      # New
        self.spatial_store: Dict[int, np.ndarray] = {}  # New

        # Start with a FlatIP index; upgrade to IVF once trained
        self._clip_index: faiss.Index = faiss.IndexFlatIP(clip_dim)
        self._trained = False

        # Paths
        self._clip_path = os.path.join(index_dir, "clip_ivf.index")
        self._meta_path = os.path.join(index_dir, "metadata.json")
        self._hog_path = os.path.join(index_dir, "hog_store.npy")
        self._color_path = os.path.join(index_dir, "color_store.npy")
        self._dct_path = os.path.join(index_dir, "dct_store.npy")
        self._spatial_path = os.path.join(index_dir, "spatial_store.npy")

        # Persistence thread
        self._persist_stop = threading.Event()
        self._persist_thread: Optional[threading.Thread] = None

    # ── Lifecycle ────────────────────────────────────────────────────

    def load(self) -> None:
        """Load persisted index + metadata from disk."""
        with self._lock:
            if os.path.exists(self._clip_path):
                self._clip_index = faiss.read_index(self._clip_path)
                if hasattr(self._clip_index, "nprobe"):
                    self._clip_index.nprobe = self.nprobe
                self._trained = True
                logger.info("Loaded CLIP index (%d vectors)", self._clip_index.ntotal)

            if os.path.exists(self._meta_path):
                with open(self._meta_path, "r") as f:
                    raw = json.load(f)
                self.metadata = {int(k): v for k, v in raw.items()}
                self.id_counter = (max(self.metadata.keys()) + 1) if self.metadata else 0
                logger.info("Loaded metadata (%d entries)", len(self.metadata))

            # Helper for loading stores
            def _load_store(path):
                if os.path.exists(path):
                    arr = np.load(path, allow_pickle=True).item()
                    return {int(k): v for k, v in arr.items()}
                return {}

            self.hog_store = _load_store(self._hog_path)
            self.color_store = _load_store(self._color_path)
            self.dct_store = _load_store(self._dct_path)
            self.spatial_store = _load_store(self._spatial_path)

    def save(self) -> None:
        """Persist index + metadata to disk."""
        with self._lock:
            faiss.write_index(self._clip_index, self._clip_path)
            with open(self._meta_path, "w") as f:
                json.dump({str(k): v for k, v in self.metadata.items()}, f)
            np.save(self._hog_path, self.hog_store)
            np.save(self._color_path, self.color_store)
            np.save(self._dct_path, self.dct_store)
            np.save(self._spatial_path, self.spatial_store)
        logger.info("FAISS index persisted to %s", self.index_dir)

    def start_periodic_persist(self, interval: int = 300) -> None:
        """Start a background thread that persists every `interval` seconds."""
        def _loop():
            while not self._persist_stop.wait(timeout=interval):
                try:
                    self.save()
                except Exception:
                    logger.exception("Periodic persist failed")

        self._persist_thread = threading.Thread(target=_loop, daemon=True)
        self._persist_thread.start()
        logger.info("Periodic persist started (every %ds)", interval)

    def stop_periodic_persist(self) -> None:
        self._persist_stop.set()
        if self._persist_thread:
            self._persist_thread.join(timeout=5)

    # ── Add ──────────────────────────────────────────────────────────

    def _maybe_upgrade_to_ivf(self) -> None:
        """
        Upgrade the Flat index to IVF once we have enough vectors.
        Requires at least nlist vectors to train.
        """
        if self._trained:
            return
        n = self._clip_index.ntotal
        if n < self.nlist:
            return

        logger.info("Training IVFFlat index with %d vectors (nlist=%d)", n, self.nlist)
        quantizer = faiss.IndexFlatIP(self.clip_dim)
        ivf_index = faiss.IndexIVFFlat(
            quantizer, self.clip_dim, self.nlist, faiss.METRIC_INNER_PRODUCT,
        )

        # Reconstruct all vectors from Flat
        all_vecs = np.zeros((n, self.clip_dim), dtype=np.float32)
        for i in range(n):
            all_vecs[i] = self._clip_index.reconstruct(i)

        ivf_index.train(all_vecs)
        ivf_index.add(all_vecs)
        ivf_index.nprobe = self.nprobe

        self._clip_index = ivf_index
        self._trained = True
        logger.info("IVFFlat index trained and populated with %d vectors", n)

    def add(
        self,
        clip_vec: np.ndarray,
        hog_vec: np.ndarray,
        color_vec: np.ndarray,
        dct_vec: np.ndarray,      # v3
        spatial_vec: np.ndarray,  # v3
        asset_id: str,
        phash: str,
        dhash: str,
        ahash: str,
        extra_meta: Optional[dict] = None,
    ) -> int:
        """Add a new asset to all indices. Returns the internal index ID."""
        clip_vec = clip_vec.astype(np.float32).reshape(1, -1)

        with self._lock:
            idx = self.id_counter
            self._clip_index.add(clip_vec)
            self.hog_store[idx] = hog_vec.astype(np.float32)
            self.color_store[idx] = color_vec.astype(np.float32)
            self.dct_store[idx] = dct_vec.astype(np.float32)
            self.spatial_store[idx] = spatial_vec.astype(np.float32)
            self.metadata[idx] = {
                "asset_id": asset_id,
                "phash": phash,
                "dhash": dhash,
                "ahash": ahash,
                **(extra_meta or {}),
            }
            self.id_counter += 1

        # Try to upgrade to IVF after enough vectors accumulate
        self._maybe_upgrade_to_ivf()
        return idx

    # ── Search ───────────────────────────────────────────────────────

    def search_clip(self, query_vec: np.ndarray, k: int = 20) -> List[Tuple[int, float]]:
        """
        Search CLIP index — returns list of (index_id, inner_product_score).
        """
        if self._clip_index.ntotal == 0:
            return []

        query_vec = query_vec.astype(np.float32).reshape(1, -1)
        actual_k = min(k, self._clip_index.ntotal)

        with self._lock:
            scores, indices = self._clip_index.search(query_vec, actual_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            results.append((int(idx), float(score)))
        return results

    def get_vectors(self, idx: int) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """Return (hog_vec, color_vec, dct_vec, spatial_vec) for the given index id."""
        return (
            self.hog_store.get(idx),
            self.color_store.get(idx),
            self.dct_store.get(idx),
            self.spatial_store.get(idx)
        )

    def get_metadata(self, idx: int) -> Optional[dict]:
        return self.metadata.get(idx)

    def get_clip_vector(self, idx: int) -> Optional[np.ndarray]:
        """Reconstruct a CLIP vector from the index."""
        try:
            with self._lock:
                return self._clip_index.reconstruct(idx).astype(np.float32)
        except Exception:
            return None

    # ── Stats ────────────────────────────────────────────────────────

    @property
    def total_vectors(self) -> int:
        return self._clip_index.ntotal

    def get_stats(self) -> dict:
        return {
            "clip_vectors": self._clip_index.ntotal,
            "hog_entries": len(self.hog_store),
            "color_entries": len(self.color_store),
            "metadata_entries": len(self.metadata),
            "ivf_trained": self._trained,
        }
