from typing import Optional, Tuple, Dict, Any
from PIL import Image, ImageOps
import io
import os
import hashlib
import httpx
from pathlib import Path
import tempfile
import subprocess
import logging
from fractions import Fraction
try:
    import ffmpeg
except ImportError:
    ffmpeg = None


class MediaUtils:
    """Utility class for media processing and thumbnail generation"""
    
    # Standard thumbnail sizes for recipe cards
    THUMBNAIL_SIZES = {
        "small": (150, 150),
        "medium": (300, 300),
        "large": (600, 600)
    }
    
    # Supported image formats
    SUPPORTED_FORMATS = {'JPEG', 'PNG', 'WebP', 'GIF'}
    
    # Supported video formats
    SUPPORTED_VIDEO_FORMATS = {'MP4', 'WebM', 'MOV', 'AVI', 'MKV'}
    
    def __init__(self, media_dir: str = "media"):
        """Initialize MediaUtils with media directory"""
        self.media_dir = Path(media_dir)
        self.media_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.media_dir / "thumbnails").mkdir(exist_ok=True)
        (self.media_dir / "images").mkdir(exist_ok=True)
        (self.media_dir / "videos").mkdir(exist_ok=True)
        (self.media_dir / "video_thumbnails").mkdir(exist_ok=True)
        (self.media_dir / "quarantine").mkdir(exist_ok=True)  # For suspicious files
        (self.media_dir / "temp").mkdir(exist_ok=True)  # For processing
    
    async def download_image(self, url: str) -> Optional[bytes]:
        """Download image from URL"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                return response.content
        except Exception as e:
            print(f"Failed to download image from {url}: {e}")
            return None
    
    def create_thumbnail(self, image_data: bytes, size: Tuple[int, int] = (300, 300)) -> Optional[bytes]:
        """Create thumbnail from image data"""
        try:
            # Open image from bytes
            with Image.open(io.BytesIO(image_data)) as img:
                # Convert to RGB if necessary (for formats like PNG with transparency)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Create thumbnail maintaining aspect ratio
                img.thumbnail(size, Image.Resampling.LANCZOS)
                
                # Create a square thumbnail with white background
                thumb = Image.new('RGB', size, (255, 255, 255))
                
                # Calculate position to center the image
                x = (size[0] - img.width) // 2
                y = (size[1] - img.height) // 2
                
                # Paste the resized image onto the square background
                thumb.paste(img, (x, y))
                
                # Convert back to bytes
                output = io.BytesIO()
                thumb.save(output, format='JPEG', quality=90, optimize=True)
                return output.getvalue()
                
        except Exception as e:
            print(f"Failed to create thumbnail: {e}")
            return None
    
    def create_multiple_thumbnails(self, image_data: bytes) -> Dict[str, Optional[bytes]]:
        """Create multiple thumbnail sizes from image data"""
        thumbnails = {}
        
        for size_name, size_tuple in self.THUMBNAIL_SIZES.items():
            thumbnail_data = self.create_thumbnail(image_data, size_tuple)
            thumbnails[size_name] = thumbnail_data
        
        return thumbnails
    
    def validate_image(self, image_data: bytes) -> Dict[str, Any]:
        """Validate image data and return metadata"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                return {
                    "valid": True,
                    "format": img.format,
                    "mode": img.mode,
                    "size": img.size,
                    "width": img.width,
                    "height": img.height,
                    "file_size": len(image_data)
                }
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }
    
    def generate_filename(self, url: str, prefix: str = "img") -> str:
        """Generate unique filename from URL"""
        # Create hash of URL for uniqueness
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        return f"{prefix}_{url_hash}.jpg"
    
    async def process_image_from_url(self, url: str, create_thumbnails: bool = True) -> Dict[str, Any]:
        """Download image from URL and process it"""
        # Download image
        image_data = await self.download_image(url)
        if not image_data:
            return {"success": False, "error": "Failed to download image"}
        
        # Validate image
        validation = self.validate_image(image_data)
        if not validation["valid"]:
            return {"success": False, "error": f"Invalid image: {validation['error']}"}
        
        # Generate filename
        filename = self.generate_filename(url)
        
        result = {
            "success": True,
            "filename": filename,
            "metadata": validation,
            "original_url": url
        }
        
        # Create thumbnails if requested
        if create_thumbnails:
            thumbnails = self.create_multiple_thumbnails(image_data)
            result["thumbnails"] = {}
            
            for size_name, thumbnail_data in thumbnails.items():
                if thumbnail_data:
                    thumb_filename = self.generate_filename(url, f"thumb_{size_name}")
                    result["thumbnails"][size_name] = {
                        "filename": thumb_filename,
                        "data": thumbnail_data,
                        "size": self.THUMBNAIL_SIZES[size_name]
                    }
        
        return result
    
    def save_image_data(self, image_data: bytes, filename: str, subdir: str = "images") -> str:
        """Save image data to disk and return file path"""
        try:
            file_path = self.media_dir / subdir / filename
            
            with open(file_path, 'wb') as f:
                f.write(image_data)
            
            return str(file_path)
        except Exception as e:
            print(f"Failed to save image {filename}: {e}")
            return None
    
    def get_image_url(self, filename: str, subdir: str = "images", base_url: str = "/media") -> str:
        """Generate URL for accessing saved image"""
        return f"{base_url}/{subdir}/{filename}"
    
    def cleanup_old_files(self, days_old: int = 30) -> int:
        """Clean up old media files (returns number of files deleted)"""
        import time
        
        deleted_count = 0
        cutoff_time = time.time() - (days_old * 24 * 60 * 60)
        
        for root, dirs, files in os.walk(self.media_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    if os.path.getmtime(file_path) < cutoff_time:
                        os.remove(file_path)
                        deleted_count += 1
                except Exception as e:
                    print(f"Failed to delete {file_path}: {e}")
        
        return deleted_count
    
    def secure_image_process(self, image_data: bytes, validation_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Securely process validated image data with sandboxing
        
        Args:
            image_data: Validated image bytes
            validation_metadata: Security validation metadata
            
        Returns:
            Dict with processed image data and metadata
        """
        try:
            # Create secure temporary file for processing
            with tempfile.NamedTemporaryFile(suffix='.tmp', dir=self.media_dir / "temp", delete=False) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(image_data)
            
            try:
                # Process image in isolated manner
                processed_result = self._process_image_securely(temp_path, validation_metadata)
                return processed_result
            finally:
                # Always clean up temp file
                try:
                    temp_path.unlink()
                except Exception as e:
                    logging.warning(f"Failed to delete temp file {temp_path}: {e}")
                    
        except Exception as e:
            logging.error(f"Secure image processing failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _process_image_securely(self, image_path: Path, validation_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process image with security constraints"""
        try:
            # Load image with security constraints
            with Image.open(image_path) as img:
                # Remove potential security risks
                # Strip EXIF data and other metadata
                cleaned_img = Image.new(img.mode, img.size, (255, 255, 255))
                if img.mode == 'P':
                    # Handle palette mode carefully
                    cleaned_img = img.convert('RGB')
                else:
                    cleaned_img.paste(img, (0, 0))
                
                # Ensure safe format conversion
                if cleaned_img.mode in ('RGBA', 'P'):
                    cleaned_img = cleaned_img.convert('RGB')
                
                # Generate secure filename
                secure_filename = self._generate_secure_filename(validation_metadata)
                
                # Save cleaned image
                output_path = self.media_dir / "images" / secure_filename
                cleaned_img.save(output_path, format='JPEG', quality=90, optimize=True)
                
                # Create thumbnails
                thumbnails = self._create_secure_thumbnails(cleaned_img, secure_filename)
                
                return {
                    "success": True,
                    "filename": secure_filename,
                    "path": str(output_path),
                    "thumbnails": thumbnails,
                    "metadata": {
                        "size": cleaned_img.size,
                        "mode": cleaned_img.mode,
                        "format": "JPEG",
                        "file_size": output_path.stat().st_size
                    }
                }
                
        except Exception as e:
            logging.error(f"Secure image processing failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_secure_filename(self, validation_metadata: Dict[str, Any]) -> str:
        """Generate cryptographically secure filename"""
        import secrets
        import time
        
        # Create hash from metadata and timestamp
        content_hash = hashlib.sha256(
            f"{validation_metadata.get('file_size', 0)}"
            f"{validation_metadata.get('actual_mime_type', '')}"
            f"{time.time()}"
            f"{secrets.token_hex(16)}"
            .encode()
        ).hexdigest()[:16]
        
        return f"img_{content_hash}.jpg"
    
    def _create_secure_thumbnails(self, img: Image.Image, base_filename: str) -> Dict[str, Dict]:
        """Create thumbnails with security constraints"""
        thumbnails = {}
        base_name = Path(base_filename).stem
        
        for size_name, size_tuple in self.THUMBNAIL_SIZES.items():
            try:
                # Create thumbnail
                thumb_img = img.copy()
                thumb_img.thumbnail(size_tuple, Image.Resampling.LANCZOS)
                
                # Create square background
                square_thumb = Image.new('RGB', size_tuple, (255, 255, 255))
                x = (size_tuple[0] - thumb_img.width) // 2
                y = (size_tuple[1] - thumb_img.height) // 2
                square_thumb.paste(thumb_img, (x, y))
                
                # Save thumbnail
                thumb_filename = f"{base_name}_thumb_{size_name}.jpg"
                thumb_path = self.media_dir / "thumbnails" / thumb_filename
                square_thumb.save(thumb_path, format='JPEG', quality=85, optimize=True)
                
                thumbnails[size_name] = {
                    "filename": thumb_filename,
                    "path": str(thumb_path),
                    "size": size_tuple,
                    "file_size": thumb_path.stat().st_size
                }
                
            except Exception as e:
                logging.warning(f"Failed to create {size_name} thumbnail: {e}")
                thumbnails[size_name] = None
        
        return thumbnails
    
    def _safe_parse_frame_rate(self, frame_rate_str: str) -> float:
        """Safely parse frame rate string (e.g., '30/1' or '29.97') without eval()"""
        try:
            if not frame_rate_str or not isinstance(frame_rate_str, str):
                return 0.0
            
            # Clean the input - only allow digits, slash, and dot
            cleaned = ''.join(c for c in frame_rate_str if c.isdigit() or c in './')
            
            if '/' in cleaned:
                # Handle fraction format like "30/1" or "29970/1000"
                try:
                    fraction = Fraction(cleaned)
                    return float(fraction)
                except (ValueError, ZeroDivisionError):
                    return 0.0
            else:
                # Handle decimal format like "29.97"
                try:
                    return float(cleaned)
                except ValueError:
                    return 0.0
        except Exception as e:
            logging.warning(f"Failed to parse frame rate '{frame_rate_str}': {e}")
            return 0.0
    
    def extract_video_thumbnail(self, video_url: str, timestamp: float = 1.0) -> Optional[bytes]:
        """Extract thumbnail from video at specified timestamp using FFmpeg"""
        if not ffmpeg:
            print("FFmpeg not available - cannot extract video thumbnail")
            return None
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_thumb:
                temp_thumb_path = temp_thumb.name
            
            # Use FFmpeg to extract frame at timestamp
            (
                ffmpeg
                .input(video_url, ss=timestamp)
                .output(temp_thumb_path, vframes=1, format='image2', vcodec='mjpeg')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            # Read the generated thumbnail
            with open(temp_thumb_path, 'rb') as f:
                thumbnail_data = f.read()
            
            # Clean up temp file
            os.unlink(temp_thumb_path)
            
            return thumbnail_data
            
        except Exception as e:
            print(f"Failed to extract video thumbnail: {e}")
            # Clean up temp file if it exists
            try:
                os.unlink(temp_thumb_path)
            except:
                pass
            return None
    
    def create_video_thumbnails(self, video_url: str, timestamp: float = 1.0) -> Dict[str, Optional[bytes]]:
        """Create multiple thumbnail sizes from video"""
        # First extract a frame from the video
        video_frame = self.extract_video_thumbnail(video_url, timestamp)
        if not video_frame:
            return {size_name: None for size_name in self.THUMBNAIL_SIZES.keys()}
        
        # Use existing image thumbnail creation for the extracted frame
        return self.create_multiple_thumbnails(video_frame)
    
    def validate_video(self, video_url: str) -> Dict[str, Any]:
        """Validate video and return metadata using FFmpeg"""
        if not ffmpeg:
            return {"valid": False, "error": "FFmpeg not available"}
        
        try:
            # Probe video file for metadata
            probe = ffmpeg.probe(video_url)
            
            # Find video stream
            video_stream = next(
                (stream for stream in probe['streams'] if stream['codec_type'] == 'video'), 
                None
            )
            
            if not video_stream:
                return {"valid": False, "error": "No video stream found"}
            
            return {
                "valid": True,
                "format": probe['format']['format_name'],
                "duration": float(probe['format'].get('duration', 0)),
                "width": int(video_stream.get('width', 0)),
                "height": int(video_stream.get('height', 0)),
                "codec": video_stream.get('codec_name', ''),
                "fps": self._safe_parse_frame_rate(video_stream.get('r_frame_rate', '0/1')),
                "bitrate": int(probe['format'].get('bit_rate', 0))
            }
            
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    def is_video_url(self, url: str) -> bool:
        """Check if URL appears to be a video based on extension or content"""
        video_extensions = {'.mp4', '.webm', '.mov', '.avi', '.mkv', '.m4v', '.flv'}
        return any(url.lower().endswith(ext) for ext in video_extensions)
    
    async def process_media_from_url(self, url: str, create_thumbnails: bool = True) -> Dict[str, Any]:
        """Process media (image or video) from URL and generate thumbnails"""
        # Check if this is a video URL
        if self.is_video_url(url):
            return await self.process_video_from_url(url, create_thumbnails)
        else:
            # Use existing image processing
            return await self.process_image_from_url(url, create_thumbnails)
    
    async def process_video_from_url(self, video_url: str, create_thumbnails: bool = True) -> Dict[str, Any]:
        """Process video from URL and generate thumbnails"""
        # Validate video
        validation = self.validate_video(video_url)
        if not validation["valid"]:
            return {"success": False, "error": f"Invalid video: {validation['error']}"}
        
        # Generate filename
        filename = self.generate_filename(video_url, "video")
        
        result = {
            "success": True,
            "filename": filename,
            "metadata": validation,
            "original_url": video_url,
            "media_type": "video"
        }
        
        # Create thumbnails if requested
        if create_thumbnails:
            # Extract thumbnail at 10% of video duration or 1 second, whichever is smaller
            duration = validation.get('duration', 10)
            timestamp = min(1.0, duration * 0.1) if duration > 0 else 1.0
            
            thumbnails = self.create_video_thumbnails(video_url, timestamp)
            result["thumbnails"] = {}
            
            for size_name, thumbnail_data in thumbnails.items():
                if thumbnail_data:
                    thumb_filename = self.generate_filename(video_url, f"video_thumb_{size_name}")
                    result["thumbnails"][size_name] = {
                        "filename": thumb_filename,
                        "data": thumbnail_data,
                        "size": self.THUMBNAIL_SIZES[size_name],
                        "timestamp": timestamp
                    }
        
        return result
    
    def optimize_image(self, image_data: bytes, max_size: Tuple[int, int] = (1200, 1200), quality: int = 85) -> bytes:
        """Optimize image for web display"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Resize if too large
                if img.width > max_size[0] or img.height > max_size[1]:
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Save optimized version
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=quality, optimize=True)
                return output.getvalue()
                
        except Exception as e:
            print(f"Failed to optimize image: {e}")
            return image_data  # Return original if optimization fails


# Global instance
media_utils = MediaUtils()