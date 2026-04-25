"""
vyntra_crawl/dsa_components.py
================================
Drop-in DSA upgrades for Scrapy's 4 weakest internal components.

Usage in settings.py:
    DUPEFILTER_CLASS         = "scrapy_project.dsa_components.BloomDupeFilter"
    SCHEDULER                = "scrapy_project.dsa_components.VyntraScheduler"
    SCHEDULER_PRIORITY_QUEUE = "scrapy_project.dsa_components.HeapPriorityQueue"
    DOWNLOADER_MIDDLEWARES   = {
        "scrapy_project.dsa_components.ConsistentHashMiddleware": 50,
        "scrapy_project.dsa_components.TrieDomainMiddleware":     150,
    }
    ITEM_PIPELINES = {
        "scrapy_project.dsa_components.LRUFingerprintPipeline": 50,
    }
"""

from __future__ import annotations

import hashlib
import heapq
import math
import struct
import time
from collections import OrderedDict
from typing import Any, Iterator, Optional

# ─────────────────────────────────────────────────────────────────────────────
# 1. BLOOM FILTER — replaces scrapy.dupefilters.RFPDupeFilter
#    Scrapy default: Python set() in memory  → O(n) memory, no disk savings
#    Upgrade:        BitArray + k hash funcs → O(1) lookup, ~1 GB for 1B URLs
# ─────────────────────────────────────────────────────────────────────────────

class BloomFilter:
    """
    Counting Bloom Filter.

    Math:
        m = bits needed  = -n*ln(p) / (ln2)^2
        k = hash funcs   = (m/n) * ln2
    where n = expected insertions, p = false-positive rate.

    For n=100_000_000, p=0.001:
        m ≈ 1_437_758_756 bits ≈ 172 MB
        k = 10 hash functions
    """

    def __init__(self, capacity: int = 100_000_000, error_rate: float = 0.001):
        self.capacity = capacity
        self.error_rate = error_rate

        # Compute optimal m and k
        m = math.ceil(-capacity * math.log(error_rate) / (math.log(2) ** 2))
        k = max(1, round((m / capacity) * math.log(2)))

        self.m = m
        self.k = k
        self.bit_array = bytearray(math.ceil(m / 8))  # packed bits
        self.count = 0

    def _hash_positions(self, item: str) -> Iterator[int]:
        """
        Generate k independent hash positions using double hashing:
            pos_i = (h1 + i * h2) % m
        Two SHA-256 digests give us h1 and h2, then we derive k positions
        without k separate hash calls — O(1) per position.
        """
        data = item.encode()
        h1 = int.from_bytes(hashlib.sha256(data).digest()[:8], "big")
        h2 = int.from_bytes(hashlib.md5(data).digest()[:8], "big") | 1  # must be odd
        for i in range(self.k):
            yield (h1 + i * h2) % self.m

    def _get_bit(self, pos: int) -> bool:
        return bool(self.bit_array[pos >> 3] & (1 << (pos & 7)))

    def _set_bit(self, pos: int) -> None:
        self.bit_array[pos >> 3] |= 1 << (pos & 7)

    def add(self, item: str) -> None:
        for pos in self._hash_positions(item):
            self._set_bit(pos)
        self.count += 1

    def __contains__(self, item: str) -> bool:
        return all(self._get_bit(pos) for pos in self._hash_positions(item))

    @property
    def fill_ratio(self) -> float:
        set_bits = sum(bin(b).count("1") for b in self.bit_array)
        return set_bits / self.m


