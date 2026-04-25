"""
Watermark Seed Registry — Content DNA Apex v7.0
Manages 32-bit seeds used for blind watermark extraction.
"""
import secrets
from typing import Optional
from storage.db_client import get_pool # Assuming db_client has what we need or we add it

class SeedRegistry:
    @staticmethod
    def generate_seed() -> int:
        """Generate a random 32-bit unsigned integer seed."""
        return secrets.randbits(32)

    @staticmethod
    async def register_seed(asset_id: str, seed: int):
        """
        Store the seed in the database for the given asset.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE registered_assets SET watermark_seed = $1 WHERE asset_id = $2::uuid",
                seed, asset_id
            )

    @staticmethod
    async def get_seed(asset_id: str) -> Optional[int]:
        """
        Retrieve the seed for a given asset ID.
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(
                "SELECT watermark_seed FROM registered_assets WHERE asset_id = $1::uuid",
                asset_id
            )
