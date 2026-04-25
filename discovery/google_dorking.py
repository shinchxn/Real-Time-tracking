"""
Google Dorking Engine — Content DNA Apex v7.0
Executes dorking sweeps using Google CSE and SerpAPI fallbacks.
"""
import os
import httpx
import logging
from typing import List, Dict
from discovery.dork_builder import DorkBuilder

logger = logging.getLogger(__name__)

class SuspectedURL:
    def __init__(self, url: str, title: str, snippet: str, source: str):
        self.url = url
        self.title = title
        self.snippet = snippet
        self.source = source

class GoogleDorkingEngine:
    def __init__(self):
        self.cse_api_key = os.getenv("GOOGLE_CSE_API_KEY")
        self.cse_id = os.getenv("GOOGLE_CSE_ID")
        self.serpapi_key = os.getenv("SERPAPI_KEY")

    async def run_dork_sweep(self, asset_metadata: Dict) -> List[SuspectedURL]:
        """
        Generate dork queries and search for matches.
        """
        queries = DorkBuilder.build_dork_queries(asset_metadata)
        all_results = []
        
        for query in queries:
            results = await self._search_google(query)
            all_results.extend(results)
            
        return all_results

    async def _search_google(self, query: str) -> List[SuspectedURL]:
        """
        Search Google using CSE first, then SerpAPI fallback.
        """
        if self.cse_api_key and self.cse_id:
            try:
                return await self._search_cse(query)
            except Exception as e:
                logger.warning(f"Google CSE failed: {e}. Trying SerpAPI fallback.")
        
        if self.serpapi_key:
            try:
                return await self._search_serpapi(query)
            except Exception as e:
                logger.error(f"SerpAPI failed: {e}")
                
        return []

    async def _search_cse(self, query: str) -> List[SuspectedURL]:
        url = "https://customsearch.googleapis.com/customsearch/v1"
        params = {
            "key": self.cse_api_key,
            "cx": self.cse_id,
            "q": query
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            results = []
            for item in data.get("items", []):
                results.append(SuspectedURL(
                    url=item["link"],
                    title=item["title"],
                    snippet=item["snippet"],
                    source="google_cse"
                ))
            return results

    async def _search_serpapi(self, query: str) -> List[SuspectedURL]:
        # Implementation for SerpAPI
        # url = "https://serpapi.com/search"
        # ...
        return []
