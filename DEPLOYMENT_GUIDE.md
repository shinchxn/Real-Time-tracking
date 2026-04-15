# 🚀 Deployment Guide - Google Cloud

This guide covers deploying the Digital Asset Protection System to Google Cloud Platform.

## Quick Start (5 minutes)

### Prerequisites
- Google Cloud Project with billing enabled
- `gcloud` CLI installed and authenticated
- Docker and Docker Compose (local testing)

---

## ☁️ Deployment Options

### Option 1: Cloud Run (Fastest - Recommended)

**Best for:** Serverless, auto-scaling, pay-per-use pricing

#### Step 1: Prepare Container

```bash
# Login to Google Cloud
gcloud auth configure-docker

# Set project
gcloud config set project YOUR_PROJECT_ID

# Create backend image
docker build -f docker/Dockerfile.backend \
  -t gcr.io/YOUR_PROJECT_ID/asset-protection-backend:v1 .

# Push to Container Registry
docker push gcr.io/YOUR_PROJECT_ID/asset-protection-backend:v1
```

#### Step 2: Deploy Backend

```bash
gcloud run deploy asset-protection-backend \
  --image gcr.io/YOUR_PROJECT_ID/asset-protection-backend:v1 \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --allow-unauthenticated \
  --set-env-vars="DEBUG=False,USE_CUDA=False"
```

Backend URL: `https://asset-protection-backend-xxxxx.run.app`

#### Step 3: Deploy Frontend

```bash
# Build frontend
docker build -f docker/Dockerfile.frontend \
  -t gcr.io/YOUR_PROJECT_ID/asset-protection-frontend:v1 .

# Push
docker push gcr.io/YOUR_PROJECT_ID/asset-protection-frontend:v1

# Deploy
gcloud run deploy asset-protection-frontend \
  --image gcr.io/YOUR_PROJECT_ID/asset-protection-frontend:v1 \
  --platform managed \
  --region us-central1 \
  --memory 512Mi \
  --allow-unauthenticated \
  --set-env-vars="VITE_API_URL=https://asset-protection-backend-xxxxx.run.app"
```

Frontend URL: `https://asset-protection-frontend-yyyyy.run.app`

#### Step 4: Test Deployment

```bash
# Check backend status
curl https://asset-protection-backend-xxxxx.run.app/status

# Check frontend
open https://asset-protection-frontend-yyyyy.run.app
```

---

### Option 2: Compute Engine (Flexible - More Control)

**Best for:** Full control, persistent storage, production workloads

#### Step 1: Create VM Instance

```bash
# Create instance
gcloud compute instances create asset-protection-vm \
  --zone us-central1-a \
  --machine-type e2-standard-4 \
  --image-family debian-12 \
  --image-project debian-cloud \
  --boot-disk-size 50GB \
  --metadata enable-oslogin=true

# Create firewall rules
gcloud compute firewall-rules create allow-asset-protection \
  --allow tcp:8000,tcp:3000,tcp:443,tcp:80 \
  --source-ranges 0.0.0.0/0
```

#### Step 2: SSH into VM

```bash
gcloud compute ssh asset-protection-vm --zone us-central1-a
```

#### Step 3: Install Docker & Deploy

```bash
# Inside VM:
sudo apt update
sudo apt install -y docker.io docker-compose git

# Clone repository
git clone https://github.com/your-org/asset-protection.git
cd asset-protection

# Create .env file
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# Start services
sudo docker-compose up -d

# Check status
sudo docker-compose ps
```

#### Step 4: Get External IP

```bash
gcloud compute instances describe asset-protection-vm \
  --zone us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

Access at: `http://<EXTERNAL_IP>:3000`

---

### Option 3: Kubernetes (GKE - Enterprise)

**Best for:** Large-scale, multi-region, enterprise deployments

#### Step 1: Create GKE Cluster

```bash
# Create cluster
gcloud container clusters create asset-protection \
  --zone us-central1-a \
  --num-nodes 3 \
  --machine-type n1-standard-2 \
  --enable-autoscaling \
  --min-nodes 1 \
  --max-nodes 5

# Get credentials
gcloud container clusters get-credentials asset-protection --zone us-central1-a
```

#### Step 2: Create Kubernetes Manifests

Create `k8s/backend-deployment.yaml`:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: asset-protection-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: gcr.io/YOUR_PROJECT_ID/asset-protection-backend:v1
        ports:
        - containerPort: 8000
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        env:
        - name: DEBUG
          value: "False"
---
apiVersion: v1
kind: Service
metadata:
  name: backend-service
spec:
  selector:
    app: backend
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: LoadBalancer
```

#### Step 3: Deploy

```bash
kubectl apply -f k8s/

# Monitor
kubectl get pods
kubectl logs -f deployment/asset-protection-backend
```

---

## 🗄️ Google Cloud Storage Setup

### Enable Cloud Storage for Uploads

```bash
# Create bucket
gsutil mb gs://asset-protection-uploads

