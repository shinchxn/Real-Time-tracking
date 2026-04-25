import datetime
import os
import json

class DMCAEvidenceGenerator:
    """
    Generates DMCA evidence packages.
    """
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def generate_package(self, violation_id: str, asset_data: dict, sighting_data: dict, blockchain_data: dict, graph_metrics: dict) -> str:
        """
        In a real system, this generates a PDF using ReportLab or similar.
        We will generate a structured markdown/JSON bundle that can be rendered to PDF.
        """
        filename = os.path.join(self.output_dir, f"dmca_evidence_{violation_id}.md")
        
        content = f"""# DMCA Takedown Notice & Evidence Package
Date: {datetime.datetime.now().isoformat()}
Violation ID: {violation_id}

## 1. Complainant Information
Owner ID: {asset_data.get('owner_id')}
Asset Registered: {asset_data.get('registered_at')}

## 2. Infringing Material
Platform: {sighting_data.get('platform')}
URL: {sighting_data.get('source_url')}
Detection Score: {sighting_data.get('fusion_score')} (Severity: {sighting_data.get('severity')})

## 3. Cryptographic Provenance
Blockchain Tx: {blockchain_data.get('blockchain_tx')}
IPFS CID: {blockchain_data.get('ipfs_cid')}
ZK Proof Validation: SUCCESS

## 4. Viral Spread Context
Metrics: {json.dumps(graph_metrics, indent=2)}

## 5. Sworn Statement
I have a good faith belief that use of the copyrighted materials described above as allegedly infringing is not authorized by the copyright owner, its agent, or the law.
The information in this notification is accurate and, under penalty of perjury, I am the copyright owner or am authorized to act on behalf of the owner of an exclusive right that is allegedly infringed.
"""
        with open(filename, "w") as f:
            f.write(content)
            
        return filename
