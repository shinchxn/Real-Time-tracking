"""
SQLAlchemy Models — Content DNA Apex v7.0
Defines the schema for organizations, assets, sightings, custody logs, 
and leaker identifications.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, 
    DateTime, ForeignKey, LargeBinary, Text, 
    Index, Table, CheckConstraint, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Organization(Base):
    __tablename__ = "organizations"
    
    org_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_name = Column(String, nullable=False)
    api_key_hash = Column(String, nullable=False, unique=True)
    private_key_encrypted = Column(LargeBinary, nullable=False)
    public_key_pem = Column(Text, nullable=False)
    aes_key_encrypted = Column(LargeBinary, nullable=False)
    key_fingerprint = Column(String, nullable=False)
    authorized_domains = Column(JSONB, server_default='[]')
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

class RegisteredAsset(Base):
    __tablename__ = "registered_assets"
    
    asset_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.org_id"))
    asset_type = Column(String, CheckConstraint("asset_type IN ('image','video','clip')"))
    original_filename = Column(String)
    dna_vector = Column(LargeBinary)
    watermark_seed = Column(Integer)
    sdna_path = Column(String)
    metadata = Column(JSONB)
    registered_at = Column(DateTime(timezone=True), server_default=text("now()"))

class Sighting(Base):
    __tablename__ = "sightings"
    
    sighting_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    asset_id = Column(UUID(as_uuid=True), ForeignKey("registered_assets.asset_id"))
    platform = Column(String)
    source_url = Column(String)
    author_handle = Column(String)
    fusion_score = Column(Float)
    severity = Column(String, CheckConstraint("severity IN ('CRITICAL','HIGH','MEDIUM','LOW','MISS')"))
    layer_scores = Column(JSONB)
    proof_type = Column(String, CheckConstraint("proof_type IN ('SDNA_CONTAINER_MATCH','CRYPTOGRAPHIC_LAYER_MATCH','FORENSIC_VISUAL_MATCH')"))
    embargo_violation = Column(Boolean, default=False)
    dmca_generated = Column(Boolean, default=False)
    evidence_path = Column(String)
    detected_at = Column(DateTime(timezone=True), server_default=text("now()"))

class CustodyLog(Base):
    __tablename__ = "custody_log"
    
    log_id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    asset_id = Column(UUID(as_uuid=True), ForeignKey("registered_assets.asset_id"))
    event_type = Column(String)
    actor_hash = Column(String)
    prev_entry_hash = Column(String)
    entry_hash = Column(String)
    logged_at = Column(DateTime(timezone=True), server_default=text("now()"))

class Session(Base):
    __tablename__ = "sessions"
    session_id = Column(String, primary_key=True)
    session_data = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"))

# Index definitions
Index("idx_sightings_asset", Sighting.asset_id)
Index("idx_sightings_severity", Sighting.severity)
Index("idx_sightings_detected", Sighting.detected_at.desc())
Index("idx_assets_org", RegisteredAsset.org_id)
