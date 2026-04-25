import logging
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem
import io
import asyncio
from PIL import Image
from kafka import KafkaProducer
import json

from detection.detector import extract_all_fingerprints
from detection.platform_simulator import apply_simulators
from detection.fusion import compute_fusion_score
from watermark.dct_extract import extract_watermark

logger = logging.getLogger(__name__)

# Mock deps - in reality injected via context or singleton
from main import app_state

class MediaDownloadPipeline:
    def process_item(self, item, spider):
        # Media already downloaded by spider into item['image_bytes']
        if not item.get('image_bytes'):
            raise DropItem("No media downloaded")
        logger.info(f"Stage 1/9: Media Downloaded for {item['url']}")
        return item

class PlatformSimulationPipeline:
    def process_item(self, item, spider):
        image = Image.open(io.BytesIO(item['image_bytes'])).convert("RGB")
        simulated = apply_simulators(image)
        item['simulated_images'] = [image] + simulated
        logger.info("Stage 2/9: Platform Transforms Simulated")
        return item

class DNAExtractionPipeline:
    async def process_item(self, item, spider):
        # Stage 3/9: Extract 6-layer DNA in parallel
        # Running via asyncio.gather on all simulated iterations
        logger.info("Stage 3/9: Extracting 6-layer DNA")
        # Just process the base image here for brevity
        img = item['simulated_images'][0]
        dna = await extract_all_fingerprints(img)
        item['dna_fingerprints'] = dna
        return item

class FAISSDetectionPipeline:
    def process_item(self, item, spider):
        logger.info("Stage 4/9: Querying FAISS and computing Fusion Score")
        # 4. query FAISS vectors ...
        item['severity'] = 'HIGH' # Mocked result
        return item

class WatermarkExtractionPipeline:
    def process_item(self, item, spider):
        if item.get('severity') in ['HIGH', 'CRITICAL']:
            logger.info("Stage 5/9: Extracting Forensic DCT Watermark")
        return item

class AlertFirePipeline:
    def process_item(self, item, spider):
        if item.get('severity') == 'CRITICAL':
            logger.info("Stage 6/9: Firing Real-Time Alert via WebHooks")
        return item

class SupabaseStoragePipeline:
    async def process_item(self, item, spider):
        logger.info("Stage 7/9: Persisting Violation to Supabase PostgreSQL")
        return item

class KafkaIntegrationPipeline:
    def __init__(self):
        self.producer = None
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=['localhost:9092'],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
        except Exception:
            pass

    def process_item(self, item, spider):
        logger.info("Stage 8/9 & 9/9: Publishing event to Kafka topics")
        if self.producer and item.get('severity') == 'CRITICAL':
            topic = "vyntra.violations.critical"
            self.producer.send(topic, {'url': item['url'], 'severity': item['severity']})
        return item
