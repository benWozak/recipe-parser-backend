from typing import Dict, Any, Optional, List
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from .media_utils import media_utils


class StorageUtils:
    """Utility class for managing media file storage and metadata"""
    
    def __init__(self, base_dir: str = "media"):
        """Initialize StorageUtils"""
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        
        # Create metadata directory
        self.metadata_dir = self.base_dir / "metadata"
        self.metadata_dir.mkdir(exist_ok=True)
    
    def generate_media_id(self, url: str) -> str:
        """Generate unique media ID from URL"""
        return hashlib.md5(url.encode()).hexdigest()[:16]
    
    async def store_media_from_url(self, url: str, recipe_id: Optional[str] = None) -> Dict[str, Any]:
        """Store media from URL with thumbnails and metadata"""
        try:
            # Process the image
            result = await media_utils.process_image_from_url(url, create_thumbnails=True)
            
            if not result["success"]:
                return result
            
            # Generate media ID
            media_id = self.generate_media_id(url)
            
            # Save original image (optimized)
            original_data = await media_utils.download_image(url)
            if not original_data:
                return {"success": False, "error": "Failed to download original image"}
            
            # Optimize the original image
            optimized_data = media_utils.optimize_image(original_data)
            
            # Save optimized original
            original_filename = f"{media_id}_original.jpg"
            original_path = media_utils.save_image_data(optimized_data, original_filename, "images")
            
            # Save thumbnails
            thumbnail_info = {}
            if "thumbnails" in result:
                for size_name, thumb_data in result["thumbnails"].items():
                    if thumb_data and thumb_data["data"]:
                        thumb_filename = f"{media_id}_{size_name}.jpg"
                        thumb_path = media_utils.save_image_data(
                            thumb_data["data"], 
                            thumb_filename, 
                            "thumbnails"
                        )
                        
                        if thumb_path:
                            thumbnail_info[size_name] = {
                                "filename": thumb_filename,
                                "path": thumb_path,
                                "url": media_utils.get_image_url(thumb_filename, "thumbnails"),
                                "size": thumb_data["size"]
                            }
            
            # Create metadata
            metadata = {
                "media_id": media_id,
                "original_url": url,
                "recipe_id": recipe_id,
                "created_at": datetime.utcnow().isoformat(),
                "original": {
                    "filename": original_filename,
                    "path": original_path,
                    "url": media_utils.get_image_url(original_filename, "images"),
                    "metadata": result["metadata"]
                },
                "thumbnails": thumbnail_info
            }
            
            # Save metadata
            metadata_file = self.metadata_dir / f"{media_id}.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return {
                "success": True,
                "media_id": media_id,
                "metadata": metadata
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_media_metadata(self, media_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for stored media"""
        try:
            metadata_file = self.metadata_dir / f"{media_id}.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            print(f"Failed to load metadata for {media_id}: {e}")
            return None
    
    def get_thumbnail_url(self, media_id: str, size: str = "medium") -> Optional[str]:
        """Get thumbnail URL for media"""
        metadata = self.get_media_metadata(media_id)
        if metadata and "thumbnails" in metadata and size in metadata["thumbnails"]:
            return metadata["thumbnails"][size]["url"]
        return None
    
    def get_original_url(self, media_id: str) -> Optional[str]:
        """Get original image URL for media"""
        metadata = self.get_media_metadata(media_id)
        if metadata and "original" in metadata:
            return metadata["original"]["url"]
        return None
    
    def delete_media(self, media_id: str) -> bool:
        """Delete media files and metadata"""
        try:
            metadata = self.get_media_metadata(media_id)
            if not metadata:
                return False
            
            # Delete original file
            if "original" in metadata and "path" in metadata["original"]:
                original_path = Path(metadata["original"]["path"])
                if original_path.exists():
                    original_path.unlink()
            
            # Delete thumbnail files
            if "thumbnails" in metadata:
                for thumb_info in metadata["thumbnails"].values():
                    if "path" in thumb_info:
                        thumb_path = Path(thumb_info["path"])
                        if thumb_path.exists():
                            thumb_path.unlink()
            
            # Delete metadata file
            metadata_file = self.metadata_dir / f"{media_id}.json"
            if metadata_file.exists():
                metadata_file.unlink()
            
            return True
            
        except Exception as e:
            print(f"Failed to delete media {media_id}: {e}")
            return False
    
    def list_media_by_recipe(self, recipe_id: str) -> List[Dict[str, Any]]:
        """List all media for a recipe"""
        media_list = []
        
        try:
            for metadata_file in self.metadata_dir.glob("*.json"):
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    if metadata.get("recipe_id") == recipe_id:
                        media_list.append(metadata)
        except Exception as e:
            print(f"Failed to list media for recipe {recipe_id}: {e}")
        
        return media_list
    
    def cleanup_orphaned_media(self, recipe_ids: List[str]) -> int:
        """Clean up media files that don't belong to any existing recipe"""
        deleted_count = 0
        
        try:
            for metadata_file in self.metadata_dir.glob("*.json"):
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    recipe_id = metadata.get("recipe_id")
                    
                    # If media has a recipe_id but recipe doesn't exist, delete it
                    if recipe_id and recipe_id not in recipe_ids:
                        if self.delete_media(metadata["media_id"]):
                            deleted_count += 1
                            
        except Exception as e:
            print(f"Failed to cleanup orphaned media: {e}")
        
        return deleted_count
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            stats = {
                "total_media": 0,
                "total_size": 0,
                "by_type": {"images": 0, "thumbnails": 0},
                "by_size": {}
            }
            
            # Count metadata files
            metadata_files = list(self.metadata_dir.glob("*.json"))
            stats["total_media"] = len(metadata_files)
            
            # Calculate storage usage
            for root, dirs, files in os.walk(self.base_dir):
                for file in files:
                    file_path = Path(root) / file
                    file_size = file_path.stat().st_size
                    stats["total_size"] += file_size
                    
                    # Categorize by directory
                    if "images" in root:
                        stats["by_type"]["images"] += file_size
                    elif "thumbnails" in root:
                        stats["by_type"]["thumbnails"] += file_size
            
            # Get thumbnail size breakdown
            for size_name in media_utils.THUMBNAIL_SIZES:
                size_total = 0
                for metadata_file in metadata_files:
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                            if "thumbnails" in metadata and size_name in metadata["thumbnails"]:
                                thumb_path = Path(metadata["thumbnails"][size_name]["path"])
                                if thumb_path.exists():
                                    size_total += thumb_path.stat().st_size
                    except:
                        continue
                stats["by_size"][size_name] = size_total
            
            return stats
            
        except Exception as e:
            print(f"Failed to get storage stats: {e}")
            return {"error": str(e)}


# Global instance
storage_utils = StorageUtils()