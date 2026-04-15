# API Quick Reference

## Base URL
```
http://localhost:8000  (Local)
https://asset-protection-backend-xxxxx.run.app  (Cloud Run)
```

## Authentication
Currently no auth required for MVP. Production: Add API keys/JWT.

---

## Endpoints

### 1. Upload Asset
Register new asset to database

```http
POST /upload
Content-Type: multipart/form-data

body:
  file: <image/video file>
```

**cURL Example:**
```bash
curl -X POST \
  -F "file=@my_image.jpg" \
  http://localhost:8000/upload
```

**Response (200):**
```json
{
  "asset_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "my_image.jpg",
  "status": "success",
  "message": "Asset uploaded and registered. DNA extracted.",
  "timestamp": "2024-04-14T10:30:00.000Z"
}
```

---

### 2. Check for Matches
Search for similar content

```http
POST /check
Content-Type: multipart/form-data

body:
  file: <image/video file to check>
```

**cURL Example:**
```bash
curl -X POST \
  -F "file=@suspicious.jpg" \
  http://localhost:8000/check
```

**Response (200):**
```json
{
  "query_asset_id": "550e8400-e29b-41d4-a716-446655440001",
  "has_unauthorized_use": true,
  "best_match": {
    "query_asset_id": "550e8400-e29b-41d4-a716-446655440001",
    "matched_asset_id": "550e8400-e29b-41d4-a716-446655440000",
    "similarity_score": 0.92,
    "match_type": "very_high",
    "matched_filename": "my_image.jpg"
  },
  "matches": [
    {
      "query_asset_id": "550e8400-e29b-41d4-a716-446655440001",
      "matched_asset_id": "550e8400-e29b-41d4-a716-446655440000",
      "similarity_score": 0.92,
      "match_type": "very_high",
      "matched_filename": "my_image.jpg"
    }
  ],
  "alerts": [
    {
      "alert_id": "abc123def456",
      "asset_id": "550e8400-e29b-41d4-a716-446655440001",
      "matched_asset_id": "550e8400-e29b-41d4-a716-446655440000",
      "similarity_score": 0.92,
      "severity": "high",
      "message": "HIGH: Strong match detected (92.0%)",
      "timestamp": "2024-04-14T10:30:00.000Z"
    }
  ],
  "timestamp": "2024-04-14T10:30:00.000Z"
}
```

---

### 3. Get Results
Retrieve aggregated statistics

```http
GET /results
```

**cURL Example:**
```bash
curl http://localhost:8000/results
```

**Response (200):**
```json
{
  "total_matches": 42,
  "unauthorized_count": 8,
  "total_alerts": 12,
  "critical_alerts": 2,
  "avg_similarity": 0.78,
  "matches": [
    {
      "query_asset_id": "uuid",
      "matched_asset_id": "uuid",
      "similarity_score": 0.92,
      "match_type": "very_high",
      "matched_filename": "image1.jpg",
      "timestamp": "2024-04-14T10:30:00.000Z"
    }
  ],
  "alerts": [...]
}
```

---

### 4. System Status
Health check and configuration

```http
GET /status
```

**cURL Example:**
```bash
curl http://localhost:8000/status
```

**Response (200):**
```json
{
  "status": "healthy",
  "database": {
    "total_embeddings": 150,
    "embedding_dim": 512,
    "metadata_entries": 50,
    "id_counter": 150
  },
  "detection": {
    "total_matches": 42,
    "unauthorized_count": 8,
    "total_alerts": 12,
    "critical_alerts": 2,
    "avg_similarity": 0.78,
    "max_similarity": 0.98,
    "min_similarity": 0.52
  },
  "config": {
    "similarity_threshold": 0.85,
    "device": "cpu",
    "clip_model": "ViT-B/32"
  }
}
```

---

### 5. Root (Service Info)
Basic service information

```http
GET /
```

