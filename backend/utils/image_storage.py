"""
Image storage utility for detected fruit categories.
Stores images when detection counter changes - replaces folder contents with new detections.
"""

import os
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import json


# Base directory for storing detection images
DETECTION_IMAGES_DIR = Path("./detection_images")


def ensure_category_directory(category: str) -> Path:
    """
    Ensure the directory for a category exists.
    
    Args:
        category: Fruit category name (e.g., 'banana', 'apple')
    
    Returns:
        Path to the category directory
    """
    category_dir = DETECTION_IMAGES_DIR / category.lower()
    category_dir.mkdir(parents=True, exist_ok=True)
    return category_dir


def replace_category_images(cropped_images: List[tuple], category: str) -> List[str]:
    """
    Replace all images in a category folder with new images.
    Used when detection counter changes - clears old images and stores new ones.
    Preserves thumbnail.* files so they don't get deleted.
    
    Args:
        cropped_images: List of tuples (image_array, metadata_dict) for each detection
        category: Fruit category name (e.g., 'banana', 'apple')
    
    Returns:
        List of relative paths to saved images
    """
    try:
        category_dir = ensure_category_directory(category)
        
        # Delete all existing images in the folder EXCEPT thumbnail files and processed images
        for file_path in category_dir.iterdir():
            if file_path.is_file() and not file_path.name.startswith('thumbnail.') and not file_path.name.startswith('processed_'):
                file_path.unlink()
        
        # Save new images
        saved_paths = []
        for idx, (cropped_image, metadata) in enumerate(cropped_images):
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{timestamp}_{idx}.jpg"
            image_path = category_dir / filename
            
            # Save image
            cv2.imwrite(str(image_path), cropped_image)
            
            # Save metadata if provided
            if metadata:
                metadata_path = category_dir / f"{timestamp}_{idx}.json"
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2, default=str)
            
            saved_paths.append(f"detection_images/{category.lower()}/{filename}")
        
        return saved_paths
    
    except Exception as e:
        print(f"Error replacing category images for {category}: {e}")
        return []


def save_detection_image(cropped_image: np.ndarray, category: str, metadata: Optional[dict] = None) -> Optional[str]:
    """
    DEPRECATED: Use replace_category_images instead.
    This function is kept for backward compatibility but does nothing.
    """
    return None


def keep_latest_images(category_dir: Path, max_images: int = 3):
    """
    Keep only the latest N images in a category directory.
    Deletes older images and their metadata files.
    
    Args:
        category_dir: Directory containing images
        max_images: Maximum number of images to keep
    """
    try:
        # Get all image files
        image_files = list(category_dir.glob("*.jpg"))
        
        if len(image_files) <= max_images:
            return
        
        # Sort by modification time (newest first)
        image_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        # Delete older images
        for old_image in image_files[max_images:]:
            old_image.unlink()
            
            # Also delete corresponding metadata file if it exists
            metadata_file = old_image.with_suffix('.json')
            if metadata_file.exists():
                metadata_file.unlink()
    
    except Exception as e:
        print(f"Error cleaning up old images in {category_dir}: {e}")


def get_category_images(category: str) -> List[dict]:
    """
    Get all images for a category.
    
    Args:
        category: Fruit category name
    
    Returns:
        List of image info dictionaries with 'path', 'timestamp', and 'metadata'
    """
    try:
        category_dir = ensure_category_directory(category)
        
        images = []
        image_files = list(category_dir.glob("*.jpg"))
        
        # Sort by modification time (newest first)
        image_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        for image_path in image_files:
            # Get timestamp from filename or file modification time
            timestamp_str = image_path.stem.split('_')[0:2]  # Extract date and time parts
            timestamp = datetime.fromtimestamp(image_path.stat().st_mtime)
            
            # Load metadata if available
            # For processed images, the JSON will also have processed_ prefix
            metadata = None
            metadata_path = image_path.with_suffix('.json')
            if metadata_path.exists():
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                except:
                    pass
            
            images.append({
                'path': f"detection_images/{category.lower()}/{image_path.name}",
                'filename': image_path.name,
                'timestamp': timestamp.isoformat(),
                'metadata': metadata
            })
        
        return images
    
    except Exception as e:
        print(f"Error getting images for {category}: {e}")
        return []


