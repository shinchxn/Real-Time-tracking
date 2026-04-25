import imagehash
from PIL import Image

def extract_phash_suite(image: Image.Image) -> dict:
    """
    Yields 4x64-bit hex strings.
    pHash, aHash, dHash, wHash
    """
    return {
        "phash": str(imagehash.phash(image, hash_size=8)),
        "ahash": str(imagehash.average_hash(image, hash_size=8)),
        "dhash": str(imagehash.dhash(image, hash_size=8)),
        "whash": str(imagehash.whash(image, hash_size=8)),
    }

def hamming_distance(hex1: str, hex2: str) -> int:
    h1 = imagehash.hex_to_hash(hex1)
    h2 = imagehash.hex_to_hash(hex2)
    return h1 - h2
