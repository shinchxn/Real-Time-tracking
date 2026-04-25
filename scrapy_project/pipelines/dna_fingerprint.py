import asyncio
from detection.pipeline import extract_6_layer_dna
from PIL import Image

class DNAFingerPrintPipeline:
    def process_item(self, item, spider):
        if item.get('cache_hit'):
            return item
        if item.get('local_path'):
            try:
                img = Image.open(item['local_path'])
                # Run async task linearly for pipeline (or use async syntax if native)
                loop = asyncio.get_event_loop()
                dna = loop.run_until_complete(extract_6_layer_dna(img))
                item['dna'] = dna
            except Exception:
                pass
        return item
