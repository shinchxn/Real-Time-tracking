"""
Asset Signer — Content DNA Apex v7.0
Handles ECDSA signing of asset metadata and image hashes.
"""
from dataclasses import dataclass
from typing import Optional
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
import hashlib

@dataclass
class SignedAsset:
    asset_id: str
    org_id: str
    signature: bytes
    image_hash: bytes
    signed_at: int

def sign_asset(image_bytes: bytes, asset_id: str, org_id: str, private_key: ec.EllipticCurvePrivateKey) -> SignedAsset:
    """
    Signs the image hash and basic metadata.
    """
    import time
    signed_at = time.time_ns()
    image_hash = hashlib.sha3_256(image_bytes).digest()
    
    # Payload for signature
    # (asset_id + org_id + image_hash + signed_at)
    payload = f"{asset_id}{org_id}{image_hash.hex()}{signed_at}".encode()
    
    signature = private_key.sign(
        payload,
        ec.ECDSA(hashes.SHA3_256())
    )
    
    return SignedAsset(
        asset_id=asset_id,
        org_id=org_id,
        signature=signature,
        image_hash=image_hash,
        signed_at=signed_at
    )
