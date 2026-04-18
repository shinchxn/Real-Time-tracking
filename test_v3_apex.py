"""
Verification script for Content DNA v3 Apex Edition.
Tests 6-layer extraction, platform simulation, and ZK-proof generation.
"""
import asyncio
import numpy as np
from PIL import Image
import os

from fingerprint.dct_freq import extract_dct_frequency_signature
from fingerprint.spatial_attention import extract_clip_spatial_attention
from detection.platform_simulator import simulate_instagram
from detection.zk_proofs import ProofManager
from config import settings

async def test_v3_forensics():
    print("--- Content DNA v3 Apex Forensics Test ---")
    
    # 1. Create dummy image
    img = Image.fromarray(np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8))
    
    # 2. Test DCT Frequency Signature (Layer 5)
    dct_sig = extract_dct_frequency_signature(img)
    print(f"✓ DCT Signature extracted: shape {dct_sig.shape}")
    
    # 3. Test CLIP Spatial Attention (Layer 6)
    spatial_sig = await extract_clip_spatial_attention(img, device="cpu")
    print(f"✓ Spatial Attention extracted: shape {spatial_sig.shape}")
    
    # 4. Test Platform Simulator
    insta_img = simulate_instagram(img)
    print(f"✓ Instagram Transform Simulated: {insta_img.size}")
    
    # 5. Test ZK-Proof Generation
    pm = ProofManager("./data/proofs_test")
    dna_mock = {"clip": [0.1]*768, "dct": dct_sig.tolist()}
    proof = pm.generate_ownership_proof("test_asset_1", dna_mock, "owner_123")
    print(f"✓ ZK-Proof Generated: Commitment={proof['commitment'][:16]}...")
    
    # Verify Proof
    with open(os.path.join("./data/proofs_test", "authority.pem"), "rb") as f:
        from cryptography.hazmat.primitives import serialization
        key = serialization.load_pem_private_key(f.read(), password=None)
        pub_key = key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        
    is_valid = pm.verify_proof(proof, pub_key)
    print(f"✓ Cryptographic Proof Verification: {'PASS' if is_valid else 'FAIL'}")

if __name__ == "__main__":
    asyncio.run(test_v3_forensics())