# Set CORS
cat > cors.json << EOF
[
  {
    "origin": ["*"],
    "method": ["GET", "HEAD", "DELETE", "PUT", "POST"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
EOF

gsutil cors set cors.json gs://asset-protection-uploads

# Update backend .env
STORAGE_TYPE=gcs
GCS_BUCKET=asset-protection-uploads
```

---

## 📊 Google Cloud SQL (Optional - Database)

For persistent metadata storage:

```bash
# Create Cloud SQL instance
gcloud sql instances create asset-protection-db \
  --database-version POSTGRES_15 \
  --tier db-f1-micro \
  --region us-central1

# Create database
gcloud sql databases create assets --instance asset-protection-db

# Get connection string
gcloud sql instances describe asset-protection-db --format='get(connectionName)'
```

---

## 🔐 Security Best Practices

### 1. Use Secret Manager

```bash
# Create secrets
echo -n "your-secret-key" | gcloud secrets create clip-model-key --data-file=-

# Reference in deployment:
gcloud run deploy ... --secrets CLIP_KEY=clip-model-key:latest
```

### 2. Setup Cloud IAM

```bash
# Create service account
gcloud iam service-accounts create asset-protection-sa

# Grant permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member serviceAccount:asset-protection-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --role roles/storage.objectViewer
```

### 3. Enable Domain SSL

```bash
# Map custom domain
gcloud run services update-traffic asset-protection-backend \
  --region us-central1
```

---

## 📈 Scale & Performance

### Cloud Run Scaling

```bash
# Increase concurrency
gcloud run deploy asset-protection-backend \
  --concurrency 100 \
  --max-instances 10
```

### Setup Load Balancing

```bash
gcloud compute backend-services create asset-protection-backend-service \
  --protocol HTTP \
  --health-checks basic-check \
  --global

gcloud compute url-maps create asset-protection-load-balancer \
  --default-service=asset-protection-backend-service
```

---

## 📊 Monitoring & Logging

### Cloud Logging

```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision" --limit=50 --format=json

# Create log sink (export to BigQuery)
gcloud logging sinks create asset-protection-logs \
  bigquery.googleapis.com/projects/YOUR_PROJECT_ID/datasets/asset_protection_logs \
  --log-filter='resource.type="cloud_run_revision"'
```

### Cloud Monitoring

```bash
# Create dashboard
gcloud monitoring dashboards create --config='{
  "displayName": "Asset Protection System",
  "gridLayout": {
    "widgets": [
      {
        "title": "Request Latency",
        "xyChart": {
          "dataSets": [{
            "timeSeriesQuery": {
              "timeSeriesFilter": {
                "filter": "metric.type=\"run.googleapis.com/request_latencies\""
              }
            }
          }]
        }
      }
    ]
  }
}'
```

### Alerting

```bash
# Create alert policy
gcloud alpha monitoring policies create \
  --display-name "Backend Error Rate" \
  --condition-display-name "High error rate" \
  --condition-threshold-value 0.05 \
  --notification-channels <CHANNEL_ID>
```

---

## 💰 Cost Optimization

### Cloud Run Pricing (Estimate)

```
Request volume:  1M/month
Memory:          2 GB
Duration:        100s average
Cost:            ~$15-25/month
```

### Optimization Tips

1. **Use cheaper regions**: `us-central1` is 20% cheaper
2. **Reduce memory**: Start with 2GB, scale if needed
3. **Enable compression**: Reduce data transfer
4. **Batch operations**: Group similar requests

### Cost estimation

```bash
# Calculate costs
gcloud billing accounts list
gcloud billing budgets list --billing-account <ACCOUNT_ID>
```

---

## 🔄 CI/CD Pipeline (GitHub Actions)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Cloud SDK
        uses: google-github-actions/setup-gcloud@v0
        with:
          project_id: ${{ secrets.GCP_PROJECT_ID }}
          service_account_key: ${{ secrets.GCP_SA_KEY }}
      
      - name: Build and push backend
        run: |
          docker build -f docker/Dockerfile.backend -t gcr.io/${{ secrets.GCP_PROJECT_ID }}/asset-protection-backend:${{ github.sha }} .
          docker push gcr.io/${{ secrets.GCP_PROJECT_ID }}/asset-protection-backend:${{ github.sha }}
      
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy asset-protection-backend \
            --image gcr.io/${{ secrets.GCP_PROJECT_ID }}/asset-protection-backend:${{ github.sha }} \
            --platform managed \
            --region us-central1
```

---

## ❓ Troubleshooting

### Backend won't start

```bash
# View logs
gcloud run logs read asset-protection-backend

# Check memory
export MEMORY=4Gi
gcloud run deploy asset-protection-backend --memory $MEMORY
```

### CLIP model too slow

```bash
# Use smaller model (for fast prototype)
CLIP_MODEL=ViT-B/16  # Faster than ViT-B/32
```

### Storage quota exceeded

```bash
# Check usage
gsutil du gs://asset-protection-uploads

# Set budget alerts
gcloud billing budgets create --billing-account=<ID> \
  --display-name="Storage Alert" \
  --budget-amount 100
```

---

## 📞 Support & References

- [Google Cloud Documentation](https://cloud.google.com/docs)
- [Cloud Run Guide](https://cloud.google.com/run/docs)
- [GKE Guide](https://cloud.google.com/kubernetes-engine/docs)

---

**Need help?** Open an issue on GitHub or contact support@assetprotection.io
