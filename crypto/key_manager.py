"""
Cryptographic Key Manager — Content DNA Apex v7.0
Handles ECDSA P-256 keypair generation, encrypted storage, and rotation.
"""
import os
import hashlib
from typing import Tuple, Optional
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

from storage.db_client import get_pool # For DB interaction if needed here, but usually handled in API layer

class KeyManager:
    def __init__(self, master_key_hex: Optional[str] = None):
        master_key_hex = master_key_hex or os.getenv("MASTER_ENCRYPTION_KEY")
        if not master_key_hex:
            # Fallback for development (NOT for production)
            logger.warning("MASTER_ENCRYPTION_KEY not set. Using insecure default.")
            master_key_hex = "0" * 64
        self.master_key = bytes.fromhex(master_key_hex)

    def generate_org_keypair(self, org_id: str) -> Tuple[bytes, str]:
        """
        Generate a new ECDSA P-256 keypair for an organization.
        Returns (encrypted_private_key, public_key_pem).
        """
        private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        public_key = private_key.public_key()

        # Serialize Private Key
        priv_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        # Encrypt Private Key with AES-256-GCM
        aesgcm = AESGCM(self.master_key)
        nonce = AESGCM.generate_nonce()
        # AAD can be org_id
        encrypted_priv = aesgcm.encrypt(nonce, priv_bytes, org_id.encode())
        full_encrypted = nonce + encrypted_priv

        # Serialize Public Key
        pub_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

        return full_encrypted, pub_pem

    def load_private_key(self, org_id: str, encrypted_priv: bytes) -> ec.EllipticCurvePrivateKey:
        """
        Decrypt and load a private key from its encrypted form.
        """
        nonce = encrypted_priv[:12]
        ciphertext = encrypted_priv[12:]
        
        aesgcm = AESGCM(self.master_key)
        priv_bytes = aesgcm.decrypt(nonce, ciphertext, org_id.encode())
        
        return serialization.load_pem_private_key(
            priv_bytes,
            password=None,
            backend=default_backend()
        )

    def get_public_key_fingerprint(self, public_key_pem: str) -> bytes:
        """
        Returns SHA3-256 of the DER-encoded public key.
        """
        pub_key = serialization.load_pem_public_key(
            public_key_pem.encode('utf-8'),
            backend=default_backend()
        )
        der_bytes = pub_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return hashlib.sha3_256(der_bytes).digest()

# ── Module Level Wrappers ───────────────────────────────────────────────────

_km = None

def _get_km():
    global _km
    if _km is None:
        _km = KeyManager()
    return _km

def generate_org_keypair(org_id: str):
    return _get_km().generate_org_keypair(org_id)

def load_private_key(org_id: str):
    # This needs to fetch from DB first or be passed the encrypted bytes
    # For the caller in sdna_converter, we might need a way to get it.
    # We'll assume the caller fetches the encrypted bytes from the DB.
    raise NotImplementedError("Use load_private_key_with_data")

def load_private_key_with_data(org_id: str, encrypted_priv: bytes):
    return _get_km().load_private_key(org_id, encrypted_priv)

def get_public_key_fingerprint(public_key_pem: str):
    return _get_km().get_public_key_fingerprint(public_key_pem)
