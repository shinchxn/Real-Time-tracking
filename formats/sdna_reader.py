"""
SDNA Binary Reader — Content DNA Apex v7.0
Implements parsing, hash verification, and signature verification for .sdna containers.
"""
import struct
import uuid
import hashlib
import io
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from formats.sdna_spec import (
    SDNA_MAGIC, SDNA_VERSION, SDNA_EOF_MARKER,
    FLAG_ENCRYPTED, FLAG_WATERMARKED, FLAG_SIGNED, FLAG_TAMPER_EVIDENT,
    DNA_LAYERS
)

class SDNATampered(Exception):
    """Raised when a hash check or signature check fails."""
    pass

@dataclass
class SDNADocument:
    version: int
    flags: int
    asset_uuid: str
    org_uuid: str
    signed_at: int
    embargo_until: int
    pubkey_fingerprint: bytes
    org_name: str
    
    signature: bytes
    image_hash: bytes
    dna_vector_hash: bytes
    nonce: bytes
    tag: bytes
    
    dna_encrypted: bytes
    watermark_seed: int
    watermark_payload: bytes
    image_format: int
    image_bytes: bytes
    
    # Fields with default values MUST be at the end
    dna_vectors: Dict[str, Any] = field(default_factory=dict)
    custody_entries: List[Dict[str, Any]] = field(default_factory=list)
    _identity_block_raw: bytes = b''
    _dna_payload_raw: bytes = b''

@dataclass
class VerificationResult:
    valid: bool
    owner: str
    signed_at: int
    tampered: bool = False
    proof_chain: List[str] = field(default_factory=list)
    error: str = ""

