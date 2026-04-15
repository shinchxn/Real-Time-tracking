"""
Test Suite: Evaluate system robustness against transformations
Tests: Cropping, Compression, Filters, Rotation, etc.
"""
import os
import sys
import cv2
import numpy as np
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance
import time
import json
from typing import Dict, List, Tuple
import logging

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from content_dna import ContentDNAGenerator
from vector_db import VectorDatabase
from matching_engine import MatchingEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImageTransformationTester:
    """Test robustness of system against image transformations"""
    
    def __init__(self, original_image_path: str):
        """
        Initialize tester
        
        Args:
            original_image_path: Path to original test image
        """
        self.original_image = Image.open(original_image_path)
        self.original_path = original_image_path
        self.test_results = []
        
        # Initialize system components
        self.dna_gen = ContentDNAGenerator()
        self.vector_db = VectorDatabase(embedding_dim=512)
        self.matching_engine = MatchingEngine(self.vector_db)
        
        # Extract original DNA
        logger.info("Extracting original image DNA...")
        self.original_dna = self.dna_gen.extract_content_dna(original_image_path)
        self.original_embedding = self.original_dna['embedding']
        
        # Add to database
        self.vector_db.add_embedding(
            embedding=self.original_embedding,
            asset_id="original",
            filename="original.jpg",
            phash=self.original_dna['phash'],
            metadata={'type': 'original'}
        )
    
    def apply_jpeg_compression(self, quality: int = 50) -> Image.Image:
        """Apply JPEG compression"""
        os.makedirs("tests/temp", exist_ok=True)
        buffer = os.path.join("tests/temp", "test_compressed.jpg")
        self.original_image.save(buffer, "JPEG", quality=quality)
        return Image.open(buffer)
    
    def apply_cropping(self, crop_percent: float = 0.1) -> Image.Image:
        """Crop image (remove edges)"""
        width, height = self.original_image.size
        left = int(width * crop_percent)
        top = int(height * crop_percent)
        right = int(width * (1 - crop_percent))
        bottom = int(height * (1 - crop_percent))
        return self.original_image.crop((left, top, right, bottom))
    
    def apply_rotation(self, angle: int = 15) -> Image.Image:
        """Rotate image"""
        return self.original_image.rotate(angle, expand=False, fillcolor='white')
    
    def apply_blur(self, radius: int = 5) -> Image.Image:
        """Apply Gaussian blur"""
        return self.original_image.filter(ImageFilter.GaussianBlur(radius=radius))
    
    def apply_brightness_change(self, factor: float = 0.8) -> Image.Image:
        """Modify brightness"""
        enhancer = ImageEnhance.Brightness(self.original_image)
        return enhancer.enhance(factor)
    
    def apply_contrast_change(self, factor: float = 1.5) -> Image.Image:
        """Modify contrast"""
        enhancer = ImageEnhance.Contrast(self.original_image)
        return enhancer.enhance(factor)
    
    def apply_saturation_change(self, factor: float = 0.5) -> Image.Image:
        """Modify saturation"""
        enhancer = ImageEnhance.Color(self.original_image)
        return enhancer.enhance(factor)
    
    def apply_resize(self, scale: float = 0.8) -> Image.Image:
        """Resize image"""
        width, height = self.original_image.size
        new_size = (int(width * scale), int(height * scale))
        return self.original_image.resize(new_size, Image.Resampling.LANCZOS)
    
    def apply_watermark(self, text: str = "WATERMARK") -> Image.Image:
        """Add text watermark"""
        from PIL import ImageDraw
        img = self.original_image.copy()
        draw = ImageDraw.Draw(img)
        width, height = img.size
        draw.text((width // 2, height // 2), text, fill='white')
        return img
    
    def test_transformation(self, name: str, transformed_image: Image.Image) -> Dict:
        """
        Test a transformed image
        
        Returns:
            dict with results
        """
        logger.info(f"Testing transformation: {name}")
        
        # Save temporarily
        os.makedirs("tests/temp", exist_ok=True)
        temp_path = os.path.join("tests/temp", f"test_{name}.jpg")
        transformed_image.save(temp_path)
        
        try:
            # Extract DNA
            transformed_dna = self.dna_gen.extract_content_dna(temp_path)
            transformed_embedding = transformed_dna['embedding']
            
            # Search for matches
            start_time = time.time()
            results = self.vector_db.search(transformed_embedding, k=5)
            search_time = time.time() - start_time
            
            # Get best match
            best_match = results[0] if results else None
            
            # Calculate similarity
            similarity = best_match['similarity_score'] if best_match else 0.0
            
            result = {
                'transformation': name,
                'similarity_score': similarity,
                'search_time_ms': search_time * 1000,
                'matched_asset': best_match['asset_id'] if best_match else None,
                'passed': similarity > 0.75,  # Threshold
                'phash_match': transformed_dna['phash'] == self.original_dna['phash']
            }
            
            logger.info(f"  ✓ Similarity: {similarity:.3f}, pHash match: {result['phash_match']}")
            self.test_results.append(result)
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        return result
    
    def run_all_tests(self) -> List[Dict]:
        """Run all transformation tests"""
        logger.info("=" * 60)
        logger.info("STARTING TRANSFORMATION ROBUSTNESS TESTS")
        logger.info("=" * 60)
        
        transformations = {
            'original': Image.open(self.original_path),
            'jpeg_compression_50': self.apply_jpeg_compression(quality=50),
            'jpeg_compression_30': self.apply_jpeg_compression(quality=30),
            'crop_10%': self.apply_cropping(crop_percent=0.1),
            'crop_20%': self.apply_cropping(crop_percent=0.2),
            'rotation_15°': self.apply_rotation(angle=15),
            'rotation_45°': self.apply_rotation(angle=45),
            'blur_light': self.apply_blur(radius=3),
            'blur_heavy': self.apply_blur(radius=10),
            'brightness_-20%': self.apply_brightness_change(factor=0.8),
            'brightness_+30%': self.apply_brightness_change(factor=1.3),
            'contrast_-50%': self.apply_contrast_change(factor=0.5),
            'contrast_+100%': self.apply_contrast_change(factor=2.0),
            'saturation_-50%': self.apply_saturation_change(factor=0.5),
            'saturation_+50%': self.apply_saturation_change(factor=1.5),
            'resize_80%': self.apply_resize(scale=0.8),
            'resize_50%': self.apply_resize(scale=0.5),
            'watermark': self.apply_watermark()
        }
        
        for name, transformed in transformations.items():
            self.test_transformation(name, transformed)
        
        return self.test_results
    
    def generate_report(self, output_path: str = "tests/results/robustness_report.json"):
        """Generate test report"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        summary = {
            'total_tests': len(self.test_results),
            'passed': sum(1 for r in self.test_results if r['passed']),
            'failed': sum(1 for r in self.test_results if not r['passed']),
            'avg_similarity': np.mean([r['similarity_score'] for r in self.test_results]),
            'avg_search_time_ms': np.mean([r['search_time_ms'] for r in self.test_results]),
            'phash_matches': sum(1 for r in self.test_results if r['phash_match']),
            'results': self.test_results
        }
        
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info("=" * 60)
        logger.info("TEST RESULTS SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {summary['total_tests']}")
        logger.info(f"Passed: {summary['passed']}")
        logger.info(f"Failed: {summary['failed']}")
        logger.info(f"Pass Rate: {summary['passed']/summary['total_tests']*100:.1f}%")
        logger.info(f"Avg Similarity: {summary['avg_similarity']:.3f}")
        logger.info(f"Avg Search Time: {summary['avg_search_time_ms']:.2f}ms")
        logger.info(f"pHash Matches: {summary['phash_matches']}/{len(self.test_results)}")
        logger.info("=" * 60)
        
        return summary


if __name__ == "__main__":
    # Test with sample image
    sample_image = "data/samples/01_red_circle.jpg"
    
    if not os.path.exists(sample_image):
        logger.error(f"Sample image not found: {sample_image}")
        sys.exit(1)
    
    tester = ImageTransformationTester(sample_image)
    results = tester.run_all_tests()
    report = tester.generate_report()
