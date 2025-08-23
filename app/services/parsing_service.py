from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from app.schemas.recipe import RecipeCreate
from app.core.config import settings
from app.services.parsers import URLParser, InstagramParser, ValidationPipeline, ParsedRecipe
from app.services.parsers.url_parser import WebsiteProtectionError
from app.services.parsers.progress_events import ProgressEventEmitter

class ParsingService:
    def __init__(self, db: Session):
        self.db = db
        self.url_parser = URLParser()  # URLParser no longer takes db as parameter
        self.instagram_parser = InstagramParser(db)
        self.validation_pipeline = ValidationPipeline()

    async def parse_from_url(self, url: str, user_id: Optional[str] = None, collection_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            # Parse using new URL parser
            parsed_recipe = await self.url_parser.parse(url)
            
            # Convert user_id to string if it's a UUID object
            user_id_str = str(user_id) if user_id is not None else None
            
            # Validate the parsed recipe
            validation_result = self.validation_pipeline.validate_parsed_recipe(
                parsed_recipe, url, user_id_str
            )
            
            # Convert to legacy format for API compatibility
            return self._convert_to_legacy_format(validation_result.parsed_recipe, collection_id)
            
        except WebsiteProtectionError as e:
            # Re-raise WebsiteProtectionError to be handled by API layer
            raise e
        except Exception as e:
            raise Exception(f"Failed to parse recipe from URL: {str(e)}")

    async def parse_from_url_with_progress(self, url: str, user_id: Optional[str] = None, collection_id: Optional[str] = None, progress_emitter: Optional[ProgressEventEmitter] = None) -> Dict[str, Any]:
        """Parse recipe from URL with progress tracking"""
        try:
            # Parse using URL parser with progress tracking
            parsed_recipe = await self.url_parser.parse(url, progress_emitter=progress_emitter)
            
            # Convert user_id to string if it's a UUID object
            user_id_str = str(user_id) if user_id is not None else None
            
            # Validate the parsed recipe
            validation_result = self.validation_pipeline.validate_parsed_recipe(
                parsed_recipe, url, user_id_str
            )
            
            # Convert to legacy format for API compatibility
            return self._convert_to_legacy_format(validation_result.parsed_recipe, collection_id)
            
        except WebsiteProtectionError as e:
            # Re-raise WebsiteProtectionError to be handled by API layer
            raise e
        except Exception as e:
            raise Exception(f"Failed to parse recipe from URL: {str(e)}")

    async def parse_from_instagram(self, url: str, user_id: Optional[str] = None, collection_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            # Parse using new Instagram parser
            parsed_recipe = await self.instagram_parser.parse(url)
            
            # Convert user_id to string if it's a UUID object
            user_id_str = str(user_id) if user_id is not None else None
            
            # Validate the parsed recipe
            validation_result = self.validation_pipeline.validate_parsed_recipe(
                parsed_recipe, url, user_id_str, {"parser_type": "instagram"}
            )
            
            # Convert to legacy format for API compatibility
            return self._convert_to_legacy_format(validation_result.parsed_recipe, collection_id)
            
        except Exception as e:
            raise Exception(f"Failed to parse recipe from Instagram: {str(e)}")

    async def parse_from_image(self, image_data: bytes, user_id: Optional[str] = None, collection_id: Optional[str] = None) -> Dict[str, Any]:
        # Placeholder for OCR image parsing
        # In a real implementation, you would use Google Cloud Vision or similar
        result = {
            "title": "Recipe from Image",
            "description": "Recipe parsed from uploaded image",
            "source_type": "image",
            "instructions": {"steps": ["Please add recipe steps manually"]},
            "ingredients": []
        }
        
        if collection_id:
            result["collection_id"] = collection_id
            
        return result
    
    def _convert_to_legacy_format(self, parsed_recipe: ParsedRecipe, collection_id: Optional[str] = None) -> Dict[str, Any]:
        """Convert ParsedRecipe to legacy API format"""
        result = {
            "title": parsed_recipe.title,
            "description": parsed_recipe.description,
            "source_type": parsed_recipe.source_type,
            "source_url": parsed_recipe.source_url,
            "prep_time": parsed_recipe.prep_time,
            "cook_time": parsed_recipe.cook_time,
            "total_time": parsed_recipe.total_time,
            "servings": parsed_recipe.servings,
            "instructions": parsed_recipe.instructions,  # Now structured
            "ingredients": parsed_recipe.ingredients,    # Now structured
            "confidence_score": parsed_recipe.confidence_score,
            "media": parsed_recipe.media
        }
        
        if collection_id:
            result["collection_id"] = collection_id
            
        return result

