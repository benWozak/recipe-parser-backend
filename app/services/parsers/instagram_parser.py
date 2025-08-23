import instaloader
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from .base_parser import BaseParser, ParsedRecipe
from .text_processor import TextProcessor, RecipePattern
from app.utils.storage_utils import storage_utils
from app.utils.media_utils import media_utils


class InstagramParser(BaseParser):
    """Parser for Instagram posts using instaloader"""
    
    def __init__(self, db):
        super().__init__(db)
        self.loader = instaloader.Instaloader()
        self.text_processor = TextProcessor()
        
        # Configure instaloader to avoid rate limiting
        self.loader.context.quiet = True
        self.loader.context.request_timeout = 30
        
    async def parse(self, instagram_url: str, **kwargs) -> ParsedRecipe:
        """Parse recipe from Instagram post URL"""
        try:
            # Extract shortcode from URL
            shortcode = self._extract_shortcode(instagram_url)
            if not shortcode:
                raise ValueError("Invalid Instagram URL format")
            
            # Download post metadata
            post = self._get_post_data(shortcode)
            
            # Validate post object before proceeding
            if not isinstance(post, instaloader.Post):
                raise Exception(f"Expected Post object, got {type(post)}")
            
            # Extract text content
            text_content = self._extract_text_content(post)
            
            # Process text for recipe components
            recipe_pattern = self.text_processor.extract_recipe_from_text(text_content)
            
            # Extract servings information from the pattern or text
            servings_count = None
            if recipe_pattern.servings:
                servings_match = re.search(r'(\d+)', recipe_pattern.servings)
                if servings_match:
                    servings_count = int(servings_match.group(1))
            
            # Extract proper description (not from recipe pattern)
            try:
                description = self._extract_description_from_post(text_content)
            except Exception as e:
                description = "Recipe from Instagram"  # Fallback
            
            # Extract additional metadata
            media_data = self._extract_media_data(post)
            
            # Store media with thumbnails if available
            await self._process_and_store_media(media_data)
            
            # Generate video thumbnails if this is a video post
            if post.is_video and media_data.get("video_url"):
                try:
                    video_thumbnails = await self._generate_video_thumbnails(media_data["video_url"])
                    if video_thumbnails:
                        media_data["video_thumbnails"] = video_thumbnails
                except Exception as e:
                    print(f"Failed to generate video thumbnails: {e}")
            
            # Build parsed recipe with structured data
            parsed_data = ParsedRecipe(
                title=recipe_pattern.title or f"Recipe from @{post.owner_username}",
                description=description,
                source_type="instagram",
                source_url=instagram_url,
                servings=servings_count,
                instructions=recipe_pattern.instructions,
                ingredients=recipe_pattern.ingredients,
                confidence_score=recipe_pattern.confidence,
                media=media_data
            )
            
            return self._validate_parsed_data(parsed_data)
            
        except Exception as e:
            raise Exception(f"Failed to parse Instagram recipe: {str(e)}")
    
    def _extract_shortcode(self, url: str) -> Optional[str]:
        """Extract Instagram post shortcode from URL"""
        # Handle various Instagram URL formats
        patterns = [
            # Direct post/reel/tv URLs (old format)
            r'instagram\.com/p/([^/?]+)',
            r'instagram\.com/reel/([^/?]+)',
            r'instagram\.com/tv/([^/?]+)',
            # User-specific URLs (new format with username in path)
            r'instagram\.com/([^/]+)/(p|reel|tv)/([^/?]+)',
            # Stories URLs
            r'instagram\.com/stories/[^/]+/([^/?]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                # For user-specific URLs, return the shortcode (group 3)
                if len(match.groups()) == 3:
                    return match.group(3)
                # For other URLs, return the shortcode (group 1)
                else:
                    return match.group(1)
        
        return None
    
    def _get_post_data(self, shortcode: str) -> instaloader.Post:
        """Get post data using instaloader"""
        try:
            post = instaloader.Post.from_shortcode(self.loader.context, shortcode)
            # Validate that we got a proper Post object
            if not hasattr(post, 'owner_username'):
                raise Exception("Invalid post object returned from instaloader")
            return post
        except Exception as e:
            raise Exception(f"Failed to fetch Instagram post: {str(e)}")
    
    def _extract_text_content(self, post: instaloader.Post) -> str:
        """Extract all text content from Instagram post"""
        text_parts = []
        
        # Main caption
        if post.caption:
            text_parts.append(post.caption)
        
        # Comments (first few, if accessible)
        try:
            comments = []
            for comment in post.get_comments():
                comments.append(comment.text)
                if len(comments) >= 5:  # Limit to avoid rate limiting
                    break
            
            if comments:
                text_parts.extend(comments)
        except:
            # Comments might not be accessible
            pass
        
        return "\n".join(text_parts)
    
    def _extract_description_from_post(self, full_text: str) -> str:
        """Extract description from Instagram post text"""
        lines = full_text.split('\n')
        
        # Look for the main descriptive paragraph (usually first or second line)
        for line in lines[:5]:
            line = line.strip()
            # Find long descriptive text that doesn't look like recipe content
            if (len(line) > 30 and 
                not re.search(r'makes?\s+\d+.*servings?|serves?\s+\d+', line.lower()) and
                not re.search(r'\d+\s*(cup|tsp|tbsp|oz|lb|gram)', line.lower()) and
                not line.lower().startswith(('make', 'combine', 'mix', 'add', 'cook', 'bake')) and
                '#' in line):  # Instagram descriptions often have hashtags
                
                # Remove hashtags and mentions for cleaner description
                clean_line = re.sub(r'#\w+', '', line)
                clean_line = re.sub(r'@\w+', '', clean_line)
                clean_line = re.sub(r'\s+', ' ', clean_line).strip()
                
                # Truncate if too long
                if len(clean_line) > 200:
                    clean_line = clean_line[:200] + "..."
                
                return clean_line
        
        # Fallback: look for any descriptive text
        for line in lines[:3]:
            line = line.strip()
            if (len(line) > 20 and 
                not re.search(r'\d+\s*(cup|tsp|tbsp|oz|lb)', line.lower()) and
                not line.lower().startswith(('ingredients', 'instructions', 'make', 'combine'))):
                return line[:150] + ("..." if len(line) > 150 else "")
        
        return "Recipe from Instagram"
    
    def _extract_media_data(self, post: instaloader.Post) -> Dict[str, Any]:
        """Extract media information from post"""
        media_data = {
            "type": "instagram_post",
            "post_id": post.shortcode,
            "username": post.owner_username,
            "timestamp": post.date_utc.isoformat() if post.date_utc else None,
            "likes": post.likes,
            "is_video": post.is_video,
            "images": []
        }
        
        # Add video URL if this is a video post
        if post.is_video:
            try:
                if hasattr(post, 'video_url'):
                    media_data["video_url"] = post.video_url
                    media_data["video_duration"] = getattr(post, 'video_duration', None)
            except:
                # Video URL might not be accessible
                pass
        
        # Add image/thumbnail URLs
        try:
            if hasattr(post, 'url'):
                # For videos, this is typically the thumbnail
                # For images, this is the actual image
                media_data["images"].append({
                    "url": post.url,
                    "width": post.dimensions[0] if post.dimensions else None,
                    "height": post.dimensions[1] if post.dimensions else None,
                    "type": "thumbnail" if post.is_video else "image"
                })
            
            # Handle sidecar posts (multiple images/videos)
            if hasattr(post, 'get_sidecar_nodes'):
                for node in post.get_sidecar_nodes():
                    if hasattr(node, 'display_url'):
                        media_item = {
                            "url": node.display_url,
                            "width": node.dimensions[0] if hasattr(node, 'dimensions') and node.dimensions else None,
                            "height": node.dimensions[1] if hasattr(node, 'dimensions') and node.dimensions else None,
                            "type": "thumbnail" if getattr(node, 'is_video', False) else "image"
                        }
                        
                        # Add video URL for video nodes if available
                        if getattr(node, 'is_video', False) and hasattr(node, 'video_url'):
                            try:
                                media_item["video_url"] = node.video_url
                                media_item["video_duration"] = getattr(node, 'video_duration', None)
                                media_item["requires_thumbnail"] = True  # Flag for video thumbnail generation
                            except:
                                pass
                        
                        media_data["images"].append(media_item)
        except:
            # Media extraction might fail due to privacy settings
            pass
        
        return media_data
    
    def parse_instagram_profile(self, username: str, max_posts: int = 10) -> List[ParsedRecipe]:
        """Parse multiple recipe posts from an Instagram profile"""
        try:
            profile = instaloader.Profile.from_username(self.loader.context, username)
            recipes = []
            
            for post in profile.get_posts():
                if len(recipes) >= max_posts:
                    break
                
                try:
                    # Check if post might contain a recipe
                    if self._post_looks_like_recipe(post):
                        instagram_url = f"https://www.instagram.com/p/{post.shortcode}/"
                        recipe = self.parse(instagram_url)
                        
                        # Only add if confidence is reasonable
                        if recipe.confidence_score > 0.3:
                            recipes.append(recipe)
                            
                except Exception:
                    # Skip posts that fail to parse
                    continue
            
            return recipes
            
        except Exception as e:
            raise Exception(f"Failed to parse Instagram profile: {str(e)}")
    
    def _post_looks_like_recipe(self, post: instaloader.Post) -> bool:
        """Quick check if post might contain a recipe"""
        if not post.caption:
            return False
        
        caption_lower = post.caption.lower()
        
        # Look for recipe-related keywords
        recipe_keywords = [
            'recipe', 'ingredients', 'cook', 'bake', 'preparation',
            'delicious', 'homemade', 'easy', 'simple', 'tasty',
            'cup', 'tablespoon', 'teaspoon', 'minutes', 'degrees'
        ]
        
        keyword_count = sum(1 for keyword in recipe_keywords if keyword in caption_lower)
        
        # Must have at least 2 recipe keywords and reasonable length
        return keyword_count >= 2 and len(post.caption.split()) >= 20
    
    def search_recipe_hashtags(self, hashtag: str, max_posts: int = 20) -> List[ParsedRecipe]:
        """Search for recipes using hashtags"""
        try:
            hashtag_obj = instaloader.Hashtag.from_name(self.loader.context, hashtag)
            recipes = []
            
            for post in hashtag_obj.get_posts():
                if len(recipes) >= max_posts:
                    break
                
                try:
                    if self._post_looks_like_recipe(post):
                        instagram_url = f"https://www.instagram.com/p/{post.shortcode}/"
                        recipe = self.parse(instagram_url)
                        
                        if recipe.confidence_score > 0.4:  # Higher threshold for hashtag searches
                            recipes.append(recipe)
                            
                except Exception:
                    continue
            
            return recipes
            
        except Exception as e:
            raise Exception(f"Failed to search hashtag {hashtag}: {str(e)}")
    
    def _validate_parsed_data(self, parsed_data: ParsedRecipe) -> ParsedRecipe:
        """Enhanced validation for Instagram-specific data"""
        # Use base validation first
        parsed_data = super()._validate_parsed_data(parsed_data)
        
        # Instagram-specific adjustments
        if parsed_data.confidence_score < 0.3:
            # Low confidence - add warning to description
            if parsed_data.description:
                parsed_data.description += " [Note: Low confidence parsing - please review]"
            else:
                parsed_data.description = "Recipe extracted from Instagram post. Please review and edit as needed."
        
        # Ensure we have some basic content
        if not parsed_data.ingredients and not parsed_data.instructions:
            parsed_data.description = "Instagram post detected but no recipe content found. Please add ingredients and instructions manually."
            parsed_data.confidence_score = 0.1
        
        return parsed_data
    
    async def _process_and_store_media(self, media_data: Dict[str, Any]) -> None:
        """Process and store media (images/videos) with thumbnails"""
        if media_data.get("images"):
            try:
                # Store the primary image/thumbnail
                primary_image = media_data["images"][0]
                if primary_image.get("url"):
                    storage_result = await storage_utils.store_media_from_url(
                        primary_image["url"],
                        recipe_id=None  # Will be set later when recipe is saved
                    )
                    
                    if storage_result.get("success"):
                        # Add stored media info to media_data
                        media_data["stored_media"] = {
                            "media_id": storage_result["media_id"],
                            "thumbnails": {
                                "small": storage_utils.get_thumbnail_url(storage_result["media_id"], "small"),
                                "medium": storage_utils.get_thumbnail_url(storage_result["media_id"], "medium"),
                                "large": storage_utils.get_thumbnail_url(storage_result["media_id"], "large")
                            },
                            "original": storage_utils.get_original_url(storage_result["media_id"])
                        }
            except Exception as e:
                print(f"Failed to store media for Instagram post: {e}")
    
    async def _generate_video_thumbnails(self, video_url: str) -> Optional[Dict[str, Any]]:
        """Generate thumbnails for video posts"""
        try:
            # Use media_utils to process video and generate thumbnails
            video_result = await media_utils.process_video_from_url(video_url, create_thumbnails=True)
            
            if video_result.get("success") and video_result.get("thumbnails"):
                return {
                    "video_metadata": video_result["metadata"],
                    "thumbnails": {
                        size: {
                            "filename": thumb_data["filename"],
                            "size": thumb_data["size"],
                            "timestamp": thumb_data["timestamp"]
                        } for size, thumb_data in video_result["thumbnails"].items()
                    }
                }
            return None
        except Exception as e:
            print(f"Failed to generate video thumbnails: {e}")
            return None