"""
Instagram Sports Spider — Content DNA Apex v7.0
Uses instagrapi for authenticated hashtag searches.
Emits MediaItem for each post found.
"""
import scrapy
from instagrapi import Client
import os
import json
import logging
from cryptography.fernet import Fernet
from typing import List

from storage.db_client import get_session, save_session

logger = logging.getLogger(__name__)

class InstagramSportsSpider(scrapy.Spider):
    name = 'instagram_sports'

    def __init__(self, hashtags: str = None, *args, **kwargs):
        super(InstagramSportsSpider, self).__init__(*args, **kwargs)
        self.hashtags = hashtags.split(',') if hashtags else ["sportshighlights"]
        self.cl = Client()
        
        # Fernet key for session encryption
        fernet_key = os.getenv("FERNET_KEY")
        if not fernet_key:
            # Generate a temporary one for dev
            fernet_key = Fernet.generate_key().decode()
            logger.warning(f"FERNET_KEY not set. Using temporary key: {fernet_key}")
        self.fernet = Fernet(fernet_key.encode())

    def start_requests(self):
        # 1. Login/Load Session
        self._authenticate()
        
        # 2. Iterate Hashtags
        for tag in self.hashtags:
            yield scrapy.Request(
                f"https://www.instagram.com/explore/tags/{tag}/",
                callback=self.parse_hashtag,
                cb_kwargs={'tag': tag},
                dont_filter=True
            )

    def _authenticate(self):
        username = os.getenv("INSTAGRAM_USERNAME")
        password = os.getenv("INSTAGRAM_PASSWORD")
        
        # Try to load session from DB
        import asyncio
        loop = asyncio.get_event_loop()
        encrypted_session = loop.run_until_complete(get_session(f"ig_{username}"))
        
        if encrypted_session:
            try:
                session_data = self.fernet.decrypt(encrypted_session.encode()).decode()
                self.cl.set_settings(json.loads(session_data))
                if self.cl.get_settings():
                    logger.info("Instagram session loaded from DB.")
                    return
            except Exception as e:
                logger.warning(f"Failed to load Instagram session: {e}")

        # Fallback to fresh login
        self.cl.login(username, password)
        settings = self.cl.get_settings()
        encrypted = self.fernet.encrypt(json.dumps(settings).encode()).decode()
        loop.run_until_complete(save_session(f"ig_{username}", encrypted))
        logger.info("Instagram fresh login successful. Session saved to DB.")

    def parse_hashtag(self, response, tag):
        # Use instagrapi to get recent media
        medias = self.cl.hashtag_medias_recent(tag, amount=20)
        
        for media in medias:
            item = {
                'source_url': f"https://www.instagram.com/p/{media.code}/",
                'platform': 'instagram',
                'post_id': media.code,
                'author_handle': media.user.username,
                'media_url': media.thumbnail_url or media.video_url, # thumbnail for images, video for videos
                'media_type': 'video' if media.media_type == 2 else 'image',
                'detected_at': media.taken_at.isoformat()
            }
            
            # If it's an image or video, we need to download it in the pipeline or here
            # For simplicity, we yield it and let the pipeline handle download + task
            yield item
