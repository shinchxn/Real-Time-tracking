"""
Domain Classifier — Content DNA Apex v7.0
Categorizes domains into Licensed, Piracy, or Unknown.
"""
from typing import Literal
from urllib.parse import urlparse

KNOWN_PIRACY_DOMAINS = [
    'streameast.live', 'sportsurge.net', 'laola1.tv', 
    'vipleague.lc', 'buffstreams.sx', 'totalsportek.pro'
]

class DomainClassifier:
    @staticmethod
    async def classify(url: str, org_id: str) -> Literal['LICENSED','CRITICAL_PIRACY','UNKNOWN']:
        """
        Check if the domain is authorized for the given organization.
        """
        domain = urlparse(url).netloc.lower()
        if not domain:
            return 'UNKNOWN'
            
        # 1. Check known piracy list
        if any(piracy in domain for piracy in KNOWN_PIRACY_DOMAINS):
            return 'CRITICAL_PIRACY'
            
        # 2. Check authorized domains from DB (mocked for now)
        # In real life: fetch from organizations table.
        authorized_domains = [] # Fetch from organizations.authorized_domains
        if domain in authorized_domains:
            return 'LICENSED'
            
        return 'UNKNOWN'
