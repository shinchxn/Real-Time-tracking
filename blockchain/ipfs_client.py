import httpx
import json
import logging
from config import settings

logger = logging.getLogger(__name__)

async def pin_json_to_ipfs(payload: dict) -> str:
    """Pins JSON data to IPFS via Pinata"""
    url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
    headers = {
        "Content-Type": "application/json",
        "pinata_api_key": "YOUR_PINATA_API_KEY", # Placeholder, would be in settings
        "pinata_secret_api_key": "YOUR_PINATA_SECRET_KEY"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # We mock the response if no key
            if headers["pinata_api_key"] == "YOUR_PINATA_API_KEY":
                return "Qm_mocked_hash_for_" + str(hash(json.dumps(payload)))
                
            res = await client.post(url, headers=headers, json={"pinataContent": payload})
            res.raise_for_status()
            return res.json()["IpfsHash"]
    except Exception as e:
        logger.error(f"IPFS pinning failed: {e}")
        return ""
