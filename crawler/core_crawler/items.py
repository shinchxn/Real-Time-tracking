import scrapy

class IngestedAssetItem(scrapy.Item):
    url = scrapy.Field()
    source_platform = scrapy.Field()
    image_bytes = scrapy.Field()
    owner_id = scrapy.Field()  # For Federated Org tracking
    timestamp = scrapy.Field()
    
    # 9-stage pipeline mutated fields
    simulated_images = scrapy.Field()
    dna_fingerprints = scrapy.Field()
    faiss_matches = scrapy.Field()
    best_match = scrapy.Field()
    watermark_valid = scrapy.Field()
    severity = scrapy.Field()
    alert_triggered = scrapy.Field()
    db_id = scrapy.Field()
