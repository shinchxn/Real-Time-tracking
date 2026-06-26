"""
Domain Classifier — Content DNA Apex v7.1
Categorizes domains into Licensed, Piracy, or Unknown.

Fixed: Added classify_sync() for use in Celery tasks (sync context).
The original async classify() is kept for backward compatibility.
"""
from typing import Literal
from urllib.parse import urlparse

KNOWN_PIRACY_DOMAINS = [
    'streameast.live', 'sportsurge.net', 'laola1.tv',
    'vipleague.lc', 'buffstreams.sx', 'totalsportek.pro',
    'cricfree.sc', 'firstrowsports.eu', 'livetv.sx',
    'rojadirecta.me', 'atdhenet.tv', 'myp2p.eu',
]

# Domains that are always the legitimate owner — never flag
LEGITIMATE_OWNER_PATTERNS = [
    'nba.com', 'bcci.tv', 'ipl.t20.com',
    'nfl.com', 'mlb.com', 'premierleague.com',
]


class DomainClassifier:
    """
    Classifies a URL's domain as:
    - 'legitimate_owner': Known rights-holder domain — skip sighting
    - 'piracy_hub': Known illegal streaming/piracy domain — CRITICAL severity
    - 'unknown': Unclassified — treat as HIGH severity
    """

    def classify_sync(self, url: str, org_id: str = "") -> Literal["legitimate_owner", "piracy_hub", "unknown"]:
        """
        Synchronous classification for use in Celery tasks.
        """
        domain = urlparse(url).netloc.lower().lstrip("www.")
        if not domain:
            return "unknown"

        # Check legitimate owner patterns
        if any(legit in domain for legit in LEGITIMATE_OWNER_PATTERNS):
            return "legitimate_owner"

        # Check known piracy domains
        if any(piracy in domain for piracy in KNOWN_PIRACY_DOMAINS):
            return "piracy_hub"

        return "unknown"

    @staticmethod
    async def classify(url: str, org_id: str = "") -> Literal["LICENSED", "CRITICAL_PIRACY", "UNKNOWN"]:
        """
        Async classification — backward compatible with original interface.
        """
        domain = urlparse(url).netloc.lower()
        if not domain:
            return "UNKNOWN"

        if any(piracy in domain for piracy in KNOWN_PIRACY_DOMAINS):
            return "CRITICAL_PIRACY"

        # In production: check authorized_domains from DB using org_id
        return "UNKNOWN"
