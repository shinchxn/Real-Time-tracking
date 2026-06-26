"""
Reverse Image Search Engine — Content DNA Apex v8.0
Replaces TinEye + Bing Visual Search (paid/stub) with:
  1. Local CLIP + FAISS similarity search (100% self-hosted, zero cost)
  2. SauceNAO free tier as optional secondary (300 req/day with free key)

Strategy:
  - Extract CLIP embedding from query image via fingerprint/clip_embedder.py
  - Search FAISS index for top-K nearest neighbours above threshold
  - Return asset URLs/IDs of matched registered assets
  - Optionally also query SauceNAO for additional platform coverage
"""
import logging
import io
import os
import numpy as np
from typing import List
from PIL import Image

logger = logging.getLogger(__name__)


class ReverseImageSearchEngine:
    """
    Self-hosted reverse image search using the project's own
    CLIP embedder + FAISS index. No external API required.
    Falls back to SauceNAO (free tier) for additional coverage.
    """

    def __init__(self):
        self.threshold = float(os.getenv("MATCH_THRESHOLD", "0.82"))
        self.saucenao_api_key = os.getenv("SAUCENAO_API_KEY", "")

    async def search(self, image_bytes: bytes) -> List[str]:
        """
        Search for matching registered assets.
        Returns a deduplicated list of suspected source URLs / asset IDs.
        """
        urls: List[str] = []

        # — Primary: CLIP + FAISS (fully local, zero cost) —
        try:
            local_matches = await self._search_local_faiss(image_bytes)
            urls.extend(local_matches)
        except Exception as e:
            logger.error("Local FAISS reverse image search failed: %s", e)

        # — Secondary: SauceNAO (free tier, optional) —
        if self.saucenao_api_key:
            try:
                saucenao_urls = await self._search_saucenao(image_bytes)
                urls.extend(saucenao_urls)
            except Exception as e:
                logger.warning("SauceNAO search failed: %s", e)

        return list(set(urls))  # deduplicate

    async def _search_local_faiss(self, image_bytes: bytes) -> List[str]:
        """
        Extract CLIP embedding and search the project's own FAISS index.
        Returns source URLs / asset IDs of matched registered assets.
        """
        from fingerprint.clip_embedder import get_clip_embedding
        from detection.faiss_index import FAISSIndex
        from config import settings

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        embedding = await get_clip_embedding(
            img,
            device=settings.DEVICE,
            model_name=settings.CLIP_MODEL,
        )

        index = FAISSIndex()
        matches = index.search(embedding, k=10)

        matched_urls: List[str] = []
        for match in matches:
            score = float(match.get("score", 0))
            if score >= self.threshold:
                asset_url = match.get("sdna_url") or match.get("asset_id", "")
                if asset_url:
                    matched_urls.append(asset_url)

        logger.info(
            "Local FAISS RIS: %d matches above %.2f threshold",
            len(matched_urls),
            self.threshold,
        )
        return matched_urls

    async def _search_saucenao(self, image_bytes: bytes) -> List[str]:
        """
        Query SauceNAO (free: 100 req/day without key, 300/day with free key).
        Good for detecting sports media reuse on known platforms.
        Sign up free at: https://saucenao.com/user.php?page=account-upgrades
        """
        import httpx

        params: dict = {
            "output_type": 2,   # JSON response
            "numres": 6,
            "db": 999,          # search all databases
        }
        if self.saucenao_api_key:
            params["api_key"] = self.saucenao_api_key

        files = {"file": ("image.jpg", image_bytes, "image/jpeg")}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://saucenao.com/search.php",
                params=params,
                files=files,
            )
            resp.raise_for_status()
            data = resp.json()

        urls: List[str] = []
        for result in data.get("results", []):
            similarity = float(result.get("header", {}).get("similarity", 0))
            if similarity >= 80.0:
                ext_urls = result.get("data", {}).get("ext_urls", [])
                urls.extend(ext_urls)

        logger.info("SauceNAO RIS: found %d URLs with similarity >= 80%%", len(urls))
        return urls
