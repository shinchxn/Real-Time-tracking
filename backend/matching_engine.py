"""
Matching Engine: Real-time similarity detection and alerting
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib
import logging
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of a content match"""
    query_asset_id: str
    matched_asset_id: str
    similarity_score: float
    match_type: str  # "exact", "very_high", "high", "warning"
    matched_filename: str
    query_filename: Optional[str] = None
    timestamp: str = None
    metadata: dict = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Alert:
    """Alert for unauthorized use"""
    alert_id: str
    asset_id: str
    matched_asset_id: str
    similarity_score: float
    severity: str  # "critical", "high", "medium", "low"
    message: str
    timestamp: str
    action_required: bool


class MatchingEngine:
    """Real-time matching and detection engine"""
    
    def __init__(self, vector_db, similarity_threshold: float = 0.85):
        """
        Initialize matching engine
        
        Args:
            vector_db: VectorDatabase instance
            similarity_threshold: Threshold for flagging matches (0-1)
        """
        self.vector_db = vector_db
        self.similarity_threshold = similarity_threshold
        self.warning_threshold = similarity_threshold - 0.10
        self.match_history = []
        self.alerts = []
    
    def detect_match(
        self,
        query_embedding: np.ndarray,
        query_asset_id: str,
        query_filename: str,
        k: int = 5
    ) -> Dict:
        """
        Detect matches for query embedding
        
        Args:
            query_embedding: Vector to search for
            query_asset_id: ID of query asset
            query_filename: Filename of query asset
            k: Number of results to return
            
        Returns:
            Dict with:
                - matches: list of MatchResult
                - alerts: list of Alert (if any matches exceed threshold)
                - best_match: MatchResult or None
                - has_unauthorized_use: bool
        """
        # Search vector database
        search_results = self.vector_db.search(query_embedding, k=k)
        
        if not search_results:
            return {
                'matches': [],
                'alerts': [],
                'best_match': None,
                'has_unauthorized_use': False
            }
        
        matches = []
        alerts_triggered = []
        best_match = None
        has_unauthorized = False
        
        for result in search_results:
            # Skip if it's the same asset
            if result['asset_id'] == query_asset_id:
                continue
            
            similarity = result['similarity_score']
            
            # Determine match type
            if similarity > 0.95:
                match_type = "exact"
            elif similarity > self.similarity_threshold:
                match_type = "very_high"
            elif similarity > self.warning_threshold:
                match_type = "high"
            else:
                match_type = "warning"
            
            match_result = MatchResult(
                query_asset_id=query_asset_id,
                matched_asset_id=result['asset_id'],
                similarity_score=similarity,
                match_type=match_type,
                matched_filename=result['filename'],
                query_filename=query_filename,
                metadata={
                    'l2_distance': result['l2_distance'],
                    'phash': result['phash'],
                    'source_metadata': result['metadata']
                }
            )
            
            matches.append(match_result)
            
            # Track best match
            if best_match is None or similarity > best_match.similarity_score:
                best_match = match_result
            
            # Generate alert if above threshold
            if similarity > self.similarity_threshold:
                alert = self._generate_alert(match_result)
                alerts_triggered.append(alert)
                has_unauthorized = True
                self.alerts.append(alert)
        
        # Record in history
        for match in matches:
            self.match_history.append(match)
        
        return {
            'matches': matches,
            'alerts': alerts_triggered,
            'best_match': best_match,
            'has_unauthorized_use': has_unauthorized
        }
    
    def _generate_alert(self, match: MatchResult) -> Alert:
        """Generate alert for unauthorized use"""
        
        if match.similarity_score > 0.95:
            severity = "critical"
            message = f"CRITICAL: Nearly exact match found ({match.similarity_score:.1%})"
        elif match.similarity_score > self.similarity_threshold:
            severity = "high"
            message = f"HIGH: Strong match detected ({match.similarity_score:.1%})"
        elif match.similarity_score > self.warning_threshold:
            severity = "medium"
            message = f"MEDIUM: Warning - potential unauthorized use ({match.similarity_score:.1%})"
        else:
            severity = "low"
            message = f"LOW: Possible match ({match.similarity_score:.1%})"
        
        alert_id = hashlib.md5(
            f"{match.query_asset_id}{match.matched_asset_id}{match.timestamp}".encode()
        ).hexdigest()[:16]
        
        alert = Alert(
            alert_id=alert_id,
            asset_id=match.query_asset_id,
            matched_asset_id=match.matched_asset_id,
            similarity_score=match.similarity_score,
            severity=severity,
            message=message,
            timestamp=match.timestamp,
            action_required=match.similarity_score > self.similarity_threshold
        )
        
        logger.info(f"Alert generated: {severity} - {message}")
        return alert
    
    def get_statistics(self) -> dict:
        """Get matching statistics"""
        if not self.match_history:
            return {
                'total_matches': 0,
                'unauthorized_count': 0,
                'total_alerts': len(self.alerts),
                'critical_alerts': 0
            }
        
        scores = [m.similarity_score for m in self.match_history]
        unauthorized = [m for m in self.match_history if m.similarity_score > self.similarity_threshold]
        critical_alerts = [a for a in self.alerts if a.severity == "critical"]
        
        return {
            'total_matches': len(self.match_history),
            'unauthorized_count': len(unauthorized),
            'total_alerts': len(self.alerts),
            'critical_alerts': len(critical_alerts),
            'avg_similarity': sum(scores) / len(scores),
            'max_similarity': max(scores),
            'min_similarity': min(scores)
        }



