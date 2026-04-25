import asyncio
from PIL import Image
import numpy as np

# Import extractors
from fingerprint.clip_embedder import extract_clip_embedding
from fingerprint.spatial_attention import extract_spatial_attention
from fingerprint.dct_frequency import extract_dct_frequency_signature
from fingerprint.phash_suite import extract_phash_suite
from fingerprint.hog_descriptor import extract_hog_descriptor
from fingerprint.color_moments import extract_color_moments
from fingerprint.fusion import calculate_fusion_score, classify_severity
from detection.faiss_index import ThreeIndexEngine

class DNAData:
    def __init__(self, clip, spatial, dct_freq, phash, hog, color):
        self.clip = clip
        self.spatial = spatial
        self.dct_freq = dct_freq
        self.phash = phash
        self.hog = hog
        self.color = color

async def extract_6_layer_dna(image: Image.Image) -> DNAData:
    """Extracts all 6 layers of DNA simultaneously via asyncio.gather."""
    
    # For blocking extractors, we run them in executor
    loop = asyncio.get_running_loop()
    
    # 1. CLIP Embedding (Async)
    t_clip = asyncio.create_task(extract_clip_embedding(image))
    
    # 2. Spatial Attention (Async)
    t_spatial = asyncio.create_task(extract_spatial_attention(image))
    
    # 3. DCT Frequency
    t_dct = loop.run_in_executor(None, extract_dct_frequency_signature, image)
    
    # 4. pHash Suite
    t_phash = loop.run_in_executor(None, extract_phash_suite, image)
    
    # 5. HOG Descriptor
    t_hog = loop.run_in_executor(None, extract_hog_descriptor, image)
    
    # 6. Color Moments
    t_color = loop.run_in_executor(None, extract_color_moments, image)
    
    results = await asyncio.gather(t_clip, t_spatial, t_dct, t_phash, t_hog, t_color)
    
    return DNAData(
        clip=results[0],
        spatial=results[1],
        dct_freq=results[2],
        phash=results[3],
        hog=results[4],
        color=results[5]
    )

async def detect_violations(dna: DNAData, index_engine: ThreeIndexEngine, supabase_client) -> list:
    """Queries the index, reranks with fusion, returns alerts."""
    candidates = index_engine.search(dna.clip, dna.hog, dna.dct_freq, dna.phash["phash"])
    
    alerts = []
    # Rerank and fuse
    for asset_id in candidates:
        # Fetch target dna from supabase (mocking this call locally)
        target = supabase_client.get_asset_dna(asset_id)
        if not target: continue
        
        # Compute distances
        clip_dist = np.dot(dna.clip, target["clip"]) # Cosine sim for normalized vecs
        spatial_dist = np.dot(dna.spatial, target["spatial"])
        dct_dist = np.dot(dna.dct_freq, target["dct_freq"])
        hog_dist = np.dot(dna.hog, target["hog"])
        color_dist = np.dot(dna.color, target["color"])
        
        from fingerprint.phash_suite import hamming_distance
        phash_dist = hamming_distance(dna.phash["phash"], target["phash"])
        
        score = calculate_fusion_score(clip_dist, spatial_dist, dct_dist, phash_dist, hog_dist, color_dist)
        sev = classify_severity(score)
        
        if sev != "NONE":
            alerts.append({
                "asset_id": asset_id,
                "score": score,
                "severity": sev
            })
            
    # Sort by score descending
    alerts.sort(key=lambda x: x["score"], reverse=True)
    return alerts
