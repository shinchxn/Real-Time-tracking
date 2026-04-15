"""
FastAPI Backend: Digital Asset Protection System
Main application with endpoints for upload, check, and results
"""
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import shutil
import logging
import uuid
import json
from datetime import datetime

from config import settings
from content_dna import ContentDNAGenerator
from vector_db import VectorDatabase
from matching_engine import MatchingEngine
from storage import storage_manager
from alerts import alert_manager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="AI-Powered Digital Asset Protection with Content DNA"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global components
dna_generator = None
vector_db = None
matching_engine = None

"""
Pydantic models for request/response
"""

class UploadResponse(BaseModel):
    asset_id: str
    filename: str
    status: str
    message: str
    timestamp: str


class CheckRequest(BaseModel):
    asset_id: Optional[str] = None  # If provided, check by ID; otherwise upload needed


class CheckResponse(BaseModel):
    query_asset_id: str
    has_unauthorized_use: bool
    best_match: Optional[dict] = None
    matches: List[dict] = []
    alerts: List[dict] = []
    timestamp: str


class MatchInfo(BaseModel):
    query_asset_id: str
    matched_asset_id: str
    similarity_score: float
    match_type: str
    matched_filename: str
    timestamp: str


class AlertInfo(BaseModel):
    alert_id: str
    asset_id: str
    matched_asset_id: str
    similarity_score: float
    severity: str
    message: str
    timestamp: str


class ResultsResponse(BaseModel):
    total_matches: int
    unauthorized_count: int
    total_alerts: int
    critical_alerts: int
    avg_similarity: float
    matches: List[MatchInfo] = []
    alerts: List[AlertInfo] = []


"""
Lifecycle events
"""

