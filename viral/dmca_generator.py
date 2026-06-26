"""
DMCA Generator — Content DNA Apex v7.1
FIX 27: Implemented DMCAGenerator with Jinja2 template rendering.
Matches call signature in background_tasks.py generate_dmca():
    generator = DMCAGenerator()
    notice_html = generator.generate_notice(
        asset=asset_record, sighting=sighting_record,
        org=org_record, fusion_score=0.95
    )
"""
import os
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DMCAGenerator:
    """
    Generates HTML DMCA takedown notices using Jinja2 templates.
    Falls back to inline template if Jinja2 is unavailable.
    """

    def __init__(self):
        from config import settings
        self.template_path = settings.DMCA_TEMPLATE_PATH
        self.sender_name = settings.DMCA_SENDER_NAME
        self.sender_email = settings.DMCA_SENDER_EMAIL

        # Ensure template file exists; create default if not
        self._ensure_template()

    def _ensure_template(self):
        """Create a default DMCA template if the configured one doesn't exist."""
        if not os.path.exists(self.template_path):
            os.makedirs(os.path.dirname(self.template_path), exist_ok=True)
            with open(self.template_path, "w", encoding="utf-8") as f:
                f.write(self._default_template())
            logger.info("[DMCAGenerator] Created default template at %s", self.template_path)

    def _default_template(self) -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>DMCA Takedown Notice</title>
<style>body{font-family:Arial,sans-serif;max-width:800px;margin:40px auto;line-height:1.6;color:#222}
h1{color:#c00}h2{color:#333;border-bottom:1px solid #ccc;padding-bottom:4px}
code{background:#f4f4f4;padding:2px 5px;border-radius:3px;font-size:.9em}</style>
</head>
<body>
<h1>DMCA Takedown Notice</h1>
<p><b>Date:</b> {{ generated_at }}</p>

<h2>Copyrighted Work</h2>
<p>Asset ID: <code>{{ asset_id }}</code> &nbsp;|&nbsp; File: <b>{{ filename }}</b></p>
<p>DNA Hash: <code>{{ dna_hash }}</code></p>
<p>IPFS CID: <code>{{ ipfs_cid }}</code></p>
<p>Registered: {{ registered_at }}</p>

<h2>Infringing Material</h2>
<p>URL: <a href="{{ infringing_url }}">{{ infringing_url }}</a></p>
<p>Platform: <b>{{ platform }}</b> &nbsp;|&nbsp; Detected: {{ detected_at }}</p>
<p>Forensic Confidence: <b>{{ fusion_score }}</b></p>

<h2>Rights Holder</h2>
<p><b>{{ org_name }}</b> &mdash; <a href="mailto:{{ sender_email }}">{{ sender_email }}</a></p>

<h2>Sworn Statement</h2>
<p>I have a good faith belief that the use of the copyrighted material described above,
as allegedly infringing, is not authorized by the copyright owner, its agent, or the law.
The information in this notification is accurate and, under penalty of perjury, I am the
copyright owner or am authorized to act on behalf of the owner of an exclusive right
that is allegedly infringed.</p>

<p>Signed: <b>{{ org_name }}</b> | {{ generated_at }}</p>
</body>
</html>
"""

    def generate_notice(
        self,
        asset: Dict[str, Any],
        sighting: Dict[str, Any],
        org: Dict[str, Any],
        fusion_score: float
    ) -> str:
        """
        Generate an HTML DMCA notice.

        Args:
            asset: Asset record dict (asset_id, filename, dna_hash, ipfs_cid, created_at)
            sighting: Sighting record dict (source_url, platform, detected_at)
            org: Org record dict (org_name)
            fusion_score: float 0.0–1.0

        Returns:
            HTML string
        """
        context = {
            "asset_id": asset.get("asset_id", ""),
            "filename": asset.get("filename", asset.get("original_filename", "")),
            "dna_hash": asset.get("dna_hash", ""),
            "ipfs_cid": asset.get("ipfs_cid", ""),
            "registered_at": asset.get("created_at", asset.get("registered_at", "")),
            "infringing_url": sighting.get("source_url", ""),
            "platform": sighting.get("platform", ""),
            "detected_at": sighting.get("detected_at", datetime.utcnow().isoformat()),
            "fusion_score": f"{fusion_score:.2%}",
            "org_name": org.get("org_name", self.sender_name),
            "sender_email": self.sender_email,
            "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        }

        try:
            from jinja2 import Environment, FileSystemLoader, select_autoescape
            env = Environment(
                loader=FileSystemLoader(os.path.dirname(os.path.abspath(self.template_path))),
                autoescape=select_autoescape(["html"])
            )
            template = env.get_template(os.path.basename(self.template_path))
            return template.render(**context)
        except Exception as e:
            logger.warning("[DMCAGenerator] Jinja2 rendering failed: %s. Using fallback.", e)
            # Fallback: simple string substitution
            html = self._default_template()
            for key, value in context.items():
                html = html.replace("{{ " + key + " }}", str(value))
            return html


# ── Legacy DMCAEvidenceGenerator — kept for backward compatibility ────────────

class DMCAEvidenceGenerator:
    """Legacy class — use DMCAGenerator for new code."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_package(
        self,
        violation_id: str,
        asset_data: dict,
        sighting_data: dict,
        blockchain_data: dict,
        graph_metrics: dict
    ) -> str:
        import json
        filename = os.path.join(self.output_dir, f"dmca_evidence_{violation_id}.md")
        content = f"""# DMCA Takedown Notice & Evidence Package
Date: {datetime.now().isoformat()}
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

## 4. Viral Spread Context
Metrics: {json.dumps(graph_metrics, indent=2)}

## 5. Sworn Statement
I have a good faith belief that use of the copyrighted materials described above
as allegedly infringing is not authorized by the copyright owner, its agent, or the law.
"""
        with open(filename, "w") as f:
            f.write(content)
        return filename
