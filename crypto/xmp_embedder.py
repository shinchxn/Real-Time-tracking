"""
XMP Embedder — Content DNA Apex v7.0
Injects and extracts XMP metadata into images (JPEG, PNG, WEBP).
Uses the https://sportsmedia.io/schema/1.0/ namespace.
"""
import io
from typing import Dict, Optional
from PIL import Image
import piexif

XMP_NS = "https://sportsmedia.io/schema/1.0/"
XMP_TEMPLATE = """<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about="" xmlns:smc="{ns}">
      <smc:AssetID>{asset_id}</smc:AssetID>
      <smc:OrgID>{org_id}</smc:OrgID>
      <smc:Signature>{signature}</smc:Signature>
      <smc:SignedAt>{signed_at}</smc:SignedAt>
      <smc:PublicKeyURL>{pubkey_url}</smc:PublicKeyURL>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>"""

def embed_xmp_metadata(image_bytes: bytes, metadata: Dict[str, str]) -> bytes:
    """
    Embeds XMP metadata into image bytes.
    """
    img = Image.open(io.BytesIO(image_bytes))
    format = img.format
    
    xmp_data = XMP_TEMPLATE.format(
        ns=XMP_NS,
        asset_id=metadata.get("AssetID", ""),
        org_id=metadata.get("OrgID", ""),
        signature=metadata.get("Signature", ""),
        signed_at=metadata.get("SignedAt", ""),
        pubkey_url=metadata.get("PublicKeyURL", "")
    ).encode('utf-8')

    if format == 'JPEG':
        # For JPEG, we use piexif to handle APP1/Exif/XMP if needed, 
        # but Pillow can also save XMP.
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', xmp=xmp_data)
        return buffer.getvalue()
    elif format == 'PNG':
        # For PNG, XMP is stored in a 'tEXt' chunk with keyword 'XML:com.adobe.xmp'
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', xmp=xmp_data)
        return buffer.getvalue()
    elif format == 'WEBP':
        buffer = io.BytesIO()
        img.save(buffer, format='WEBP', xmp=xmp_data)
        return buffer.getvalue()
    else:
        # Fallback
        buffer = io.BytesIO()
        img.save(buffer, format=format)
        return buffer.getvalue()

def extract_xmp_metadata(image_bytes: bytes) -> Optional[Dict[str, str]]:
    """
    Extracts XMP metadata from image bytes.
    """
    img = Image.open(io.BytesIO(image_bytes))
    xmp = img.info.get("xmp")
    if not xmp:
        return None
    
    if isinstance(xmp, bytes):
        xmp = xmp.decode('utf-8', errors='ignore')
    
    # Very simple parsing (Regex or XML parser would be better)
    import re
    def get_tag(tag):
        match = re.search(f"<smc:{tag}>(.*?)</smc:{tag}>", xmp)
        return match.group(1) if match else None

    results = {
        "AssetID": get_tag("AssetID"),
        "OrgID": get_tag("OrgID"),
        "Signature": get_tag("Signature"),
        "SignedAt": get_tag("SignedAt"),
        "PublicKeyURL": get_tag("PublicKeyURL")
    }
    
    if any(results.values()):
        return results
    return None