class BloomDupeFilter:
    """
    Scrapy DUPEFILTER_CLASS replacement.

    Scrapy's RFPDupeFilter stores fingerprints in a Python set:
        - Memory: 50 bytes per URL at 100M URLs = 5 GB
        - Lookup: O(1) average but full hash stored
    This Bloom filter:
        - Memory: ~172 MB for 100M URLs at 0.1% FP rate
        - Lookup: O(k) = O(10) — constant, very fast
        - False positives: ~0.1% (a URL is skipped once, harmless)
        - False negatives: ZERO (never misses a true duplicate)
    """

    def __init__(self, capacity: int = 100_000_000, error_rate: float = 0.001,
                 debug: bool = False):
        self.bf = BloomFilter(capacity, error_rate)
        self.debug = debug
        self.logdupes = True

    @classmethod
    def from_settings(cls, settings):
        capacity   = settings.getint("BLOOM_CAPACITY", 100_000_000)
        error_rate = settings.getfloat("BLOOM_ERROR_RATE", 0.001)
        debug      = settings.getbool("DUPEFILTER_DEBUG", False)
        return cls(capacity, error_rate, debug)

    @classmethod
    def from_crawler(cls, crawler):
        return cls.from_settings(crawler.settings)

    def request_seen(self, request) -> bool:
        fp = self._fingerprint(request)
        if fp in self.bf:
            return True
        self.bf.add(fp)
        return False

    def _fingerprint(self, request) -> str:
        """Canonical fingerprint: method + sorted URL + body hash."""
        h = hashlib.sha256()
        h.update(request.method.encode())
        h.update(request.url.encode())
        if request.body:
            h.update(request.body)
        return h.hexdigest()

    def open(self):
        pass

    def close(self, reason: str):
        pass

    def log(self, request, spider):
        if self.debug and self.logdupes:
            spider.logger.debug(f"[BloomDupeFilter] Filtered duplicate: {request}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. MIN-HEAP PRIORITY QUEUE — replaces ScrapyPriorityQueue (LIFO/FIFO buckets)
#    Scrapy default: one deque per integer priority, O(log n) bucket select
#    Upgrade:        single heapq min-heap, composite score as key
#                    score = match_prob_boost + page_rank - domain_cooldown
# ─────────────────────────────────────────────────────────────────────────────

class HeapEntry:
    """Heap entry that breaks ties by insertion order (FIFO within same score)."""
    __slots__ = ("score", "seq", "request")

    def __init__(self, score: float, seq: int, request):
        self.score = score
        self.seq = seq
        self.request = request

    def __lt__(self, other: "HeapEntry") -> bool:
        # Min-heap: lower score = higher priority (negate score for max-priority)
        if self.score != other.score:
            return self.score < other.score
        return self.seq < other.seq


class HeapPriorityQueue:
    """
    Drop-in for SCHEDULER_PRIORITY_QUEUE.

    Composite score (negated so min-heap acts as max-priority):
        raw_score = request.priority          (set by spider, 0-1000)
                  + domain_boost              (high-value img hosts boosted)
                  - domain_cooldown_penalty   (recently crawled domains penalised)

    heap key = -raw_score  (so highest raw_score pops first)
    """

    # Domains that frequently host stolen images get a priority boost
    HIGH_VALUE_DOMAINS = {
        "imgur.com": 200,
        "unsplash.com": 180,
        "pexels.com": 180,
        "flickr.com": 160,
        "pinterest.com": 150,
        "500px.com": 140,
        "behance.net": 130,
        "deviantart.com": 120,
        "pixabay.com": 110,
        "artstation.com": 150,
        "shutterstock.com": 100,
        "stock.adobe.com": 100,
    }

    def __init__(self):
        self._heap: list[HeapEntry] = []
        self._seq = 0
        self._domain_last_crawl: dict[str, float] = {}

    def push(self, request, _priority: int = 0) -> None:
        domain = self._extract_domain(request.url)
        boost  = self.HIGH_VALUE_DOMAINS.get(domain, 0)

        last   = self._domain_last_crawl.get(domain, 0)
        age    = time.monotonic() - last
        # Cooldown: penalty decays from 500 → 0 over 60 seconds
        cooldown = max(0.0, 500.0 - age * (500.0 / 60.0))

        raw_score = (request.priority or 0) + boost - cooldown
        entry = HeapEntry(score=-raw_score, seq=self._seq, request=request)
        self._seq += 1
        heapq.heappush(self._heap, entry)

    def pop(self):
        if not self._heap:
            return None
        entry = heapq.heappop(self._heap)
        domain = self._extract_domain(entry.request.url)
        self._domain_last_crawl[domain] = time.monotonic()
        return entry.request

    def peek(self):
        return self._heap[0].request if self._heap else None

    def __len__(self) -> int:
        return len(self._heap)

    def close(self) -> list:
        # Return remaining requests for Scrapy's persistence layer
        return [e.request for e in self._heap]

    @staticmethod
    def _extract_domain(url: str) -> str:
        try:
            host = url.split("//", 1)[1].split("/", 1)[0].split("?")[0]
            parts = host.split(".")
            return ".".join(parts[-2:]) if len(parts) >= 2 else host
        except Exception:
            return url


# ─────────────────────────────────────────────────────────────────────────────
# 3. TRIE DOMAIN ROUTER — Scrapy Spider Middleware
#    Scrapy default: regex list evaluated top-to-bottom O(R × L) per URL
#    Upgrade:        Trie lookup O(d) where d = domain label depth (≤5)
#                    Same Trie node stores: allowed flag + rate bucket reference
# ─────────────────────────────────────────────────────────────────────────────

class _TrieNode:
    __slots__ = ("children", "is_terminal", "allowed", "rate_limit_rps")

    def __init__(self):
        self.children: dict[str, "_TrieNode"] = {}
        self.is_terminal = False
        self.allowed: Optional[bool] = None   # None = inherit from parent
        self.rate_limit_rps: float = 2.0       # default 2 requests/sec per domain


class DomainTrie:
    """
    Trie keyed on reversed domain labels: "cdn.example.com" → ["com","example","cdn"]

    Why reversed? Wildcards like "*.example.com" are a prefix match on the
    reversed label list — the Trie handles them naturally at the root level.

    O(d) insert, O(d) lookup where d = number of labels (≤ 5 for most domains).
    """

    def __init__(self):
        self.root = _TrieNode()

    def insert(self, domain: str, allowed: bool, rate_rps: float = 2.0) -> None:
        labels = self._labels(domain)
        node = self.root
        for label in labels:
            node = node.children.setdefault(label, _TrieNode())
        node.is_terminal = True
        node.allowed = allowed
        node.rate_limit_rps = rate_rps

    def lookup(self, domain: str) -> tuple[bool, float]:
        """Returns (allowed, rate_limit_rps). Inherits from closest ancestor."""
        labels = self._labels(domain)
        node = self.root
        last_allowed = True       # default: allow
        last_rps = 2.0
        for label in labels:
            child = node.children.get(label) or node.children.get("*")
            if child is None:
                break
            node = child
            if node.allowed is not None:
                last_allowed = node.allowed
                last_rps = node.rate_limit_rps
        return last_allowed, last_rps

    @staticmethod
    def _labels(domain: str) -> list[str]:
        """Reverse label list: "cdn.example.com" → ["com", "example", "cdn"]"""
        return domain.lower().split(".")[::-1]


class _TokenBucket:
    """Token bucket rate limiter. Thread-safe via GIL for CPython."""
    __slots__ = ("rate", "capacity", "tokens", "last")

    def __init__(self, rate_rps: float):
        self.rate = rate_rps
        self.capacity = max(rate_rps * 2, 1.0)   # burst = 2× steady rate
        self.tokens = self.capacity
        self.last = time.monotonic()

    def consume(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last
        self.last = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class TrieDomainMiddleware:
    """
    Scrapy SPIDER_MIDDLEWARES / DOWNLOADER_MIDDLEWARES component.

    On every outgoing request:
      1. Trie lookup in O(d) → is this domain allowed?
      2. Token bucket check  → are we within rate limit?
      3. Blocked/throttled?  → drop with reason logged.
    """

    # Pre-loaded blocklist (platform ToS-violating sustained scrapers)
    BLOCKED = [
        ("instagram.com",  False, 0.0),
        ("facebook.com",   False, 0.0),
        ("whatsapp.com",   False, 0.0),
    ]
    # Allowed high-value targets with custom RPS
    ALLOWED = [
        ("imgur.com",      True, 5.0),
        ("unsplash.com",   True, 3.0),
        ("pexels.com",     True, 3.0),
        ("pinterest.com",  True, 2.0),
        ("reddit.com",     True, 2.0),
        ("deviantart.com", True, 1.5),
        ("youtube.com",    True, 1.0),
        ("tiktok.com",     True, 1.0),
        ("tinEye.com",     True, 2.0),
        ("bing.com",       True, 2.0),
        ("pixabay.com",    True, 3.0),
        ("artstation.com", True, 2.0),
        ("shutterstock.com", True, 1.0),
    ]

    def __init__(self):
        self.trie = DomainTrie()
        self._buckets: dict[str, _TokenBucket] = {}
        for domain, allowed, rps in self.BLOCKED + self.ALLOWED:
            self.trie.insert(domain, allowed, rps)

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_request(self, request, spider):
        domain = HeapPriorityQueue._extract_domain(request.url)
        allowed, rps = self.trie.lookup(domain)

        if not allowed:
            from scrapy.exceptions import IgnoreRequest
            spider.logger.debug(f"[TrieMiddleware] Blocked domain: {domain}")
            raise IgnoreRequest(f"Domain blocked by Trie router: {domain}")

        # Per-domain token bucket
        bucket = self._buckets.setdefault(domain, _TokenBucket(rps))
        if not bucket.consume():
            from scrapy.exceptions import IgnoreRequest
            raise IgnoreRequest(f"Rate limited by Trie router: {domain} ({rps} rps)")

        return None   # pass through


# ─────────────────────────────────────────────────────────────────────────────
# 4. CONSISTENT HASH RING — Scrapy Downloader Middleware
#    Scrapy default: single Twisted reactor, all requests on one process
#    Upgrade:        CH ring assigns each domain to a stable worker endpoint
#                    Adding/removing workers remaps only 1/N domains
# ─────────────────────────────────────────────────────────────────────────────

class ConsistentHashRing:
    """
    Consistent Hash Ring with virtual nodes.

    Each physical node gets V virtual nodes spread around the ring.
    This ensures even distribution even with few physical nodes.
    Virtual nodes: V=150 gives < 5% std-dev in load distribution.

    Lookup: binary search on sorted ring → O(log(N×V))
    Insert/remove node: O(V log(N×V)) — only ~1/N URLs re-assigned
    """

    def __init__(self, nodes: list[str], virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
        self._ring: list[tuple[int, str]] = []   # (hash_value, node)
        self._nodes: set[str] = set()
        for node in nodes:
            self.add_node(node)

    def add_node(self, node: str) -> None:
        for i in range(self.virtual_nodes):
            key = f"{node}:vn{i}".encode()
            h = int.from_bytes(hashlib.md5(key).digest()[:4], "big")
            self._ring.append((h, node))
        self._ring.sort()
        self._nodes.add(node)

    def remove_node(self, node: str) -> None:
        self._ring = [(h, n) for h, n in self._ring if n != node]
        self._nodes.discard(node)

    def get_node(self, key: str) -> str:
        if not self._ring:
            raise ValueError("Ring is empty")
        h = int.from_bytes(hashlib.md5(key.encode()).digest()[:4], "big")
        # Binary search for the first ring position ≥ h
        lo, hi = 0, len(self._ring)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._ring[mid][0] < h:
                lo = mid + 1
            else:
                hi = mid
        idx = lo % len(self._ring)   # wrap around
        return self._ring[idx][1]

    def distribution(self) -> dict[str, int]:
        """Debug: count virtual node slots per physical node."""
        counts: dict[str, int] = {}
        for _, node in self._ring:
            counts[node] = counts.get(node, 0) + 1
        return counts


class ConsistentHashMiddleware:
    """
    Scrapy DOWNLOADER_MIDDLEWARES component.

    Tags each request with X-Vyntra-Worker header so a downstream
    proxy/load-balancer or Scrapy-cluster can route it to the correct
    worker. Same domain always goes to same worker → per-domain state
    (cookies, session, rate counters) stays local to one process.
    """

    # Worker endpoints (replace with real K8s pod IPs / Scrapy-cluster URLs)
    DEFAULT_WORKERS = [
        "worker-0.vyntra-crawl.svc",
        "worker-1.vyntra-crawl.svc",
        "worker-2.vyntra-crawl.svc",
        "worker-3.vyntra-crawl.svc",
    ]

    def __init__(self, workers: list[str]):
        self.ring = ConsistentHashRing(workers)

    @classmethod
    def from_crawler(cls, crawler):
        workers = crawler.settings.getlist("VYNTRA_WORKERS", cls.DEFAULT_WORKERS)
        return cls(workers)

    def process_request(self, request, spider):
        domain = HeapPriorityQueue._extract_domain(request.url)
        worker = self.ring.get_node(domain)
        request.headers["X-Vyntra-Worker"] = worker
        request.meta["vyntra_worker"] = worker
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 5. LRU FINGERPRINT CACHE — Scrapy Item Pipeline
#    Before hitting FAISS (expensive), check in-memory O(1) cache.
#    Implemented as doubly-linked-list + hash-map (classic LRU pattern).
# ─────────────────────────────────────────────────────────────────────────────

class LRUCache:
    """
    O(1) get, O(1) put LRU Cache.
    Uses OrderedDict (Python's built-in DLL + hash-map hybrid).
    On every get: move_to_end(key) → O(1) via pointer swap.
    On every put: append + evict oldest if over capacity.
    """

    def __init__(self, capacity: int = 50_000):
        self.capacity = capacity
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            self.misses += 1
            return None
        self._cache.move_to_end(key)   # O(1) pointer update
        self.hits += 1
        return self._cache[key]

    def put(self, key: str, value: Any) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self.capacity:
            self._cache.popitem(last=False)  # evict LRU (first item)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    def __len__(self) -> int:
        return len(self._cache)


class LRUFingerprintPipeline:
    """
    Scrapy ITEM_PIPELINES component.

    Flow:
      1. Compute image fingerprint from item["image_url"]
      2. Check LRU cache (O(1)) — cache hit → skip FAISS entirely
      3. Cache miss → call FAISS vector search (async, ~8ms)
      4. Store result in LRU cache for future hits
    """

    def __init__(self, capacity: int = 50_000):
        self.cache = LRUCache(capacity)
        self._faiss_calls = 0

    @classmethod
    def from_crawler(cls, crawler):
        cap = crawler.settings.getint("LRU_CACHE_CAPACITY", 50_000)
        return cls(cap)

    def open_spider(self, spider):
        spider.logger.info(
            f"[LRUPipeline] Cache ready: capacity={self.cache.capacity}"
        )

    def process_item(self, item, spider):
        url = item.get("image_url", item.get("url", ""))
        if not url:
            return item
            
        fp = hashlib.sha256(url.encode()).hexdigest()

        cached = self.cache.get(fp)
        if cached is not None:
            # Rehydrate item with cached forensic data
            item.update(cached)
            item["cache_hit"] = True
            return item

        # Cache miss: populate on next pass (see DetectionPipeline integration)
        item["cache_hit"] = False
        item["_cache_key"] = fp
        return item

class LRUCachePopulatorPipeline:
    """
    Saves forensic results back into the LRU cache at the end of the pipeline.
    """
    def process_item(self, item, spider):
        if not item.get("cache_hit") and "_cache_key" in item:
            # Create a compact result for caching
            cache_data = {
                "dna": item.get("dna"),
                "fusion_score": item.get("fusion_score"),
                "severity": item.get("severity"),
                "asset_id": item.get("asset_id"),
                "match_result": item.get("match_result"),
            }
            # Find the LRU pipeline instance to access the shared cache
            # In a real system, we'd use a shared singleton or Redis
            for pipe in spider.crawler.engine.scraper.pipelines:
                if isinstance(pipe, LRUFingerprintPipeline):
                     pipe.cache.put(item["_cache_key"], cache_data)
                     break
        return item


# ─────────────────────────────────────────────────────────────────────────────
# 6. VYNTRA SCHEDULER — wraps Scrapy's BaseScheduler, plugs in all DSA pieces
# ─────────────────────────────────────────────────────────────────────────────

class VyntraScheduler:
    """
    Scrapy SCHEDULER replacement.

    Wires together:
      - BloomDupeFilter     → deduplicate with Bloom Filter
      - HeapPriorityQueue   → schedule with composite min-heap score
      - TrieDomainMiddleware is registered separately in DOWNLOADER_MIDDLEWARES

    Implements Scrapy's BaseScheduler interface:
        enqueue_request(request) → bool
        next_request()           → Request | None
        has_pending_requests()   → bool
        open(spider)
        close(reason)
    """

    def __init__(self, dupefilter, heap: HeapPriorityQueue, stats=None, debug=False):
        self.df = dupefilter
        self.heap = heap
        self.stats = stats
        self.debug = debug

    @classmethod
    def from_crawler(cls, crawler):
        settings = crawler.settings
        df   = BloomDupeFilter.from_settings(settings)
        heap = HeapPriorityQueue()
        return cls(
            dupefilter=df,
            heap=heap,
            stats=crawler.stats,
            debug=settings.getbool("SCHEDULER_DEBUG", False),
        )

    def open(self, spider):
        self.spider = spider
        return self.df.open()

    def close(self, reason: str):
        return self.df.close(reason)

    def enqueue_request(self, request) -> bool:
        if not request.dont_filter and self.df.request_seen(request):
            if self.debug:
                self.spider.logger.debug(f"[VyntraScheduler] Dup filtered: {request.url}")
            if self.stats:
                self.stats.inc_value("scheduler/filtered", spider=self.spider)
            return False
        self.heap.push(request)
        if self.stats:
            self.stats.inc_value("scheduler/enqueued", spider=self.spider)
        return True

    def next_request(self):
        request = self.heap.pop()
        if request and self.stats:
            self.stats.inc_value("scheduler/dequeued", spider=self.spider)
        return request

    def has_pending_requests(self) -> bool:
        return len(self.heap) > 0
