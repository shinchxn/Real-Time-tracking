import os
from supabase import create_client, Client
from config import settings
import logging

logger = logging.getLogger(__name__)

class SupabaseClient:
    def __init__(self):
        url = settings.SUPABASE_URL
        key = settings.SUPABASE_KEY
        if url and key:
            self.client: Client = create_client(url, key)
            self._connected = True
        else:
            self.client = None
            self._connected = False

    async def ping(self):
        """Mock ping"""
        return self._connected

    async def sync_pending(self):
        return 0

    def get_asset_dna(self, asset_id):
        # Stub local fetch if no db configured
        if not self._connected:
            return None
        try:
            # Sync API call in our mock
            res = self.client.table("assets").select("*").eq("id", asset_id).execute()
            if res.data:
                return res.data[0]
        except:
            pass
        return None
        
    async def insert_violation(self, record: dict):
        if self._connected:
            self.client.table("violations").insert(record).execute()
