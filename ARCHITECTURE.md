# System Architecture & Data Flow

## 🏗️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Browser (React)                         │
│                      Digital Asset Dashboard                         │
│  ┌──────────────────┐  ┌───────────────────┐  ┌─────────────────┐  │
│  │ Upload Section   │  │ Results Display   │  │  Stats Panel    │  │
│  │ (Drag & Drop)    │  │ (Matches & Score) │  │  (Real-time)    │  │
│  └────────┬─────────┘  └────────┬──────────┘  └────────┬────────┘  │
└───────────┼─────────────────────┼──────────────────────┼────────────┘
            │ POST: Upload        │ GET: Results         │ GET: Status
            │ POST: Check         │                      │
            └─────────────────────┼──────────────────────┴──────────┐
                                  │                                 │
┌─────────────────────────────────┴──────────────────────────────────┐
│                       FastAPI Backend (Python)                      │
│                         http://0.0.0.0:8000                         │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ API Endpoints                                                 │ │
│  │ • POST /upload   → Register asset                            │ │
│  │ • POST /check    → Detect matches                            │ │
│  │ • GET /results   → Fetch statistics                          │ │
│  │ • GET /status    → Health check                              │ │
│  │ • GET /          → Service info                              │ │
│  └──────────────────────────┬──────────────────────────────────┘ │
│                             │                                     │
│  ┌──────────────────────────┴──────────────────────────────────┐ │
│  │ Processing Pipeline                                          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│         ↓                    ↓                      ↓              │
│  ┌─────────────┐      ┌─────────────┐      ┌──────────────┐     │
│  │   CLIP      │      │   pHash     │      │ FAISS Vector │     │
│  │ Embeddings  │      │ Perceptual  │      │   Database   │     │
│  │ (512-dim)   │      │   Hashing   │      │              │     │
│  └──────┬──────┘      └──────┬──────┘      └────────┬─────┘     │
│         │                    │                      │            │
│         └────────────────────┼──────────────────────┘            │
│                              ↓                                    │
│                    ┌──────────────────┐                          │
│                    │ Matching Engine  │                          │
│                    │ • Similarity     │                          │
│                    │ • Thresholds     │                          │
│                    │ • Alerts         │                          │
│                    └──────────────────┘                          │
│                              ↓                                    │
│                    ┌──────────────────┐                          │
│                    │   Results        │                          │
│                    │ • Matches        │                          │
│                    │ • Alerts         │                          │
│                    │ • Stats          │                          │
│                    └──────────────────┘                          │
│                                                                   │
└────────────┬────────────────────────────────────────────────────┘
             │ JSON Response
             ↓
      Browser Updates UI
```

---

## 📊 Data Flow: Upload & Registration

```
User Action: Upload File
        │
        ↓
   File Upload (multipart/form-data)
        │
        ├─→ File Validation
        │   • Check type (jpg, png, mp4, etc.)
        │   • Check size (<50MB)
        │   • Reject if invalid
        │
        ├─→ Save to Disk
        │   └→ /data/uploads/{asset_id}_{filename}
        │
        ├─→ Extract Content DNA
        │   ├─→ Load File
        │   ├─→ CLIP Model Inference
        │   │   └→ 512-dim embedding vector
        │   └─→ pHash Generation
        │       └→ 64-bit perceptual hash
        │
        ├─→ Add to Vector Database
        │   ├─→ Index Embedding in FAISS
        │   └─→ Store Metadata (JSON)
        │
        ├─→ Save Index
        │   ├─→ faiss_index.bin (FAISS binary)
        │   └─→ metadata.json (asset info)
        │
        └─→ Return Response
            {
              "asset_id": "uuid",
              "filename": "image.jpg",
              "status": "success"
            }
```

---

## 🔍 Data Flow: Check & Detection

```
User Action: Upload File to Check
        │
        ├─→ Same Validation & DNA Extraction
        │
        ├─→ Query FAISS Index
        │   ├─→ Search for k=5 similar embeddings
        │   ├─→ Compute L2 distances
        │   ├─→ Return top matches with scores
        │   └─→ Search time: ~20-50ms
        │
        ├─→ Match Engine Processing
        │   ├─→ For each match:
        │   │   ├─→ Compute similarity score
        │   │   ├─→ Compare against thresholds
        │   │   ├─→ Determine match type
        │   │   └─→ Generate alert if needed
        │   │
        │   └─→ Aggregate Results
        │       ├─→ Best match
        │       ├─→ All matches (ranked)
        │       └─→ All alerts (by severity)
        │
        └─→ Return Detection Results
            {
              "has_unauthorized_use": true/false,
              "best_match": {...},
              "matches": [...],
              "alerts": [...]
            }
