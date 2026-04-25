"""
SDNA Specification Constants — Content DNA Apex v7.0
All magic bytes, flag bitmasks, format constants, and custody event types.
"""

# ── File Magic ─────────────────────────────────────────────────────────────────
SDNA_MAGIC = bytes([0x89, 0x53, 0x44, 0x4E, 0x41, 0x0D, 0x0A, 0x1A])  # 8 bytes
SDNA_VERSION = 0x0001
SDNA_EOF_MARKER = b'EOF!'

# ── Flags Bitmask ──────────────────────────────────────────────────────────────
FLAG_ENCRYPTED      = 0b00000001  # DNA block is AES-256-GCM encrypted
FLAG_WATERMARKED    = 0b00000010  # DCT spread-spectrum watermark embedded
FLAG_SIGNED         = 0b00000100  # ECDSA P-256 signature present
FLAG_TAMPER_EVIDENT = 0b00001000  # custody hash chain present
FLAG_EMBARGO_ACTIVE = 0b00010000  # embargo window currently active

# ── Image Format Magic (uint32) ────────────────────────────────────────────────
IMG_PNG  = 0x504E4700
IMG_JPEG = 0x4A504547
IMG_WEBP = 0x57454250
IMG_H265 = 0x48323635

# ── Custody Event Types (uint8) ────────────────────────────────────────────────
CUSTODY_REGISTERED  = 0
CUSTODY_DISTRIBUTED = 1
CUSTODY_LICENSED    = 2
CUSTODY_VIOLATION   = 3
CUSTODY_DMCA_FILED  = 4

# ── Block Size Constants ───────────────────────────────────────────────────────
CRYPTO_BLOCK_SIZE   = 156   # 64 ECDSA + 32 image_hash + 32 dna_hash + 12 nonce + 16 tag
CUSTODY_ENTRY_SIZE  = 57    # 8 ts_ns + 1 event + 16 actor_hash + 32 prev_hash

# ── DNA Layer Names (order matters — must match serialization) ─────────────────
DNA_LAYERS = ["clip", "phash", "hog", "color", "dct", "spatial"]

# ── Proof Type Hierarchy (strongest first) ─────────────────────────────────────
PROOF_SDNA_CONTAINER        = "SDNA_CONTAINER_MATCH"
PROOF_CRYPTOGRAPHIC_LAYER   = "CRYPTOGRAPHIC_LAYER_MATCH"
PROOF_TEMPORAL_WATERMARK    = "TEMPORAL_WATERMARK_MATCH"
PROOF_AUDIO_WATERMARK       = "AUDIO_WATERMARK_MATCH"
PROOF_STREAM_FINGERPRINT    = "STREAM_FINGERPRINT_MATCH"
PROOF_FORENSIC_VISUAL       = "FORENSIC_VISUAL_MATCH"
PROOF_DORK_DOMAIN_HIT       = "DORK_DOMAIN_HIT"

PROOF_HIERARCHY = [
    PROOF_SDNA_CONTAINER,
    PROOF_CRYPTOGRAPHIC_LAYER,
    PROOF_TEMPORAL_WATERMARK,
    PROOF_AUDIO_WATERMARK,
    PROOF_STREAM_FINGERPRINT,
    PROOF_FORENSIC_VISUAL,
    PROOF_DORK_DOMAIN_HIT,
]

# ── Severity Upgrade Map ───────────────────────────────────────────────────────
SEVERITY_UPGRADE = {
    "LOW": "MEDIUM",
    "MEDIUM": "HIGH",
    "HIGH": "CRITICAL",
    "CRITICAL": "CRITICAL",
    "MISS": "MISS",
}
