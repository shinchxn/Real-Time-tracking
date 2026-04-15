"""
Vector Database: FAISS-based similarity search for embeddings
"""
import json
import numpy as np
import faiss
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)


class VectorDatabase:
    """FAISS-based vector database for embeddings"""
    
    def __init__(self, embedding_dim: int = 512):
        """
        Initialize FAISS index
        
        Args:
            embedding_dim: Dimension of embeddings (CLIP ViT-B/32 = 512)
        """
        self.embedding_dim = embedding_dim
        self.index = faiss.IndexFlatL2(embedding_dim)  # L2 distance (Euclidean)
        self.metadata = {}
        self.id_counter = 0
        
    def add_embedding(
        self,
        embedding: np.ndarray,
        asset_id: str,
        filename: str,
        phash: str,
        metadata: dict
    ) -> int:
        """
        Add embedding to index
        
        Args:
            embedding: 1D numpy array of shape (embedding_dim,)
            asset_id: Unique identifier for asset
            filename: Original filename
            phash: Perceptual hash
            metadata: Additional metadata dict
            
        Returns:
            int: Assigned index ID
        """
        # Ensure embedding is float32 and right shape
        embedding = embedding.astype(np.float32).reshape(1, -1)
        
        # Add to FAISS index
        self.index.add(embedding)
        
        # Store metadata
        idx_id = self.id_counter
        self.metadata[idx_id] = {
            'asset_id': asset_id,
            'filename': filename,
            'phash': phash,
            'added_timestamp': datetime.utcnow().isoformat(),
            **metadata
        }
        
        self.id_counter += 1
        logger.info(f"Added embedding to index: {filename} (idx={idx_id})")
        
        return idx_id
    
    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 5
    ) -> List[Dict]:
        """
        Search for similar embeddings
        
        Args:
            query_embedding: 1D numpy array of shape (embedding_dim,)
            k: Number of results to return
            
        Returns:
            List of dicts:
                {
                    'index_id': int,
                    'l2_distance': float,
                    'similarity_score': float (0-1, normalized),
                    'asset_id': str,
                    'filename': str,
                    'phash': str,
                    'metadata': dict
                }
        """
        if self.index.ntotal == 0:
            return []
        
        # Ensure query is float32
        query_embedding = query_embedding.astype(np.float32).reshape(1, -1)
        
        # Normalize query (cosine similarity)
        query_embedding = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        
        # Search
        distances, indices = self.index.search(query_embedding, min(k, self.index.ntotal))
        
        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx == -1:  # Invalid index
                continue
            
            # Convert L2 distance to similarity score (0-1)
            # For normalized vectors: similarity = 1 - (distance / 2)
            # or: similarity = 1 - distance^2 / 2
            similarity = 1.0 / (1.0 + dist)  # Alternative: sigmoid-like
            
            meta = self.metadata.get(idx, {})
            results.append({
                'index_id': int(idx),
                'l2_distance': float(dist),
                'similarity_score': float(similarity),
                'asset_id': meta.get('asset_id'),
                'filename': meta.get('filename'),
                'phash': meta.get('phash'),
                'metadata': meta
            })
        
        return results
    
    def save(self, index_path: str, metadata_path: str) -> None:
        """
        Save index and metadata to disk
        
        Args:
            index_path: Path to save FAISS index
            metadata_path: Path to save metadata JSON
        """
        Path(index_path).parent.mkdir(parents=True, exist_ok=True)
        Path(metadata_path).parent.mkdir(parents=True, exist_ok=True)
        
        faiss.write_index(self.index, index_path)
        with open(metadata_path, 'w') as f:
            json.dump(self.metadata, f, indent=2)
        
        logger.info(f"Saved FAISS index to {index_path}")
        logger.info(f"Saved metadata to {metadata_path}")
    
    def load(self, index_path: str, metadata_path: str) -> None:
        """
        Load index and metadata from disk
        
        Args:
            index_path: Path to load FAISS index
            metadata_path: Path to load metadata JSON
        """
        if Path(index_path).exists():
            self.index = faiss.read_index(index_path)
            logger.info(f"Loaded FAISS index from {index_path}")
        
        if Path(metadata_path).exists():
            with open(metadata_path, 'r') as f:
                loaded_meta = json.load(f)
                # Convert string keys back to int
                self.metadata = {int(k): v for k, v in loaded_meta.items()}
                self.id_counter = max(int(k) for k in loaded_meta.keys()) + 1 if loaded_meta else 0
            logger.info(f"Loaded metadata from {metadata_path}")
    
    def delete(self, asset_id: str) -> bool:
        """
        Delete asset by asset_id (marks metadata, doesn't rebuild index)
        
        Args:
            asset_id: Asset identifier
            
        Returns:
            bool: True if found and deleted
        """
        for idx, meta in list(self.metadata.items()):
            if meta.get('asset_id') == asset_id:
                del self.metadata[idx]
                logger.info(f"Deleted asset {asset_id} from metadata")
                return True
        return False
    
    def get_stats(self) -> dict:
        """Get database statistics"""
        return {
            'total_embeddings': self.index.ntotal,
            'embedding_dim': self.embedding_dim,
            'metadata_entries': len(self.metadata),
            'id_counter': self.id_counter
        }
