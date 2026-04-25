from PIL import Image
from detection.platform_profiles import simulate_instagram, simulate_tiktok, simulate_twitter

class PlatformSimPipeline:
    def process_item(self, item, spider):
        if item.get('local_path'):
            try:
                img = Image.open(item['local_path'])
                platform = item.get('platform')
                if platform == 'instagram':
                    img = simulate_instagram(img)
                elif platform == 'tiktok':
                    img = simulate_tiktok(img)
                elif platform == 'twitter':
                    img = simulate_twitter(img)
                # save back
                img.save(item['local_path'])
            except Exception:
                pass
        return item
