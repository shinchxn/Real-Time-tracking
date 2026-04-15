# Integration Examples

## Real-World Use Cases & Code Samples

---

## 1. Web Scraper - Detect Unauthorized Reposts

```python
import requests
import asyncio
from PIL import Image
from io import BytesIO

class WebScraper:
    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url
    
    async def check_url(self, image_url):
        """Download image from URL and check"""
        try:
            # Download image
            response = requests.get(image_url, timeout=10)
            img = Image.open(BytesIO(response.content))
            
            # Save temp
            temp_path = "/tmp/check.jpg"
            img.save(temp_path)
            
            # Check
            with open(temp_path, 'rb') as f:
                files = {'file': f}
                result = requests.post(
                    f"{self.api_url}/check",
                    files=files
                )
            
            return result.json()
        except Exception as e:
            print(f"Error checking {image_url}: {e}")
            return None
    
    async def scan_website(self, urls):
        """Scan multiple URLs for unauthorized use"""
        results = []
        for url in urls:
            match = await self.check_url(url)
            if match and match['has_unauthorized_use']:
                results.append({
                    'url': url,
                    'match': match['best_match']['similarity_score']
                })
        return results

# Usage
async def main():
    scraper = WebScraper()
    urls = [
        "https://example.com/image1.jpg",
        "https://example.com/image2.jpg",
    ]
    
    unauthorized = await scraper.scan_website(urls)
    for item in unauthorized:
        print(f"⚠️ Match: {item['url']} ({item['match']:.1%})")

# asyncio.run(main())
```

---

## 2. Social Media Bot - Monitor Platform

```python
import instagrapi  # Instagram API
import twitter  # Twitter API
from pathlib import Path
import requests
import json
from datetime import datetime

class SocialMediaMonitor:
    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url
        self.instagram = instagrapi.Client()
        self.twitter = twitter.Api(...)
        self.alerts_log = []
    
    def upload_reference_assets(self, directory):
        """Register all reference images"""
        for file in Path(directory).glob('*.jpg'):
            with open(file, 'rb') as f:
                files = {'file': f}
                resp = requests.post(
                    f"{self.api_url}/upload",
                    files=files
                )
                print(f"Registered: {file.name}")
    
    def check_instagram_posts(self, username):
        """Monitor Instagram account for reposts"""
        user = self.instagram.user_info_by_username(username)
        posts = self.instagram.user_medias(user.pk, amount=50)
        
        for post in posts:
            image_url = post.media_type == 1 and post.image_versions2.candidates[0].url
            
            if image_url:
                result = self._check_url(image_url)
                
                if result['has_unauthorized_use']:
                    alert = {
                        'platform': 'Instagram',
                        'username': username,
                        'post_id': post.id,
                        'similarity': result['best_match']['similarity_score'],
                        'timestamp': datetime.utcnow()
                    }
                    self.alerts_log.append(alert)
                    self._send_alert(alert)
    
    def check_twitter_images(self, hashtag):
        """Monitor Twitter hashtag"""
        tweets = self.twitter.GetSearch(term=f"#{hashtag}", result_type="recent")
        
        for tweet in tweets:
            if tweet.media:
                for media in tweet.media:
                    result = self._check_url(media.media_url)
                    
                    if result['has_unauthorized_use']:
                        print(f"⚠️ ALERT: @{tweet.user.screen_name}")
    
    def _check_url(self, url):
        """Helper to check URL"""
        import io
        response = requests.get(url)
        with open('/tmp/check.jpg', 'wb') as f:
            f.write(response.content)
        
        with open('/tmp/check.jpg', 'rb') as f:
            files = {'file': f}
            result = requests.post(f"{self.api_url}/check", files=files)
        return result.json()
    
    def _send_alert(self, alert):
        """Send alert to admin"""
        # Send email, webhook, Slack, etc.
        print(f"🚨 UNAUTHORIZED USE: {alert}")

# Usage
monitor = SocialMediaMonitor()
monitor.upload_reference_assets("./protected_assets")
monitor.check_instagram_posts("brand_account")
monitor.check_twitter_images("brand_hashtag")
```

