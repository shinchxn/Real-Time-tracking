from watermark.dct_extract import extract_dct_watermark
from watermark.dwt_extract import extract_dwt_watermark
from PIL import Image

class WatermarkExtractPipeline:
    def process_item(self, item, spider):
        if item.get('local_path'):
            try:
                img = Image.open(item['local_path'])
                # Assuming owner hint from URL or metadata, or brute force (which isn't scalable).
                # We'll rely on the DWT blind extraction 
                res_dwt = extract_dwt_watermark(img)
                item['extracted_wm'] = res_dwt if res_dwt.get('valid') else None
            except Exception:
                pass
        return item