class SDNAReader:
    def read(self, file_path: str) -> SDNADocument:
        with open(file_path, "rb") as f:
            return self.read_from_bytes(f.read())

    def read_from_bytes(self, data: bytes) -> SDNADocument:
        if len(data) < 18 + 36: # Min size
            raise SDNATampered("File too small")
            
        # 1. Fixed Header
        magic, version, header_len, flags = struct.unpack(">8sHII", data[:18])
        if magic != SDNA_MAGIC:
            raise SDNATampered("Invalid SDNA magic bytes")
        
        # 2. Checksum Block (at the end)
        if data[-4:] != SDNA_EOF_MARKER:
            raise SDNATampered("Missing EOF marker")
        
        file_hash_actual = data[-36:-4]
        file_content_to_hash = data[:-36]
        if hashlib.sha3_256(file_content_to_hash).digest() != file_hash_actual:
            raise SDNATampered("File hash mismatch (tampered)")

        offset = 18
        
        # 3. Identity Block
        # Offset 18: 16s(asset_uuid), 16s(org_uuid), Q(signed_at), Q(embargo), 32s(fingerprint), H(name_len)
        fixed_id_len = 16 + 16 + 8 + 8 + 32 + 2 # 82 bytes
        asset_uid_bytes, org_uid_bytes, signed_at, embargo, fingerprint, name_len = struct.unpack(
            ">16s16sQQ32sH", data[offset:offset+fixed_id_len]
        )
        identity_block_raw = data[offset : offset + fixed_id_len + name_len]
        org_name = data[offset + fixed_id_len : offset + fixed_id_len + name_len].decode('utf-8')
        offset += fixed_id_len + name_len

        # 4. Crypto Block
        # 64s signature, 32s image_hash, 32s dna_hash, 12s nonce, 16s tag
        crypto_block_len = 64 + 32 + 32 + 12 + 16
        signature, image_hash, dna_vector_hash, nonce, tag = struct.unpack(
            ">64s32s32s12s16s", data[offset:offset+crypto_block_len]
        )
        offset += crypto_block_len

        # 5. DNA Block
        dna_block_len = struct.unpack(">I", data[offset:offset+4])[0]
        offset += 4
        dna_encrypted = data[offset:offset+dna_block_len]
        offset += dna_block_len
        
        dna_vectors = {}
        dna_payload_raw = b''
        if not (flags & FLAG_ENCRYPTED):
            # If not encrypted, we can parse it now
            dna_payload_raw = dna_encrypted
            dna_vectors = self._parse_dna_payload(dna_payload_raw)

        # 6. Watermark Block
        wm_seed, wm_payload_len = struct.unpack(">II", data[offset:offset+8])
        offset += 8
        wm_payload = data[offset:offset+wm_payload_len]
        offset += wm_payload_len

        # 7. Custody Block
        entry_count = struct.unpack(">I", data[offset:offset+4])[0]
        offset += 4
        custody_entries = []
        for _ in range(entry_count):
            ts, event, actor, prev = struct.unpack(">QB16s32s", data[offset:offset+57])
            custody_entries.append({
                "ts_ns": ts,
                "event": event,
                "actor": actor,
                "prev": prev
            })
            offset += 57
            
        # 8. Image Block
        img_format, img_len = struct.unpack(">IQ", data[offset:offset+12])
        offset += 12
        image_bytes = data[offset:offset+img_len]

        return SDNADocument(
            version=version,
            flags=flags,
            asset_uuid=str(uuid.UUID(bytes=asset_uid_bytes)),
            org_uuid=str(uuid.UUID(bytes=org_uid_bytes)),
            signed_at=signed_at,
            embargo_until=embargo,
            pubkey_fingerprint=fingerprint,
            org_name=org_name,
            signature=signature,
            image_hash=image_hash,
            dna_vector_hash=dna_vector_hash,
            nonce=nonce,
            tag=tag,
            dna_encrypted=dna_encrypted,
            dna_vectors=dna_vectors,
            watermark_seed=wm_seed,
            watermark_payload=wm_payload,
            custody_entries=custody_entries,
            image_format=img_format,
            image_bytes=image_bytes,
            _identity_block_raw=identity_block_raw,
            _dna_payload_raw=dna_payload_raw
        )

    def _parse_dna_payload(self, payload: bytes) -> Dict[str, Any]:
        import numpy as np
        vectors = {}
        offset = 0
        for layer in DNA_LAYERS:
            if offset + 4 > len(payload): break
            vlen = struct.unpack(">I", payload[offset:offset+4])[0]
            offset += 4
            if vlen > 0:
                vectors[layer] = np.frombuffer(payload[offset:offset+vlen], dtype=np.float32).tolist()
                offset += vlen
            else:
                vectors[layer] = None
        return vectors

    def verify_signature(self, doc: SDNADocument, public_key_resolver: Callable[[str], ec.EllipticCurvePublicKey]) -> VerificationResult:
        """
        ECDSA verify + custody chain walk.
        """
        try:
            pub_key = public_key_resolver(doc.org_uuid)
            if not pub_key:
                return VerificationResult(valid=False, owner=doc.org_name, signed_at=doc.signed_at, error="Public key not found")

            # Signs SHA3-256 of (MAGIC + IDENTITY_BLOCK + IMAGE_HASH + DNA_VECTOR_HASH)
            sign_payload = SDNA_MAGIC + doc._identity_block_raw + doc.image_hash + doc.dna_vector_hash
            
            # Signature is Raw P-256: r (32 bytes) + s (32 bytes)
            r = int.from_bytes(doc.signature[:32], 'big')
            s = int.from_bytes(doc.signature[32:], 'big')
            der_sig = encode_dss_signature(r, s)
            
            pub_key.verify(der_sig, sign_payload, ec.ECDSA(hashes.SHA3_256()))
            
            # Verify Custody Chain
            self._verify_custody_chain(doc.custody_entries)
            
            return VerificationResult(valid=True, owner=doc.org_name, signed_at=doc.signed_at, proof_chain=["SDNA_CONTAINER_MATCH"])
            
        except Exception as e:
            return VerificationResult(valid=False, owner=doc.org_name, signed_at=doc.signed_at, tampered=True, error=str(e))

    def _verify_custody_chain(self, entries: List[Dict[str, Any]]):
        """Walk linked hashes, raise SDNATampered on any gap."""
        if not entries: return
        
        # First entry prev must be zeros
        # Actually, each entry's hash should be verified.
        # "entry_hash (SHA3-256 of entry bytes)"
        # But we don't store the hash in the block? The spec says "prev_entry_hash" is stored.
        # "uint64 timestamp_ns | uint8 event_type | 16 bytes actor_hash | 32 bytes prev_entry_hash"
        
        for i in range(len(entries)):
            entry = entries[i]
            # Pack current entry to check if next one links to it
            current_raw = struct.pack(">QB16s32s", entry["ts_ns"], entry["event"], entry["actor"], entry["prev"])
            current_hash = hashlib.sha3_256(current_raw).digest()
            
            if i + 1 < len(entries):
                if entries[i+1]["prev"] != current_hash:
                    raise SDNATampered(f"Custody chain broken at entry {i+1}")

    def decrypt_dna(self, doc: SDNADocument, aes_key: bytes):
        """Decrypt DNA block if encrypted."""
        if not (doc.flags & FLAG_ENCRYPTED):
            return doc.dna_vectors
            
        aesgcm = AESGCM(aes_key)
        # Nonce and Tag are in doc
        # AAD = Identity Block
        try:
            full_encrypted = doc.dna_encrypted + doc.tag
            decrypted = aesgcm.decrypt(doc.nonce, full_encrypted, doc._identity_block_raw)
            doc._dna_payload_raw = decrypted
            doc.dna_vectors = self._parse_dna_payload(decrypted)
            return doc.dna_vectors
        except Exception as e:
            raise SDNATampered(f"DNA decryption failed: {e}")

    def extract_image(self, doc: SDNADocument) -> bytes:
        # Verify image hash matches
        if hashlib.sha3_256(doc.image_bytes).digest() != doc.image_hash:
            raise SDNATampered("Image content tampered (hash mismatch)")
        return doc.image_bytes