---

## 3. File Upload Service - Protect User-Generated Content

```python
from fastapi import FastAPI, UploadFile, File
from pathlib import Path
import requests

app = FastAPI()

PROTECTION_API = "http://localhost:8000"

@app.post("/upload")
async def upload_content(file: UploadFile = File(...)):
    """
    User uploads content:
    1. Check for matches (unauthorized use)
    2. Register if unique
    3. Return certificate
    """
    
    # Save temporarily
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, 'wb') as f:
        f.write(await file.read())
    
    # Check for matches
    with open(temp_path, 'rb') as f:
        check_response = requests.post(
            f"{PROTECTION_API}/check",
            files={'file': f}
        )
    
    check_result = check_response.json()
    
    if check_result['has_unauthorized_use']:
        # Reject upload
        return {
            'status': 'rejected',
            'reason': 'possible_repost',
            'similarity': check_result['best_match']['similarity_score']
        }
    
    # Register original
    with open(temp_path, 'rb') as f:
        upload_response = requests.post(
            f"{PROTECTION_API}/upload",
            files={'file': f}
        )
    
    upload_result = upload_response.json()
    asset_id = upload_result['asset_id']
    
    return {
        'status': 'accepted',
        'asset_id': asset_id,
        'certificate': {
            'created': upload_result['timestamp'],
            'file': file.filename,
            'verified': True
        }
    }
```

---

## 4. Batch Processing Pipeline

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import json
from pathlib import Path

class BatchProcessor:
    def __init__(self, api_url="http://localhost:8000", workers=4):
        self.api_url = api_url
        self.workers = workers
        self.results = []
    
    def process_directory(self, directory, action='check'):
        """Process all images in directory"""
        files = list(Path(directory).glob('*.jpg')) + \
                list(Path(directory).glob('*.png'))
        
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {
                executor.submit(self._process_file, f, action): f 
                for f in files
            }
            
            for future in as_completed(futures):
                file = futures[future]
                try:
                    result = future.result()
                    self.results.append(result)
                    print(f"✓ {file.name}")
                except Exception as e:
                    print(f"✗ {file.name}: {e}")
    
    def _process_file(self, file_path, action='check'):
        """Process single file"""
        with open(file_path, 'rb') as f:
            files = {'file': f}
            endpoint = f"{self.api_url}/{action}"
            response = requests.post(endpoint, files=files)
        
        return {
            'file': file_path.name,
            'result': response.json()
        }
    
    def save_report(self, output_file='report.json'):
        """Save results to JSON"""
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        # Print summary
        total = len(self.results)
        unauthorized = sum(
            1 for r in self.results 
            if r['result'].get('has_unauthorized_use')
        )
        
        print(f"\n📊 Summary:")
        print(f"  Total: {total}")
        print(f"  Unauthorized: {unauthorized}")
        print(f"  Match Rate: {unauthorized/total*100:.1f}%")

