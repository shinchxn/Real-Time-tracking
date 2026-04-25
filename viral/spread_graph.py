import networkx as nx
import datetime
from collections import defaultdict
import uuid

class SpreadGraphManager:
    """
    Manages the viral spread graph of an asset using NetworkX.
    Nodes: Asset, Sighting
    Edges: DERIVED_FROM, APPEARED_AT
    """
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_asset(self, asset_id: str, dna_hash: str):
        self.graph.add_node(asset_id, type='Asset', dna_hash=dna_hash, registered_at=datetime.datetime.now())

    def add_sighting(self, asset_id: str, sighting_id: str, url: str, platform: str, score: float, transforms_applied: list):
        # Sighting node
        self.graph.add_node(sighting_id, type='Sighting', url=url, platform=platform, 
                            detected_at=datetime.datetime.now(), score=score, 
                            transforms_applied=transforms_applied)
                            
        # APPEARED_AT edge (Asset -> Sighting)
        self.graph.add_edge(asset_id, sighting_id, type='APPEARED_AT', confidence=score)
        
        # If highly similar, it's a direct derivative
        if score >= 0.87:
            # We assume it originated from the root asset
            self.graph.add_edge(sighting_id, asset_id, type='DERIVED_FROM', similarity=score)

    def get_metrics(self, asset_id: str) -> dict:
        if asset_id not in self.graph:
            return {}
            
        sightings = [n for n in self.graph.successors(asset_id) if self.graph.nodes[n].get('type') == 'Sighting']
        
        if not sightings:
            return {"viral_depth": 0, "viral_width": 0}
            
        viral_width = len(sightings)
        # Depth would be computed if we track sighting-to-sighting derivation. For now, max 1.
        viral_depth = 1 
        
        platforms = defaultdict(int)
        for s in sightings:
            p = self.graph.nodes[s].get('platform', 'unknown')
            platforms[p] += 1
            
        return {
            "viral_depth": viral_depth,
            "viral_width": viral_width,
            "platforms": dict(platforms),
            "total_sightings": viral_width
        }
