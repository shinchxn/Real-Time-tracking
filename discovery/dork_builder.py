"""
Dork Builder — Content DNA Apex v7.0
Generates targeted Google Dorking queries for asset hunting.
"""
from typing import List, Dict

DORK_TEMPLATES = [
    'filetype:jpg "{org_name}" -{official_domain}',
    'filetype:png "{event_name}" -{official_domain}',
    'inurl:upload "{league_name}" highlight',
    'site:reddit.com "{org_name}" highlights',
    'site:twitter.com "{event_name}" media',
    'site:instagram.com "{hashtag}"',
    '"stolen from" OR "found online" "{org_name}" sport',
    '"{asset_id_prefix}" OR "{wm_fingerprint_hex[:8]}"',
    'site:streameast.live OR site:sportsurge.net "{league_name}"',
    '"{event_name}" "stream" OR "download" OR "full match" -"{official_domain}"',
]

class DorkBuilder:
    @staticmethod
    def build_dork_queries(asset_metadata: Dict) -> List[str]:
        """
        Generate 8-12 targeted queries per asset.
        """
        org_name = asset_metadata.get("org_name", "Sports")
        event_name = asset_metadata.get("event", "Match")
        league_name = asset_metadata.get("league", "")
        official_domain = asset_metadata.get("official_domain", "official.com")
        asset_id = asset_metadata.get("asset_id", "00000000")
        
        queries = []
        
        # 1. Official Templates
        for template in DORK_TEMPLATES:
            query = template.format(
                org_name=org_name,
                event_name=event_name,
                league_name=league_name,
                official_domain=official_domain,
                hashtag=asset_metadata.get("seed_hashtags", ["sport"])[0],
                asset_id_prefix=asset_id[:8],
                wm_fingerprint_hex="00000000" # Placeholder
            )
            queries.append(query)
            
        # 2. Player-specific queries
        players = asset_metadata.get("player_names", [])
        for player in players[:2]:
            queries.append(f'"{player}" "{event_name}" highlight -{official_domain}')
            
        # 3. Dynamic keywords
        keywords = asset_metadata.get("event_keywords", [])
        if keywords:
            queries.append(f'"{event_name}" {" OR ".join(keywords[:3])} -{official_domain}')
            
        return queries[:12]
