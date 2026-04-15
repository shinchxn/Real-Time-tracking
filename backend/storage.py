"""
Storage Module: Handle local and cloud storage (GCS)
"""
import os
import shutil
from pathlib import Path
from typing import Optional
import logging
from google.cloud import storage
from google.oauth2 import service_account
from config import settings

logger = logging.getLogger(__name__)

class StorageManager:
    """Manage file storage (Local or GCS)"""
    
    def __init__(self):
        self.storage_type = settings.STORAGE_TYPE
        self.bucket_name = settings.GCS_BUCKET
        self.client = None
        self.bucket = None
        
        if self.storage_type == "gcs":
            if not self.bucket_name:
                logger.warning("STORAGE_TYPE is GCS but GCS_BUCKET is not set. Falling back to local.")
                self.storage_type = "local"
            else:
                try:
                    self.client = storage.Client()
                    self.bucket = self.client.bucket(self.bucket_name)
                    logger.info(f"Using GCS storage: gs://{self.bucket_name}")
                except Exception as e:
                    logger.error(f"Failed to initialize GCS client: {e}. Falling back to local.")
                    self.storage_type = "local"
        
        if self.storage_type == "local":
            os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
            logger.info(f"Using local storage: {settings.UPLOAD_DIR}")

    def upload_file(self, local_path: str, destination_name: str) -> str:
        """
        Upload file to storage
        
        Args:
            local_path: Path to local file
            destination_name: Name of file in destination
            
        Returns:
            str: Path or URL to stored file
        """
        if self.storage_type == "gcs":
            try:
                blob = self.bucket.blob(destination_name)
                blob.upload_from_filename(local_path)
                logger.info(f"Uploaded to GCS: gs://{self.bucket_name}/{destination_name}")
                return f"gs://{self.bucket_name}/{destination_name}"
            except Exception as e:
                logger.error(f"GCS upload failed: {e}")
                # Fallback to local if possible, but usually we just want to know it failed
                raise
        else:
            # Local storage - file is already at settings.UPLOAD_DIR
            # Just return the path relative to workspace or absolute
            return local_path

    def download_file(self, source_name: str, local_destination: str) -> None:
        """Download file from storage"""
        if self.storage_type == "gcs":
            try:
                blob = self.bucket.blob(source_name)
                blob.download_to_filename(local_destination)
                logger.info(f"Downloaded from GCS: {source_name} -> {local_destination}")
            except Exception as e:
                logger.error(f"GCS download failed: {e}")
                raise
        else:
            # Local - just copy
            source_path = os.path.join(settings.UPLOAD_DIR, source_name)
            if os.path.exists(source_path):
                shutil.copy2(source_path, local_destination)

    def delete_file(self, file_name: str) -> None:
        """Delete file from storage"""
        if self.storage_type == "gcs":
            try:
                blob = self.bucket.blob(file_name)
                blob.delete()
                logger.info(f"Deleted from GCS: {file_name}")
            except Exception as e:
                logger.error(f"GCS delete failed: {e}")
        else:
            file_path = os.path.join(settings.UPLOAD_DIR, file_name)
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted from local: {file_path}")

storage_manager = StorageManager()