**Response (200):**
```json
{
  "service": "Digital Asset Protection System",
  "version": "1.0.0",
  "status": "running",
  "docs": "/docs"
}
```

---

## Response Codes

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Asset uploaded/checked successfully |
| 400 | Bad Request | Invalid file type, missing fields |
| 413 | Payload Too Large | File exceeds 50MB limit |
| 500 | Server Error | Processing failed |
| 503 | Service Unavailable | System not initialized |

---

## File Formats

### Supported
- **Images**: JPG, JPEG, PNG, GIF, BMP, WebP
- **Videos**: MP4, AVI, MOV

### Limits
- **Max Size**: 50MB
- **Min Size**: 1KB
- **Duration**: No limit (sampled at 30 frame intervals)

---

## Similarity Scoring

```
Score     Meaning           Action
-------   ---------------   -----------
0.95-1.0  Exact match       CRITICAL - Likely duplicate
0.85-0.95 Very high         HIGH - Probable unauthorized
0.75-0.85 High              MEDIUM - Review recommended
0.50-0.75 Moderate          LOW - Informational
0.0-0.50  Low/No match      None - Different content
```

---

## Python Client Example

```python
import requests
import json

BASE_URL = "http://localhost:8000"

# Upload asset
def upload_asset(file_path):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(f"{BASE_URL}/upload", files=files)
    return response.json()

# Check for matches
def check_image(file_path):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(f"{BASE_URL}/check", files=files)
    return response.json()

# Get statistics
def get_stats():
    response = requests.get(f"{BASE_URL}/results")
    return response.json()

# Usage
if __name__ == "__main__":
    # Register original
    result = upload_asset("original.jpg")
    print(f"Uploaded: {result['asset_id']}")
    
    # Check suspicious image
    matches = check_image("suspicious.jpg")
    if matches['has_unauthorized_use']:
        print(f"⚠️ Match found! Similarity: {matches['best_match']['similarity_score']:.1%}")
    
    # View stats
    stats = get_stats()
    print(f"Total alerts: {stats['total_alerts']}")
```

---

## JavaScript/Fetch Example

```javascript
const BASE_URL = "http://localhost:8000";

// Upload asset
async function uploadAsset(file) {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch(`${BASE_URL}/upload`, {
    method: 'POST',
    body: formData
  });
  return await response.json();
}

// Check for matches
async function checkImage(file) {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch(`${BASE_URL}/check`, {
    method: 'POST',
    body: formData
  });
  return await response.json();
}

// Get statistics
async function getStats() {
  const response = await fetch(`${BASE_URL}/results`);
  return await response.json();
}

// Usage
async function main() {
  const fileInput = document.querySelector('input[type="file"]');
  const file = fileInput.files[0];
  
  const result = await checkImage(file);
  console.log(result);
}
```

---

## Batch Processing (Pseudo-code)

```python
# Scan multiple files
import os
from pathlib import Path

def batch_check(directory):
    results = []
    for file in Path(directory).glob('*.jpg'):
        match = check_image(str(file))
        if match['has_unauthorized_use']:
            results.append({
                'file': file.name,
                'match': match['best_match']
            })
    return results

# Process 1000 files
unauthorized = batch_check('./uploads')
print(f"Found {len(unauthorized)} unauthorized uses")
```

---

## Rate Limiting

Currently no rate limits. Production deployment should implement:
- 100 requests/minute per IP
- 10MB/second upload bandwidth

---

## Error Handling

```python
try:
    response = requests.post(f"{BASE_URL}/check", files=files)
    response.raise_for_status()
    data = response.json()
except requests.exceptions.Timeout:
    print("Request timeout (5 min limit)")
except requests.exceptions.RequestException as e:
    print(f"Error: {e}")
```

---

## Interactive API Documentation

Swagger UI: `http://localhost:8000/docs`
ReDoc: `http://localhost:8000/redoc`

---

**Version**: v1.0.0  
**Last Updated**: April 2024
