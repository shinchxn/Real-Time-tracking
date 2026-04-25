import logging
class AlertPipeline:
    def process_item(self, item, spider):
        sev = item.get('severity')
        if sev in ['HIGH', 'CRITICAL']:
            # Push Celery task ideally
            logging.info(f"ALERT: {sev} violation on {item.get('source_url')}")
        return item
