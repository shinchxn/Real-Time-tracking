"""
SDNA Binary Writer — Content DNA Apex v7.0
Implements the full binary serialization for the .sdna container format.
"""
import struct
import uuid
import time
import hashlib
from typing import Dict, List, Optional, Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes

from formats.sdna_spec import (
    SDNA_MAGIC, SDNA_VERSION, SDNA_EOF_MARKER,
    FLAG_ENCRYPTED, FLAG_WATERMARKED, FLAG_SIGNED, FLAG_TAMPER_EVIDENT, FLAG_EMBARGO_ACTIVE,
    DNA_LAYERS, CUSTODY_REGISTERED
)

class SDNAWriter:
    def __init__(self, org_private_key: Optional[ec.EllipticCurvePrivateKey] = None, 
                 org_aes_key: Optional[bytes] = None, 
                 pubkey_fingerprint: Optional[bytes] = None,
                 org_name: str = "Unknown"):
        self.private_key = org_private_key
        self.aes_key = org_aes_key
        self.pubkey_fingerprint = pubkey_fingerprint or b'\x00' * 32
        self.org_name = org_name

    def pack(self, image_bytes: bytes, asset_uuid: str, org_uuid: str, dna_vectors: dict,
             watermark_seed: int, watermark_payload: bytes,
             image_format: int,
             embargo_until: int = 0, existing_custody: list = None) -> bytes:
        """
        Full .sdna container packer.
        """
        flags = 0
        if self.aes_key: flags |= FLAG_ENCRYPTED
        if watermark_payload: flags |= FLAG_WATERMARKED
        if self.private_key: flags |= FLAG_SIGNED
        if existing_custody or True: flags |= FLAG_TAMPER_EVIDENT
        if embargo_until > time.time_ns(): flags |= FLAG_EMBARGO_ACTIVE

        # 1. Identity Block
        asset_uid_bytes = uuid.UUID(asset_uuid).bytes
        org_uid_bytes = uuid.UUID(org_uuid).bytes
        signed_at = time.time_ns()
        org_name_bytes = self.org_name.encode('utf-8')
        
        identity_block = struct.pack(
            ">16s16sQQ32sH",
            asset_uid_bytes,
            org_uid_bytes,
            signed_at,
            embargo_until,
            self.pubkey_fingerprint,
            len(org_name_bytes)
        ) + org_name_bytes

        # 2. DNA Block
        dna_payload = b''
        for layer in DNA_LAYERS:
            vec = dna_vectors.get(layer)
            if vec is not None:
                import numpy as np
                data = np.array(vec, dtype=np.float32).tobytes()
                dna_payload += struct.pack(">I", len(data)) + data
            else:
                dna_payload += struct.pack(">I", 0)

        dna_vector_hash = hashlib.sha3_256(dna_payload).digest()
        
        nonce = b'\x00' * 12
        tag = b'\x00' * 16
        dna_encrypted = dna_payload
        
        if self.aes_key:
            aesgcm = AESGCM(self.aes_key)
            nonce = AESGCM.generate_nonce()
            # AAD = Identity Block
            dna_encrypted_with_tag = aesgcm.encrypt(nonce, dna_payload, identity_block)
            dna_encrypted = dna_encrypted_with_tag[:-16]
            tag = dna_encrypted_with_tag[-16:]

        # 3. Crypto Block Prep (Hash Image)
        image_hash = hashlib.sha3_256(image_bytes).digest()
        
        signature = b'\x00' * 64
        if self.private_key:
            # Signs SHA3-256 of (MAGIC + IDENTITY_BLOCK + IMAGE_HASH + DNA_VECTOR_HASH)
            sign_payload = SDNA_MAGIC + identity_block + image_hash + dna_vector_hash
            signature = self.private_key.sign(sign_payload, ec.ECDSA(hashes.SHA3_256()))
            # Signature might not be exactly 64 bytes (DER vs Raw). 
            # Spec says Raw P-256: r (32) + s (32)
            # cryptography returns DER by default.
            from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
            r, s = decode_dss_signature(signature)
            signature = r.to_bytes(32, 'big') + s.to_bytes(32, 'big')

        crypto_block = struct.pack(">64s32s32s12s16s", signature, image_hash, dna_vector_hash, nonce, tag)

        # 4. Watermark Block
        wm_payload_len = len(watermark_payload)
        watermark_block = struct.pack(">II", watermark_seed, wm_payload_len) + watermark_payload

        # 5. Custody Block
        if existing_custody is None:
            # Initial registration entry
            existing_custody = [{
                "ts_ns": signed_at,
                "event": CUSTODY_REGISTERED,
                "actor": hashlib.md5(org_uid_bytes).digest(), # Simple actor hash
                "prev": b'\x00' * 32
            }]
        
        custody_payload = struct.pack(">I", len(existing_custody))
        for entry in existing_custody:
            custody_payload += struct.pack(">QB16s32s", 
                                          entry["ts_ns"], 
                                          entry["event"], 
                                          entry["actor"], 
                                          entry["prev"])
        
        # 6. Image Block
        image_block = struct.pack(">I Q", image_format, len(image_bytes)) + image_bytes

        # Combine blocks (excluding Checksum)
        header_blocks = identity_block + crypto_block + (struct.pack(">I", len(dna_encrypted)) + dna_encrypted) + watermark_block + custody_payload + image_block
        
        version = SDNA_VERSION
        header_len = len(header_blocks) + 10 # 8 magic + 2 version + 4 header_len + 4 flags is the fixed part? 
        # Wait, spec says: 0-8 MAGIC, 8-2 VERSION, 10-4 HEADER_LEN, 14-4 FLAGS. Total 18 bytes fixed header.
        # HEADER_LENGTH = full file length excluding checksum+EOF
        
        # Recalculate HEADER_LEN to include itself and flags? "full file length excluding checksum+EOF"
        # Total fixed header is 18 bytes.
        # header_blocks starts at offset 18.
        # file_hash and EOF follow.
        
        total_len_before_checksum = 18 + len(header_blocks)
        
        fixed_header = struct.pack(">8sHII", SDNA_MAGIC, version, total_len_before_checksum, flags)
        
        full_content_so_far = fixed_header + header_blocks
        
        # 7. Checksum Block
        file_hash = hashlib.sha3_256(full_content_so_far).digest()
        checksum_block = file_hash + SDNA_EOF_MARKER
        
        return full_content_so_far + checksum_block