# Usage
processor = BatchProcessor(workers=8)
processor.process_directory('./uploads', action='check')
processor.save_report('batch_results.json')
```

---

## 5. Dashboard Integration - Real-Time Alerts

```javascript
// React Dashboard Component
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const ProtectionDashboard = () => {
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    // Fetch stats every 30s
    const interval = setInterval(async () => {
      const response = await axios.get('http://localhost:8000/results');
      setStats(response.data);
      
      // Filter new alerts
      const critical = response.data.alerts.filter(
        a => a.severity === 'critical'
      );
      setAlerts(critical);
    }, 30000);
    
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="dashboard">
      <div className="stats">
        <h2>Unauthorized Uses: {stats?.unauthorized_count}</h2>
        <h2>Critical Alerts: {stats?.critical_alerts}</h2>
      </div>
      
      <div className="alerts">
        {alerts.map(alert => (
          <div key={alert.alert_id} className="alert critical">
            <h3>🚨 {alert.message}</h3>
            <p>Similarity: {(alert.similarity_score * 100).toFixed(1)}%</p>
            <button onClick={() => reviewAlert(alert)}>
              Review
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProtectionDashboard;
```

---

## 6. CLI Tool

```python
#!/usr/bin/env python3
"""
Command-line tool for Digital Asset Protection System
"""

import click
import requests
import json
import sys
from pathlib import Path
from tabulate import tabulate

API_URL = "http://localhost:8000"

@click.group()
def cli():
    """Digital Asset Protection CLI"""
    pass

@cli.command()
@click.argument('filepath', type=click.Path(exists=True))
def upload(filepath):
    """Register asset"""
    with open(filepath, 'rb') as f:
        files = {'file': f}
        response = requests.post(f"{API_URL}/upload", files=files)
    
    result = response.json()
    click.echo(f"✓ Asset ID: {result['asset_id']}")
    click.echo(f"  File: {result['filename']}")

@cli.command()
@click.argument('filepath', type=click.Path(exists=True))
def check(filepath):
    """Check for matches"""
    with open(filepath, 'rb') as f:
        files = {'file': f}
        response = requests.post(f"{API_URL}/check", files=files)
    
    result = response.json()
    
    if result['has_unauthorized_use']:
        click.secho("⚠️  UNAUTHORIZED USE DETECTED", fg='red')
        match = result['best_match']
        click.echo(f"  Matched: {match['matched_filename']}")
        click.echo(f"  Similarity: {match['similarity_score']:.1%}")
    else:
        click.secho("✓ No matches found", fg='green')

@cli.command()
def stats():
    """Show statistics"""
    response = requests.get(f"{API_URL}/results")
    data = response.json()
    
    table = [
        ['Total Matches', data['total_matches']],
        ['Unauthorized', data['unauthorized_count']],
        ['Alerts', data['total_alerts']],
        ['Critical', data['critical_alerts']],
    ]
    
    click.echo(tabulate(table, headers=['Metric', 'Count']))

@cli.command()
@click.argument('directory', type=click.Path(exists=True))
def scan_dir(directory):
    """Scan directory"""
    files = list(Path(directory).glob('*.jpg'))
    click.echo(f"Scanning {len(files)} files...")
    
    unauthorized = []
    for file in files:
        with open(file, 'rb') as f:
            files_dict = {'file': f}
            response = requests.post(f"{API_URL}/check", files=files_dict)
            result = response.json()
        
        if result['has_unauthorized_use']:
            unauthorized.append(file.name)
    
    click.secho(f"Found {len(unauthorized)} unauthorized uses", fg='red')

if __name__ == '__main__':
    cli()
```

**Usage:**
```bash
# Register asset
./cli.py upload original.jpg

# Check file
./cli.py check suspicious.jpg

# View stats
./cli.py stats

# Scan directory
./cli.py scan-dir ./uploads
```

---

## 7. Webhook Alert System

```python
from fastapi import FastAPI
import requests
import json
from datetime import datetime

app = FastAPI()

WEBHOOK_SECRET = "your-secret-key"
ALERT_WEBHOOKS = [
    "https://your-domain.com/alerts/webhook",
    "https://slack.com/hooks/xxx",
]

def send_webhook_alert(alert):
    """Send alert to external services"""
    payload = {
        'timestamp': datetime.utcnow().isoformat(),
        'alert_id': alert['alert_id'],
        'severity': alert['severity'],
        'message': alert['message'],
        'similarity': alert['similarity_score'],
        'matched_asset': alert['matched_asset_id']
    }
    
    for webhook in ALERT_WEBHOOKS:
        try:
            requests.post(
                webhook,
                json=payload,
                headers={'X-Webhook-Secret': WEBHOOK_SECRET},
                timeout=5
            )
        except Exception as e:
            print(f"Webhook failed: {e}")

# Hook into detection system
@app.post("/check")
async def check_with_webhooks(file):
    # ... existing check logic ...
    
    result = detection_result
    
    # Send webhook alerts
    for alert in result['alerts']:
        send_webhook_alert(alert)
    
    return result
```

---

**These examples demonstrate production-ready integrations!**

For more examples, see: [https://github.com/your-org/asset-protection/examples](docs/examples)
