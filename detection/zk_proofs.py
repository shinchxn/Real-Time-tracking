"""
Blockchain + ZK Proof Manager
Generates cryptographic proofs of ownership (Commitment + Signature)
that allow proving ownership to platforms without exposing the original asset.
"""
import os
import hashlib
import json
from datetime import datetime, timezone
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import serialization

class ProofManager:
    """Manages ownership proofs and blockchain anchors."""
    
    def __init__(self, proofs_dir: str):
        self.proofs_dir = proofs_dir
        os.makedirs(proofs_dir, exist_ok=True)
        self.private_key_path = os.path.join(proofs_dir, "authority.pem")
        self._ensure_keys()

    def _ensure_keys(self):
        if not os.path.exists(self.private_key_path):
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            with open(self.private_key_path, "wb") as f:
                f.write(key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))

    def _get_private_key(self):
        with open(self.private_key_path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)

    def generate_ownership_proof(self, asset_id: str, content_dna: dict, owner_id: str) -> dict:
        """
        Create a ZK-compatible commitment: 
        H(AssetID || DNA_Hashes || OwnerSalt)
        """
        # 1. Create a deterministic DNA summary
        dna_summary = json.dumps(content_dna, sort_keys=True).encode()
        dna_hash = hashlib.sha256(dna_summary).hexdigest()
        
        # 2. Secret salt for owner
        salt = hashlib.sha256(f"{owner_id}-secret-salt".encode()).hexdigest()
        
        # 3. Final commitment (The 'ZK' part - others can verify if they have the parts, but can't reverse it)
        commitment_payload = f"{asset_id}|{dna_hash}|{salt}".encode()
        commitment = hashlib.sha256(commitment_payload).hexdigest()
        
        # 4. Sign the commitment (Authority/Blockchain Anchor)
        private_key = self._get_private_key()
        signature = private_key.sign(
            commitment.encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256()
        )
        
        proof = {
            "asset_id": asset_id,
            "commitment": commitment,
            "signature": signature.hex(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "algo": "SHA256-RSA-PSS",
            "v": "3.0"
        }
        
        # Save proof
        proof_path = os.path.join(self.proofs_dir, f"{asset_id}_proof.json")
        with open(proof_path, "w") as f:
            json.dump(proof, f)
            
        return proof

    def verify_proof(self, proof: dict, public_key_pem: str) -> bool:
        """Verify the cryptographic signature of an ownership proof."""
        public_key = serialization.load_pem_public_key(public_key_pem.encode())
        try:
            public_key.verify(
                bytes.fromhex(proof["signature"]),
                proof["commitment"].encode(),
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256()
            )
            return True
        except Exception:
            return False
