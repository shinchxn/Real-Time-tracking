# Content DNA Apex — v8.0 Full Power Prototype

Content DNA Apex is a high-accuracy, self-hosted forensic pipeline for real-time digital asset tracking, AI manipulation detection, and advanced robust watermarking. Built with a FastAPI backend and Celery workers, it provides an enterprise-grade API to protect, verify, and trace digital media across the web.

---

## 🚀 Key Features

### 1. 6-Layer Forensic DNA Fingerprinting
Extracts and combines multiple semantic and structural features to create a robust asset identity:
- **Semantic:** CLIP embeddings (auto-selecting `vit-base-patch32` or `vit-large-patch14`).
- **Structural:** pHash (perceptual hashing).
- **Frequency:** DCT frequency signature.
- **Attention:** CLIP patch-level spatial attention grid.
- **Color:** HSV color moments.
- **Edges:** HOG (Histogram of Oriented Gradients) descriptors.

*These features are combined using custom fusion weights to achieve high-recall detection even when images are cropped, filtered, or compressed.*

### 2. Triple-Layer Robust Watermarking
Assets are embedded with an invisible, resilient identity payload:
- **Layer A (DCT):** 256-bit 2-stage PN sequence embedded in the frequency domain (survives JPEG compression).
- **Layer B (DWT):** Redundant wavelet domain watermark (survives social media resizing and cropping).
- **Layer C (LSB):** High-speed steganographic fingerprint in the blue channel.
- **Layer D (XMP):** Standard cryptographic metadata signature.

### 3. AI Manipulation & Clone Detection
Analyzes content for synthetic origins and deepfake manipulations:
- **Deepfake Detector:** Evaluates Laplacian variance heuristics to detect facial manipulations and GAN artifacts.
- **Diffusion Detector:** Uses Discrete Wavelet Transform (DWT LL3) spectral analysis to identify latent diffusion model signatures.
- **AI Clone Detection:** Identifies semantic matches (high CLIP similarity) that are structurally disjoint (low pHash) from registered assets.

### 4. Viral Spread Tracking & DMCA Automation
- **Real-Time Graph:** Uses `NetworkX` to maintain an in-memory spread graph of content sightings.
- **Timeline & Platforms:** Tracks chronological sightings and per-platform distributions.
- **DMCA Generator:** Automatically generates formatted DMCA takedown notices using Jinja2 templates based on high-confidence infringement sightings.

### 5. Web3 Blockchain Anchoring & ZK Proofs
- **Polygon Registry:** Queues background Celery tasks to asynchronously anchor Content DNA hashes to a smart contract on the Polygon network.
- **ZK Proofs:** Generates zero-knowledge proofs demonstrating asset ownership without revealing the underlying master key.

---

## 🏗️ Architecture

```mermaid
graph TD
    subgraph Client
        UI[Frontend / Dashboard]
        API_Clients[API Consumers]
    end

    subgraph API_Gateway
        Upload["/api/v1/upload"]
        Detect["/api/v1/detect"]
        Watermark["/api/v1/watermark"]
        AI_Detect["/api/v1/ai"]
        Viral["/api/v1/viral"]
        Blockchain["/api/v1/blockchain"]
    end

    subgraph Core_Engine
        DNA[Forensic DNA Extractor]
        WM[Watermark Embed / Extract]
        Fusion[Fusion Scoring]
        Graph[NetworkX Spread Graph]
    end

    subgraph Storage_and_Indexing
        FAISS[(FAISS Vector Index)]
        Postgres[(PostgreSQL Metadata)]
        Redis[(Redis Broker / Cache)]
    end

    subgraph Background_Workers
        Task_Anchor[Blockchain Anchor]
        Task_DMCA[DMCA Generator]
        Task_Rescan[Deep Rescan]
    end

    Client --> API_Gateway
    Upload --> DNA
    Upload --> WM
    Detect --> DNA
    Detect --> FAISS
    Detect --> Fusion
    Fusion --> Graph
    Upload --> FAISS
    
    API_Gateway --> Core_Engine
    Core_Engine --> Storage_and_Indexing
    
    Redis --> Background_Workers
    Task_Anchor -.-> Polygon[Polygon Network]
```

### Tech Stack
- **Web Framework:** FastAPI, Uvicorn, Pydantic
- **Machine Learning:** PyTorch, HuggingFace Transformers, FAISS
- **Computer Vision & Signal Processing:** OpenCV, Pillow, PyWavelets (pywt), ImageHash
- **Asynchronous Workers:** Celery, Redis
- **Database:** PostgreSQL (asyncpg), SQLAlchemy
- **Data Structures:** NetworkX (Graphs)
- **Web3:** web3.py

---

## 🛠️ Installation & Quickstart

### Prerequisites
- Docker & Docker Compose
- Python 3.10+ (if running locally without Docker)

### 1. Environment Setup
Create a `.env` file in the root directory:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/contentdna
REDIS_URL=redis://localhost:6379/0
REDIS_RESULT_URL=redis://localhost:6379/1
WATERMARK_MASTER_SEED=0xDEADBEEF
FRONTEND_URL=http://localhost:3000
BLOCKCHAIN_PRIVATE_KEY=
CONTRACT_ADDRESS=
WEB3_RPC_URL=https://polygon-rpc.com
```

### 2. Start Services via Docker Compose
The provided `docker-compose.yml` spins up PostgreSQL, Redis, the FastAPI application, and Celery workers.
```bash
docker-compose up -d
```

### 3. Initialize Database
Apply the initial schema migrations:
```bash
psql postgresql://postgres:postgres@localhost:5432/contentdna -f storage/migrations/001_initial.sql
```

### 4. Verify API
The API should now be running locally. Visit the interactive Swagger UI:
- **Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** `GET http://localhost:8000/api/v1/health`

---

## 📡 Core API Endpoints

### Registration & Upload
- `POST /api/v1/upload` - Extract DNA, register in FAISS, embed watermarks, and queue blockchain anchor.

### Detection & Forensics
- `POST /api/v1/detect` - Check an image against the FAISS index for matches and run AI heuristics.
- `POST /api/v1/verify` - Extract and verify the DCT watermark payload from an image.
- `POST /api/v1/check-url` - Run detection pipeline on an image from a public URL.

### AI Capabilities
- `POST /api/v1/ai/detect-generated` - Detect diffusion artifacts.
- `POST /api/v1/ai/detect-manipulation` - Detect deepfake / GAN manipulation.
- `POST /api/v1/ai/detect-clone` - Detect semantic clones of registered assets.

### Viral Spread & Blockchain
- `GET /api/v1/viral/{asset_id}` - Get NetworkX spread graph metrics.
- `POST /api/v1/dmca/generate/{sighting_id}` - Auto-generate DMCA notice.
- `POST /api/v1/blockchain/register/{asset_id}` - Manually trigger Polygon anchoring.

---

## ⚙️ Development & Customization

- **FAISS Configuration:** The `FAISSIndex` uses `IndexIVFPQ` for memory-efficient scaling. Configurable via `config.py` (nlist, nprobe).
- **Fusion Weights:** Tweak the multi-modal fusion scoring weights in `detection/fusion.py` to adjust sensitivity.
- **Data Persistence:** FAISS vectors and NetworkX graph data are persisted periodically. Ensure `./data` is mounted to a persistent volume.