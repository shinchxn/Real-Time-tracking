"""
Generate sample dataset for testing
Creates diverse test images with various content
"""
import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_images(output_dir: str = "data/samples", count: int = 10):
    """
    Create diverse sample images for testing
    
    Args:
        output_dir: Directory to save images
        count: Number of sample images to create
    """
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"Creating {count} sample images...")
    
    # Image 1: Red circle
    img = Image.new('RGB', (512, 512), 'white')
    draw = ImageDraw.Draw(img)
    draw.ellipse([50, 50, 450, 450], fill='red', outline='darkred', width=5)
    img.save(os.path.join(output_dir, '01_red_circle.jpg'))
    logger.info("✓ Created: red_circle.jpg")
    
    # Image 2: Blue square
    img = Image.new('RGB', (512, 512), 'white')
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 450, 450], fill='blue', outline='darkblue', width=5)
    img.save(os.path.join(output_dir, '02_blue_square.jpg'))
    logger.info("✓ Created: blue_square.jpg")
    
    # Image 3: Green triangle
    img = Image.new('RGB', (512, 512), 'white')
    draw = ImageDraw.Draw(img)
    draw.polygon([(256, 50), (450, 450), (62, 450)], fill='green', outline='darkgreen')
    img.save(os.path.join(output_dir, '03_green_triangle.jpg'))
    logger.info("✓ Created: green_triangle.jpg")
    
    # Image 4: Gradient background
    img = Image.new('RGB', (512, 512))
    pixels = img.load()
    for i in range(512):
        for j in range(512):
            pixels[i, j] = (int(i * 255 / 512), int(j * 255 / 512), 128)
    img.save(os.path.join(output_dir, '04_gradient.jpg'))
    logger.info("✓ Created: gradient.jpg")
    
    # Image 5: Grid pattern
    img = Image.new('RGB', (512, 512), 'white')
    draw = ImageDraw.Draw(img)
    for i in range(0, 512, 32):
        draw.line([(i, 0), (i, 512)], fill='gray', width=1)
        draw.line([(0, i), (512, i)], fill='gray', width=1)
    img.save(os.path.join(output_dir, '05_grid.jpg'))
    logger.info("✓ Created: grid.jpg")
    
    # Image 6: Checkerboard
    img = Image.new('RGB', (512, 512))
    pixels = img.load()
    for i in range(512):
        for j in range(512):
            if (i // 32 + j // 32) % 2 == 0:
                pixels[i, j] = (0, 0, 0)
            else:
                pixels[i, j] = (255, 255, 255)
    img.save(os.path.join(output_dir, '06_checkerboard.jpg'))
    logger.info("✓ Created: checkerboard.jpg")
    
    # Image 7: Random noise
    img = Image.new('RGB', (512, 512))
    pixels = np.random.randint(0, 256, (512, 512, 3), dtype=np.uint8)
    img = Image.fromarray(pixels)
    img.save(os.path.join(output_dir, '07_random_noise.jpg'))
    logger.info("✓ Created: random_noise.jpg")
    
    # Image 8: Text image
    img = Image.new('RGB', (512, 512), 'white')
    draw = ImageDraw.Draw(img)
    text = "ASSET\nPROTECTION\nSYSTEM"
    bbox = draw.textbbox((0, 0), text)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (512 - text_width) / 2
    y = (512 - text_height) / 2
    draw.text((x, y), text, fill='blue')
    img.save(os.path.join(output_dir, '08_text.jpg'))
    logger.info("✓ Created: text.jpg")
    
    # Image 9: Geometric shapes mix
    img = Image.new('RGB', (512, 512), 'lightgray')
    draw = ImageDraw.Draw(img)
    draw.ellipse([20, 20, 150, 150], fill='red')
    draw.rectangle([180, 20, 310, 150], fill='green')
    draw.polygon([(340, 20), (510, 150), (340, 150)], fill='blue')
    draw.line([(20, 200), (490, 200)], fill='black', width=3)
    img.save(os.path.join(output_dir, '09_shapes_mix.jpg'))
    logger.info("✓ Created: shapes_mix.jpg")
    
    # Image 10: Colored squares grid
    img = Image.new('RGB', (512, 512))
    colors = ['red', 'green', 'blue', 'yellow', 'magenta', 'cyan', 'orange', 'purple']
    cell_size = 64
    idx = 0
    for i in range(0, 512, cell_size):
        for j in range(0, 512, cell_size):
            color = colors[idx % len(colors)]
            cell = Image.new('RGB', (cell_size, cell_size), color)
            img.paste(cell, (i, j))
            idx += 1
    img.save(os.path.join(output_dir, '10_color_grid.jpg'))
    logger.info("✓ Created: color_grid.jpg")
    
    logger.info(f"✓ Created {count} sample images in {output_dir}")


if __name__ == "__main__":
    create_sample_images()