```

---

## 🗄️ Data Storage Architecture

```
Local File System
│
├── /data/
│   ├── uploads/                    # User uploaded files
│   │   └── {asset_id}_{filename}
│   │
│   ├── faiss_index.bin            # FAISS index (binary)
│   │   ├─ 512-dim embeddings
│   │   ├─ Similarity graph
│   │   └─ Scalable to millions
│   │
│   └── metadata.json              # Asset metadata
│       └─ {
│           "0": {
│               "asset_id": "uuid",
│               "filename": "...",
│               "phash": "64hex",
│               "added_timestamp": "...",
│               "file_path": "..."
│           },
│           "1": {...},
│           ...
│         }

In-Memory (while running)
│
├── CLIP Model (2-3GB)
│   └─ Pre-loaded for fast inference
│
└── Vector Database Instance
    └─ FAISS index (shared memory)
```

---

## 🔄 System Interactions

```
┌─────────────────────────────────────────────────────────┐
│ Module: Content DNA Generator (ContentDNAGenerator)    │
├─────────────────────────────────────────────────────────┤
│ Inputs: Image/Video file path                           │
│ Process:                                                │
│ 1. Load image with PIL/cv2                             │
│ 2. Pass through CLIP model                             │
│ 3. Extract 512-dim embedding                           │
│ 4. Compute 64-bit perceptual hash                      │
│ Outputs:                                               │
│ • embedding: np.ndarray (512,)                         │
│ • phash: str (16 hex chars)                            │
│ • shape: tuple (width, height)                         │
│ • format: str (JPEG, PNG, etc.)                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Module: Vector Database (VectorDatabase)               │
├─────────────────────────────────────────────────────────┤
│ Inputs: embedding vector, asset_id, metadata           │
│ Process:                                                │
│ 1. Index embedding in FAISS (L2 distance)             │
│ 2. Store metadata in dict                              │
│ 3. Maintain counter for next ID                        │
│ Outputs:                                               │
│ • index_id: int (auto-increment)                       │
│ • FAISS search results: distance + index               │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Module: Matching Engine (MatchingEngine)               │
├─────────────────────────────────────────────────────────┤
│ Inputs: query embedding, thresholds                    │
│ Process:                                                │
│ 1. Search FAISS for k similar embeddings              │
│ 2. Convert distances to similarity scores              │
│ 3. Filter by query asset ID                            │
│ 4. Classify as match types                             │
│ 5. Generate alerts if threshold exceeded               │
│ Outputs:                                               │
│ • MatchResult objects                                  │
│ • Alert objects                                        │
│ • Statistics (count, avg, max similarity)              │
└─────────────────────────────────────────────────────────┘
```

---

## ⚙️ Processing Pipeline

```
INPUT: Image File
   │
   ├─ Validation
   │  └─ Check: size, type, existence
   │
   ├─ Loading
   │  └─ PIL.Image / cv2.imread
   │
   ├─ CLIP Preprocessing
   │  ├─ Resize to 224x224
   │  ├─ Normalize
   │  └─ Convert to tensor
   │
   ├─ Embedding Extraction
   │  ├─ Forward pass through CLIP
   │  ├─ Get image features
   │  └─ Normalize to unit vector
   │
   ├─ pHash Generation
   │  ├─ Resize to 8x8 grayscale
   │  ├─ Compute DCT
   │  ├─ Compare to mean
   │  └─ Generate 64-bit hash
   │
   ├─ FAISS Indexing
   │  ├─ Convert to float32
   │  ├─ Add to index
   │  └─ Assign index ID
   │
   └─ Metadata Storage
      └─ Store in JSON

OUTPUT: DNA Record
   {
     embedding: 512-dim vector,
     phash: 64-bit hash,
     asset_id: uuid string,
     filename: original filename,
     timestamp: ISO8601
   }

QUERY PIPELINE:
   Similar input processing PLUS:
   │
   ├─ FAISS Search
   │  ├─ Find 5 nearest neighbors
   │  ├─ Get L2 distances
   │  └─ Compute similarities = 1/(1+distance)
   │
   ├─ Similarity Scoring
   │  ├─ Normalize to 0-1
   │  ├─ Compare to thresholds
   │  └─ Classify match type
   │
   └─ Alert Generation
      ├─ Check severity
      ├─ Create alert if needed
      └─ Add to history

