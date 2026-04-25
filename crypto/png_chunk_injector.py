"""
PNG Chunk Injector — Content DNA Apex v7.0
Injects and extracts custom ancillary chunks (orGN) into PNG files.
Payload is AES-256-GCM encrypted.
"""
import struct
import zlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from typing import Optional, Dict

def inject_ownership_chunk(png_bytes: bytes, payload: bytes, aes_key: bytes) -> bytes:
    """
    Inject private 'orGN' ancillary chunk after IHDR block.
    Payload is assumed to be already encrypted or we encrypt it here.
    """
    # Encrypt payload
    aesgcm = AESGCM(aes_key)
    nonce = AESGCM.generate_nonce()
    encrypted_payload = aesgcm.encrypt(nonce, payload, b"orGN")
    chunk_data = nonce + encrypted_payload
    
    # PNG format: 8 bytes magic + series of chunks
    # Chunk: 4 bytes length, 4 bytes type, N bytes data, 4 bytes CRC
    
    if png_bytes[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError("Not a valid PNG file")
        
    output = bytearray(png_bytes[:8])
    
    # Find IHDR chunk
    offset = 8
    while offset < len(png_bytes):
        length = struct.unpack(">I", png_bytes[offset:offset+4])[0]
        chunk_type = png_bytes[offset+4:offset+8]
        
        # Add current chunk to output
        output.extend(png_bytes[offset:offset+12+length])
        
        if chunk_type == b'IHDR':
            # Inject orGN chunk right after IHDR
            or_gn_type = b'orGN'
            or_gn_len = len(chunk_data)
            or_gn_header = struct.pack(">I", or_gn_len) + or_gn_type
            or_gn_crc = zlib.crc32(or_gn_type + chunk_data) & 0xffffffff
            
            output.extend(or_gn_header)
            output.extend(chunk_data)
            output.extend(struct.pack(">I", or_gn_crc))
            
        offset += 12 + length
        
    return bytes(output)

def extract_ownership_chunk(png_bytes: bytes, aes_key: bytes) -> Optional[bytes]:
    """Scan PNG chunks for 'orGN', decrypt and return payload."""
    if png_bytes[:8] != b'\x89PNG\r\n\x1a\n':
        return None
        
    offset = 8
    while offset < len(png_bytes):
        length = struct.unpack(">I", png_bytes[offset:offset+4])[0]
        chunk_type = png_bytes[offset+4:offset+8]
        
        if chunk_type == b'orGN':
            chunk_data = png_bytes[offset+8:offset+8+length]
            nonce = chunk_data[:12]
            ciphertext = chunk_data[12:]
            
            try:
                aesgcm = AESGCM(aes_key)
                decrypted = aesgcm.decrypt(nonce, ciphertext, b"orGN")
                return decrypted
            except Exception:
                return None
                
        offset += 12 + length
        
    return None
