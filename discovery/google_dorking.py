"""
Google Dorking Engine — Content DNA Apex v8.0
Uses yagooglesearch (pagodo's core library) instead of paid Google CSE / SerpAPI.
Zero API key required. Proxy-rotation supported via env vars.
Falls back to DuckDuckGo scraping if Google rate-limits.
"""
import logging
import os
import time
import random
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
    """
    Replaces paid Google CSE + SerpAPI with yagooglesearch / pagodo (open-source).
    Falls back to DuckDuckGo scraping if Google rate-limits.
    No API key required.
    """

    def __init__(self):
        self.min_delay = float(os.getenv("DORK_MIN_DELAY", "5.0"))
        self.max_delay = float(os.getenv("DORK_MAX_DELAY", "12.0"))
        self.max_results_per_dork = int(os.getenv("DORK_MAX_RESULTS", "10"))
        self.proxies = self._load_proxies()

    def _load_proxies(self) -> list:
        """Load proxy list from env var or proxy file."""
        proxy_str = os.getenv("DORK_PROXIES", "")
        if proxy_str:
            return [p.strip() for p in proxy_str.split(",") if p.strip()]
        proxy_file = os.getenv("DORK_PROXY_FILE", "")
        if proxy_file and os.path.exists(proxy_file):
            with open(proxy_file) as f:
                return [line.strip() for line in f if line.strip()]
        return [""]  # yagooglesearch expects at least one entry (empty = no proxy)

    async def run_dork_sweep(self, asset_metadata: Dict) -> List[SuspectedURL]:
        """Build dork queries from asset metadata and run each with randomized delay."""
        queries = DorkBuilder.build_dork_queries(asset_metadata)
        all_results: List[SuspectedURL] = []
        for query in queries:
            results = self._search_pagodo(query)
            all_results.extend(results)
            time.sleep(random.uniform(self.min_delay, self.max_delay))
        return all_results

    def _search_pagodo(self, query: str) -> List[SuspectedURL]:
        """
        Use yagooglesearch (pagodo's core library) to run the dork query.
        No API key needed — scrapes Google directly with delay + proxy rotation.
        """
        try:
            import yagooglesearch
            proxy = random.choice(self.proxies) if self.proxies else ""
            search = yagooglesearch.SearchClient(
                query,
                tbs="",
                verbosity=0,
                num=self.max_results_per_dork,
                max_search_result_urls_to_return=self.max_results_per_dork,
                proxy=proxy,
            )
            search.assign_random_user_agent()
            urls = search.search()

            results: List[SuspectedURL] = []
            for url in urls:
                if isinstance(url, str) and url.startswith("http"):
                    results.append(SuspectedURL(
                        url=url,
                        title="",
                        snippet="",
                        source="pagodo"
                    ))
            return results

        except Exception as e:
            logger.warning("pagodo search failed for query '%s': %s — trying DuckDuckGo fallback", query, e)
            return self._search_duckduckgo(query)

    def _search_duckduckgo(self, query: str) -> List[SuspectedURL]:
        """
        Fallback: scrape DuckDuckGo HTML results.
        No API key, no rate limit issues.
        """
        try:
            from duckduckgo_search import DDGS
            results: List[SuspectedURL] = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=self.max_results_per_dork):
                    results.append(SuspectedURL(
                        url=r.get("href", ""),
                        title=r.get("title", ""),
                        snippet=r.get("body", ""),
                        source="duckduckgo"
                    ))
            return results
        except Exception as e:
            logger.error("DuckDuckGo fallback also failed for query '%s': %s", query, e)
            return []

    def sweep(self, search_terms: list) -> list:
        """
        Synchronous wrapper for Celery tasks (run_dork_sweep).
        Builds queries from plain search terms and runs yagooglesearch / DDG fallback.

        Returns:
            list of dicts: [{"url": str, "platform": str, "media_bytes_b64": str, ...}, ...]
        """
        results: List[SuspectedURL] = []
        for term in search_terms:
            if not term:
                continue
            queries = [
                term,
                f'filetype:jpg "{term}"',
                f'"{term}" site:reddit.com',
                f'"{term}" stream OR download',
            ]
            for query in queries:
                found = self._search_pagodo(query)
                results.extend(found)
                time.sleep(random.uniform(self.min_delay, self.max_delay))

        return [
            {
                "url": s.url,
                "platform": "web",
                "media_bytes_b64": "",
                "title": s.title,
                "snippet": s.snippet,
            }
            for s in results
        ]
