"""
FAISS Index — Content DNA Apex v6.0
Adds: load_or_create() factory, atexit flush hook, SIGTERM handler.
"""
import atexit
import faiss
import numpy as np
import os
import pickle
import signal
import threading
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class FAISSIndex:
    """
    Enterprise-grade FAISS indexing system for Content DNA Apex v6.0.
    Integrates 6-layer DNA forensic tracking with:
      - Periodic persistence thread
      - Guaranteed shutdown flush (atexit + SIGTERM)
      - load_or_create() factory method
    """
    def __init__(
        self,
        clip_dim: int = 768,
        hog_dim: int = 128,
        color_dim: int = 9,
        dct_dim: int = 128,
        spatial_dim: int = 256,
        nlist: int = 512,
        nprobe: int = 64,
        index_dir: str = "data/faiss"
    ):
        self.clip_dim = clip_dim
        self.hog_dim = hog_dim
        self.color_dim = color_dim
        self.dct_dim = dct_dim
        self.spatial_dim = spatial_dim
        self.nlist = nlist
        self.nprobe = nprobe
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        # File paths
        self.index_path = self.index_dir / "clip_v3.index"
        self.meta_path = self.index_dir / "meta_v3.pkl"
        self.vector_store_path = self.index_dir / "vectors_v3.pkl"

        # Build FAISS index (IndexIVFPQ for efficiency at scale)
        quantizer = faiss.IndexFlatIP(clip_dim)
        ivf_index = faiss.IndexIVFPQ(
            quantizer, clip_dim, nlist, 32, 8, faiss.METRIC_INNER_PRODUCT
        )
        ivf_index.nprobe = nprobe
        self.index = faiss.IndexIDMap(ivf_index)

        # Storage
        self.metadata: Dict[int, Any] = {}
        self.clip_store: Dict[int, np.ndarray] = {}
        self.other_vectors: Dict[int, Dict[str, np.ndarray]] = {}

        self.current_id = 0
        self.is_trained = False
        self._lock = threading.Lock()
        self._persist_thread = None
        self._stop_persist = threading.Event()

        # Register shutdown hooks
        atexit.register(self._shutdown_flush)
        try:
            signal.signal(signal.SIGTERM, self._sigterm_handler)
        except (ValueError, OSError):
            pass  # Not in main thread — skip signal handler

    # ── Factory ─────────────────────────────────────────────────────────────

    @classmethod
    def load_or_create(
        cls,
        clip_dim: int = 768,
        hog_dim: int = 128,
        color_dim: int = 9,
        dct_dim: int = 128,
        spatial_dim: int = 256,
        nlist: int = 512,
        nprobe: int = 64,
        index_dir: str = "data/faiss",
    ) -> "FAISSIndex":
        """
        Factory: loads an existing index from disk if available, otherwise
        creates a fresh one. Preferred entry point for all consumers.
        """
        instance = cls(
            clip_dim=clip_dim,
            hog_dim=hog_dim,
            color_dim=color_dim,
            dct_dim=dct_dim,
            spatial_dim=spatial_dim,
            nlist=nlist,
            nprobe=nprobe,
            index_dir=index_dir,
        )
        idx_path = Path(index_dir) / "clip_v3.index"
        if idx_path.exists():
            instance.load()
            logger.info("[FAISS] Loaded existing index (%d vectors)", instance.total_vectors)
        else:
            logger.info("[FAISS] No existing index at %s. Starting fresh.", idx_path)
        return instance

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def total_vectors(self) -> int:
        return self.index.ntotal

    # ── Training ─────────────────────────────────────────────────────────────

    def train(self, samples: np.ndarray):
        """Train the IVFPQ index with sample vectors."""
        if samples.shape[0] < self.nlist:
            logger.warning("Not enough samples to train FAISS index. Need at least %d", self.nlist)
            return

        logger.info("Training FAISS index with %d samples...", samples.shape[0])
        samples = samples.astype(np.float32)
        faiss.normalize_L2(samples)
        self.index.train(samples)
        self.is_trained = True
        logger.info("FAISS training complete.")

    # ── Add ──────────────────────────────────────────────────────────────────

    def add(
        self,
        asset_id: str,
        clip_vec: np.ndarray,
        hog_vec: np.ndarray,
        color_vec: np.ndarray,
        dct_vec: np.ndarray,
        spatial_vec: np.ndarray,
        phash: str,
        metadata: Optional[Dict] = None
    ):
        """Add a new asset to the 6-layer DNA index."""
        with self._lock:
            clip_vec = clip_vec.astype(np.float32)
            if clip_vec.ndim == 1:
                clip_vec = np.expand_dims(clip_vec, 0)
            faiss.normalize_L2(clip_vec)

            if not self.is_trained:
                logger.info("Auto-bootstrapping index training...")
                fake_train = np.random.randn(self.nlist * 39, self.clip_dim).astype(np.float32)
                self.train(fake_train)

            idx_int = int(self.current_id)
            indices = np.array([idx_int], dtype=np.int64)
            self.index.add_with_ids(clip_vec, indices)

            self.metadata[idx_int] = {
                "asset_id": str(asset_id),
                "phash": str(phash),
                **(metadata or {}),
            }
            self.clip_store[idx_int] = clip_vec.flatten()
            self.other_vectors[idx_int] = {
                "hog": hog_vec,
                "color": color_vec,
                "dct": dct_vec,
                "spatial": spatial_vec,
            }
            self.current_id = idx_int + 1
            return idx_int

    # ── Search ───────────────────────────────────────────────────────────────

    def search_clip(self, query_vec: np.ndarray, k: int = 20) -> List[Tuple[int, float]]:
        """Search for candidates using CLIP cosine similarity."""
        if not self.is_trained or self.index.ntotal == 0:
            return []

        query_vec = query_vec.astype(np.float32)
        if query_vec.ndim == 1:
            query_vec = np.expand_dims(query_vec, 0)
        faiss.normalize_L2(query_vec)

        distances, indices = self.index.search(query_vec, k)
        return [
            (int(idx), float(dist))
            for dist, idx in zip(distances[0], indices[0])
            if idx != -1
        ]

    # ── Accessors ────────────────────────────────────────────────────────────

    def get_metadata(self, idx: int) -> Optional[Dict]:
        return self.metadata.get(idx)

    def get_clip_vector(self, idx: int) -> Optional[np.ndarray]:
        return self.clip_store.get(idx)

    def get_vectors(self, idx: int) -> Tuple[Optional[np.ndarray], ...]:
        v = self.other_vectors.get(idx, {})
        return v.get("hog"), v.get("color"), v.get("dct"), v.get("spatial")

    def get_stats(self) -> Dict:
        return {
            "total_vectors": self.total_vectors,
            "trained": self.is_trained,
            "dim": self.clip_dim,
            "index_type": "IVFPQ",
            "index_path": str(self.index_path),
        }

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self):
        """Persist index and metadata to disk (thread-safe)."""
        with self._lock:
            try:
                faiss.write_index(self.index, str(self.index_path))
                with open(self.meta_path, "wb") as f:
                    pickle.dump({
                        "meta": self.metadata,
                        "cur": self.current_id,
                        "trained": self.is_trained,
                    }, f)
                with open(self.vector_store_path, "wb") as f:
                    pickle.dump({
                        "clip": self.clip_store,
                        "others": self.other_vectors,
                    }, f)
                logger.info("[FAISS] Index saved (%d vectors) → %s", self.total_vectors, self.index_dir)
            except Exception as e:
                logger.error("[FAISS] Failed to save index: %s", e)

    def load(self):
        """Load index and metadata from disk."""
        with self._lock:
            if not self.index_path.exists():
                logger.info("[FAISS] No index file at %s. Starting fresh.", self.index_path)
                return
            try:
                self.index = faiss.read_index(str(self.index_path))
                with open(self.meta_path, "rb") as f:
                    d = pickle.load(f)
                    self.metadata = d["meta"]
                    self.current_id = int(d["cur"])
                    self.is_trained = d["trained"]
                if self.vector_store_path.exists():
                    with open(self.vector_store_path, "rb") as f:
                        dv = pickle.load(f)
                        self.clip_store = dv["clip"]
                        self.other_vectors = dv["others"]
                logger.info("[FAISS] Loaded: %d vectors", self.total_vectors)
            except Exception as e:
                logger.error("[FAISS] Failed to load index: %s", e)

    # ── Periodic Persistence Thread ──────────────────────────────────────────

    def start_periodic_persist(self, interval: int = 600):
        """Start a background thread to persist the index every N seconds."""
        if self._persist_thread and self._persist_thread.is_alive():
            return
        self._stop_persist.clear()

        def _persist_loop():
            while not self._stop_persist.wait(interval):
                logger.info("[FAISS] Periodic persist...")
                self.save()

        self._persist_thread = threading.Thread(target=_persist_loop, daemon=True, name="faiss-persist")
        self._persist_thread.start()

    def stop_periodic_persist(self):
        """Stop the background persistence thread."""
        self._stop_persist.set()
        if self._persist_thread:
            self._persist_thread.join(timeout=5)

    # ── Shutdown Hooks ───────────────────────────────────────────────────────

    def _shutdown_flush(self):
        """atexit hook — ensures index is flushed before process exit."""
        logger.info("[FAISS] atexit flush triggered — saving index...")
        try:
            self.stop_periodic_persist()
            self.save()
            logger.info("[FAISS] atexit flush complete.")
        except Exception as e:
            logger.error("[FAISS] atexit flush failed: %s", e)

    def _sigterm_handler(self, signum, frame):
        """SIGTERM handler — flush index before pod termination."""
        logger.info("[FAISS] SIGTERM received — flushing index before shutdown...")
        self._shutdown_flush()
        # Re-raise default SIGTERM behavior
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGTERM)