@app.on_event("startup")
async def startup_event():
    """Initialize components on startup"""
    global dna_generator, vector_db, matching_engine
    
    logger.info("=" * 60)
    logger.info("Digital Asset Protection System - Starting Up")
    logger.info("=" * 60)
    
    try:
        # Initialize Content DNA Generator
        logger.info("Initializing Content DNA Generator...")
        dna_generator = ContentDNAGenerator()
        logger.info(f"✓ CLIP model loaded: {settings.CLIP_MODEL}")
        logger.info(f"✓ Device: {settings.DEVICE}")
        
        # Initialize Vector Database
        logger.info("Initializing Vector Database...")
        vector_db = VectorDatabase(embedding_dim=512)  # CLIP ViT-B/32 = 512-dim
        
        # Try to load existing index
        if (os.path.exists(settings.FAISS_INDEX_PATH) and 
            os.path.exists(settings.FAISS_METADATA_PATH)):
            logger.info("Loading existing FAISS index...")
            vector_db.load(settings.FAISS_INDEX_PATH, settings.FAISS_METADATA_PATH)
            logger.info(f"✓ Loaded FAISS index with {vector_db.index.ntotal} embeddings")
        else:
            logger.info("No existing index found. Starting with empty database.")
        
        # Initialize Matching Engine
        matching_engine = MatchingEngine(
            vector_db=vector_db,
            similarity_threshold=settings.SIMILARITY_THRESHOLD
        )
        logger.info(f"✓ Matching Engine initialized")
        logger.info(f"  - Similarity threshold: {settings.SIMILARITY_THRESHOLD}")
        logger.info(f"  - Warning threshold: {settings.WARNING_THRESHOLD}")
        
        logger.info("=" * 60)
        logger.info("✓ System ready")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Save state on shutdown"""
    logger.info("Shutting down... Saving state")
    if vector_db is not None:
        vector_db.save(settings.FAISS_INDEX_PATH, settings.FAISS_METADATA_PATH)
        logger.info("✓ Vector database saved")


"""
API Endpoints
"""

@app.post("/upload", response_model=UploadResponse)
async def upload_asset(file: UploadFile = File(...)) -> UploadResponse:
    """
    Upload and register new digital asset
    
    POST /upload
    - Accepts image/video file
    - Generates Content DNA
    - Stores in vector database
    """
    if dna_generator is None or vector_db is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    asset_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    
    try:
        # Validate file
        if file.filename is None:
            raise HTTPException(status_code=400, detail="Filename required")
        
        file_ext = file.filename.split('.')[-1].lower()
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}"
            )
        
        # Save uploaded file
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(settings.UPLOAD_DIR, f"{asset_id}_{file.filename}")
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Uploaded file: {file.filename} -> {asset_id}")
        
        # Extract Content DNA
        if file_ext in ["mp4", "avi", "mov"]:
            dna_result = dna_generator.extract_video_dna(file_path)
            dna_type = "video"
            
            # Add each frame embedding
            for i, (embedding, phash) in enumerate(
                zip(dna_result['embeddings'], dna_result['phashes'])
            ):
                vector_db.add_embedding(
                    embedding=embedding,
                    asset_id=asset_id,
                    filename=file.filename,
                    phash=phash,
                    metadata={
                        'type': 'video',
                        'frame_index': i,
                        'fps': dna_result['fps']
                    }
                )
        else:
            dna_result = dna_generator.extract_content_dna(file_path)
            dna_type = "image"
            
            # Add single embedding
            vector_db.add_embedding(
                embedding=dna_result['embedding'],
                asset_id=asset_id,
                filename=file.filename,
                phash=dna_result['phash'],
                metadata={
                    'type': 'image',
                    'shape': dna_result['shape'],
                    'format': dna_result['format']
                }
            )
        
        # Upload to permanent storage (GCS or Local copy)
        final_path = storage_manager.upload_file(file_path, f"{asset_id}_{file.filename}")
        
        # Update metadata with final storage path
        # In a real system, we'd update the vector_db metadata here
        
        # Save database
        vector_db.save(settings.FAISS_INDEX_PATH, settings.FAISS_METADATA_PATH)
        
        logger.info(f"Asset registered: {asset_id} ({dna_type}) stored at {final_path}")
        
        return UploadResponse(
            asset_id=asset_id,
            filename=file.filename,
            status="success",
            message=f"Asset uploaded and registered. DNA extracted.",
            timestamp=timestamp
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        # Cleanup file on error
        try:
            os.remove(file_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/check", response_model=CheckResponse)
async def check_similarity(file: UploadFile = File(...)) -> CheckResponse:
    """
    Check uploaded media for similarity matches
    
    POST /check
    - Accepts image/video file
    - Searches for similar content in database
    - Returns matches and alerts
    """
    if dna_generator is None or vector_db is None or matching_engine is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    query_asset_id = str(uuid.uuid4())
    timestamp = datetime.utcnow().isoformat()
    
    try:
        # Validate and save file
        if file.filename is None:
            raise HTTPException(status_code=400, detail="Filename required")
        
        file_ext = file.filename.split('.')[-1].lower()
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="File type not allowed")
        
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(settings.UPLOAD_DIR, f"query_{query_asset_id}_{file.filename}")
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Received query: {file.filename}")
        
        # Extract DNA and check
        if file_ext in ["mp4", "avi", "mov"]:
            dna_result = dna_generator.extract_video_dna(file_path)
            embeddings = dna_result['embeddings']
        else:
            dna_result = dna_generator.extract_content_dna(file_path)
            embeddings = [dna_result['embedding']]
        
        # Aggregate results across all embeddings
        all_matches = []
        all_alerts = []
        best_match = None
        has_unauthorized = False
        
        for i, embedding in enumerate(embeddings):
            detection_result = matching_engine.detect_match(
                query_embedding=embedding,
                query_asset_id=query_asset_id,
                query_filename=file.filename,
                k=5
            )
            
            all_matches.extend(detection_result['matches'])
            all_alerts.extend(detection_result['alerts'])
            
            if detection_result['has_unauthorized_use']:
                has_unauthorized = True
                
                if (best_match is None or 
                    detection_result['best_match'].similarity_score > best_match.similarity_score):
                    best_match = detection_result['best_match']
        
        # Format response
        matches_data = [
            {
                'query_asset_id': m.query_asset_id,
                'matched_asset_id': m.matched_asset_id,
                'similarity_score': m.similarity_score,
                'match_type': m.match_type,
                'matched_filename': m.matched_filename
            }
            for m in all_matches
        ]
        
        alerts_data = [
            {
                'alert_id': a.alert_id,
                'asset_id': a.asset_id,
                'matched_asset_id': a.matched_asset_id,
                'similarity_score': a.similarity_score,
                'severity': a.severity,
                'message': a.message
            }
            for a in all_alerts
        ]
        
        best_match_data = None
        if best_match:
            best_match_data = {
                'query_asset_id': best_match.query_asset_id,
                'matched_asset_id': best_match.matched_asset_id,
                'similarity_score': best_match.similarity_score,
                'match_type': best_match.match_type,
                'matched_filename': best_match.matched_filename
            }
        
        logger.info(
            f"Detection complete: unauthorized={has_unauthorized}, "
            f"matches={len(all_matches)}, alerts={len(all_alerts)}"
        )
        
        # Async background alerts
        if has_unauthorized and settings.ALERT_ENABLED:
            background_tasks.add_task(send_bulk_alerts, all_alerts)
        
        return CheckResponse(
            query_asset_id=query_asset_id,
            has_unauthorized_use=has_unauthorized,
            best_match=best_match_data,
            matches=matches_data,
            alerts=alerts_data,
            timestamp=timestamp
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Check failed: {e}")
        try:
            os.remove(file_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Check failed: {str(e)}")


@app.get("/results", response_model=ResultsResponse)
async def get_results() -> ResultsResponse:
    """
    Get detection results and statistics
    
    GET /results
    - Returns aggregated statistics
    - Lists recent matches and alerts
    """
    if matching_engine is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        stats = matching_engine.get_statistics()
        
        # Get recent matches and alerts
        recent_matches = [
            MatchInfo(
                query_asset_id=m.query_asset_id,
                matched_asset_id=m.matched_asset_id,
                similarity_score=m.similarity_score,
                match_type=m.match_type,
                matched_filename=m.matched_filename,
                timestamp=m.timestamp
            )
            for m in matching_engine.match_history[-50:]  # Last 50
        ]
        
        recent_alerts = [
            AlertInfo(
                alert_id=a.alert_id,
                asset_id=a.asset_id,
                matched_asset_id=a.matched_asset_id,
                similarity_score=a.similarity_score,
                severity=a.severity,
                message=a.message,
                timestamp=a.timestamp
            )
            for a in matching_engine.alerts[-50:]  # Last 50
        ]
        
        return ResultsResponse(
            total_matches=stats['total_matches'],
            unauthorized_count=stats['unauthorized_count'],
            total_alerts=stats['total_alerts'],
            critical_alerts=stats['critical_alerts'],
            avg_similarity=stats.get('avg_similarity', 0.0),
            matches=recent_matches,
            alerts=recent_alerts
        )
    
    except Exception as e:
        logger.error(f"Results retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get results: {str(e)}")


async def send_bulk_alerts(alerts: List[dict]):
    """Send multiple alerts asynchronously"""
    for alert in alerts:
        await alert_manager.send_alert(alert)


@app.get("/status")
async def get_status() -> dict:
    """Get system status"""
    try:
        if vector_db is None:
            return {"status": "initializing"}
        
        db_stats = vector_db.get_stats()
        engine_stats = matching_engine.get_statistics() if matching_engine else {}
        
        return {
            "status": "healthy",
            "database": db_stats,
            "detection": engine_stats,
            "config": {
                "similarity_threshold": settings.SIMILARITY_THRESHOLD,
                "device": settings.DEVICE,
                "clip_model": settings.CLIP_MODEL
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Digital Asset Protection System",
        "version": settings.API_VERSION,
        "status": "running",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
