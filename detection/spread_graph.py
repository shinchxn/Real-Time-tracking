"""
Viral Spread Graph Manager
Maps the 'infection tree' of a digital asset across platforms.
Calculates reach, identifies original source, and tracks velocity.
"""
import networkx as nx
import logging
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

class SpreadGraph:
    def __init__(self, asset_id: str):
        self.asset_id = asset_id
        self.graph = nx.DiGraph()
        
    def add_incident(self, incident_id: str, platform: str, url: str, timestamp: str, reach: int = 0, parent_id: str = None):
        """Add a violation incident to the graph."""
        self.graph.add_node(
            incident_id, 
            platform=platform, 
            url=url, 
            timestamp=timestamp, 
            reach=reach
        )
        
        if parent_id and self.graph.has_node(parent_id):
            self.graph.add_edge(parent_id, incident_id)
        elif self.graph.number_of_nodes() > 1:
            # Try to find 'parent' by earliest timestamp if not specified
            # This is a heuristic for spread mapping
            nodes = sorted(
                [n for n in self.graph.nodes(data=True) if n[0] != incident_id],
                key=lambda x: x[1]['timestamp']
            )
            if nodes:
                self.graph.add_edge(nodes[0][0], incident_id)

    def get_stats(self) -> Dict:
        """Calculate graph-wide stats for damages/reach."""
        total_reach = sum(nx.get_node_attributes(self.graph, 'reach').values())
        platforms = set(nx.get_node_attributes(self.graph, 'platform').values())
        
        return {
            "asset_id": self.asset_id,
            "total_incidents": self.graph.number_of_nodes(),
            "total_estimated_reach": total_reach,
            "platform_count": len(platforms),
            "spread_depth": nx.dag_longest_path_length(self.graph) if self.graph.number_of_nodes() > 0 else 0
        }

    def export_graph(self):
        """Export for visualization in the dashboard (v3 Apex)."""
        return nx.node_link_data(self.graph)