def get_all_categories() -> List[str]:
    """
    Get list of all categories that have images.
    
    Returns:
        List of category names
    """
    try:
        if not DETECTION_IMAGES_DIR.exists():
            return []
        
        categories = []
        for item in DETECTION_IMAGES_DIR.iterdir():
            if item.is_dir():
                categories.append(item.name)
        
        return sorted(categories)
    
    except Exception as e:
        print(f"Error getting categories: {e}")
        return []


def delete_category_images(category: str) -> bool:
    """
    Delete all images for a category.
    Preserves thumbnail.* files so they don't get deleted.
    
    Args:
        category: Fruit category name
    
    Returns:
        True if successful, False otherwise
    """
    try:
        category_dir = ensure_category_directory(category)
        
        # Delete all files in the directory EXCEPT thumbnail files and processed images
        for file_path in category_dir.iterdir():
            if file_path.is_file() and not file_path.name.startswith('thumbnail.') and not file_path.name.startswith('processed_'):
                file_path.unlink()
        
        # Only remove the directory if it's empty (no thumbnail files)
        try:
            category_dir.rmdir()
        except OSError:
            # Directory not empty (has thumbnail files), that's fine
            pass
        
        return True
    
    except Exception as e:
        print(f"Error deleting images for {category}: {e}")
        return False


def save_thumbnail(cropped_image: np.ndarray, category: str) -> Optional[str]:
    """
    Save a thumbnail image for a category. Thumbnail files are preserved
    when replace_category_images or delete_category_images are called.
    
    Args:
        cropped_image: Image array to save as thumbnail
        category: Fruit category name (e.g., 'banana', 'apple')
    
    Returns:
        Relative path to saved thumbnail, or None if error
    """
    try:
        category_dir = ensure_category_directory(category)
        
        # Determine file extension based on image format
        # Use .jpg as default
        thumbnail_filename = "thumbnail.jpg"
        thumbnail_path = category_dir / thumbnail_filename
        
        # Save thumbnail
        cv2.imwrite(str(thumbnail_path), cropped_image)
        
        relative_path = f"detection_images/{category.lower()}/{thumbnail_filename}"
        return relative_path
    
    except Exception as e:
        print(f"Error saving thumbnail for {category}: {e}")
        return None


def mark_image_as_processed(image_path: Path) -> Optional[str]:
    """
    Mark an image and its metadata JSON as processed by renaming them with a "processed_" prefix.
    Processed images are preserved when replace_category_images or delete_category_images are called.
    
    Args:
        image_path: Path to the image file
    
    Returns:
        New relative path to the renamed image, or None if error
    """
    try:
        if not image_path.exists():
            return None
        
        # Skip if already processed
        if image_path.name.startswith('processed_') or image_path.name.startswith('thumbnail.'):
            return f"detection_images/{image_path.parent.name}/{image_path.name}"
        
        # Rename image file
        new_image_name = f"processed_{image_path.name}"
        new_image_path = image_path.parent / new_image_name
        image_path.rename(new_image_path)
        
        # Rename corresponding JSON metadata file if it exists
        metadata_path = image_path.with_suffix('.json')
        if metadata_path.exists():
            new_metadata_name = f"processed_{metadata_path.name}"
            new_metadata_path = metadata_path.parent / new_metadata_name
            metadata_path.rename(new_metadata_path)
        
        relative_path = f"detection_images/{image_path.parent.name}/{new_image_name}"
        return relative_path
    
    except Exception as e:
        print(f"Error marking image as processed {image_path}: {e}")
        return None