OUTPUT: Detection Result
   {
     matches: [{
       asset_id, filename, similarity, type
     }, ...],
     alerts: [{
       severity, message, similarity
     }, ...],
     best_match: {...}
   }
```

---

## 🌐 Frontend Data Flow

```
React App State
│
├─ selectedFile: File | null
├─ results: CheckResponse | null
├─ statistics: ResultsResponse | null
├─ loading: boolean
├─ error: string | null
└─ checkHistory: CheckResponse[]

State Updates:
│
├─ handleUpload(file)
│  └─ POST /upload → refreshStatistics()
│
├─ handleCheck(file)
│  └─ POST /check → setResults() → refreshStatistics()
│
├─ fetchStatistics()
│  └─ GET /results → setStatistics()
│
└─ Periodic refresh
   └─ useEffect: every 10 seconds
```

---

## 📈 Scalability & Performance

```
Single Instance (Current)
├─ Memory: 2-3GB (CLIP model)
├─ CPU: Single process
├─ Requests/sec: ~1-2
└─ Database size: Millions of embeddings

Horizontal Scaling (Future)
├─ Multiple backend instances
├─ Load balancer (nginx, Cloud Load Balancer)
├─ Shared FAISS index
├─ External database (PostgreSQL)
└─ Requests/sec: 10-100+

Cloud Run Auto-scaling
├─ Min instances: 1
├─ Max instances: 100
├─ Concurrency: 80 per instance
└─ Auto-scaling based on requests
```

---

## 🔒 Security Flow

```
HTTP Request
│
├─ CORS Check
│  └─ Origin validation
│
├─ File Validation
│  ├─ File extension check
│  ├─ MIME type check
│  ├─ Size limit check (50MB)
│  └─ Magic number verification
│
├─ Content Processing
│  ├─ Temporary file creation
│  ├─ Safe loading
│  └─ Memory cleanup
│
├─ Response Generation
│  ├─ Data sanitization
│  ├─ Error details limited
│  └─ No sensitive data in response
│
└─ File Cleanup
   └─ Delete temporary files
```

---

## 🎯 Request/Response Cycle

```
Client Request:
POST /check
Content-Type: multipart/form-data
Body: file binary

Server Processing (Total: <1000ms):
│
├─ Parse multipart (10-50ms)
├─ Validate & save (5-20ms)
├─ Extract DNA (200-400ms)
├─ FAISS search (15-50ms)
├─ Generate results (10-50ms)
└─ Serialize JSON (1-10ms)

Server Response:
200 OK
Content-Type: application/json
Body: {
  "query_asset_id": "...",
  "has_unauthorized_use": true/false,
  "best_match": {...},
  "matches": [...],
  "alerts": [...],
  "timestamp": "ISO8601"
}

Client Processing:
├─ Parse JSON (5ms)
├─ Update state (5ms)
├─ Re-render component (10-50ms)
└─ Display results (50-100ms)
```

---

## 📊 Database Growth Model

```
Time → Embeddings Growth

Week 1:   10 assets    → 10 embeddings  (1KB index)
Week 2:   50 assets    → 50 embeddings  (5KB index)
Month 1:  500 assets   → 500 embeddings (50KB index)
Month 3:  5K assets    → 5K embeddings  (500KB index)
Year 1:   100K assets  → 100K embeddings (10MB index)
Year 5:   1M assets    → 1M embeddings  (100MB index)

FAISS scales linearly with number of embeddings.
Index size ≈ embeddings × embedding_dim × 4 bytes
Example: 100K × 512 × 4 = 200MB
```

---

## 🔄 Update & Maintenance

```
Daily Operations:
├─ Monitor logs
├─ Check error rates
└─ Update statistics

Weekly:
├─ Database optimization
├─ Review alert patterns
└─ Performance analysis

Monthly:
├─ FAISS index rebuild (optional)
├─ Archiving old data
└─ Model evaluation

Quarterly:
├─ Model update (if needed)
├─ Security audit
└─ Performance tuning
```

---

This architecture ensures:
✅ **Scalability** - Horizontal scaling ready
✅ **Performance** - Sub-second detection
✅ **Reliability** - Persistent storage
✅ **Security** - Input validation & cleanup
✅ **Maintainability** - Clear data flow
