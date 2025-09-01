from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel
import re

try:
    from sqlalchemy.orm import Session
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    Session = None


class ParsedRecipe(BaseModel):
    """Data structure for parsed recipe data"""
    title: str
    description: str = ""
    source_type: str
    source_url: Optional[str] = None
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    total_time: Optional[int] = None
    servings: Optional[int] = None
    instructions: str  # HTML formatted instructions
    ingredients: str   # HTML formatted ingredients
    notes: str = ""    # HTML formatted notes
    confidence_score: float = 0.0
    media: Optional[Dict[str, Any]] = None


class BaseParser(ABC):
    """Abstract base class for all recipe parsers"""
    
    def __init__(self, db: Union[Session, None] = None):
        self.db = db
    
    @abstractmethod
    async def parse(self, source: str, **kwargs) -> ParsedRecipe:
        """Parse recipe from source and return structured data"""
        pass
    
    def _parse_duration(self, duration_str: Optional[str]) -> Optional[int]:
        """Parse duration string into minutes"""
        if not duration_str:
            return None
        
        # Parse ISO 8601 duration (PT15M) or simple formats
        if duration_str.startswith('PT'):
            # ISO 8601 format
            match = re.search(r'(\d+)H', duration_str)
            hours = int(match.group(1)) if match else 0
            match = re.search(r'(\d+)M', duration_str)
            minutes = int(match.group(1)) if match else 0
            return hours * 60 + minutes
        
        # Try to extract number from string
        match = re.search(r'(\d+)', str(duration_str))
        return int(match.group(1)) if match else None
    
    def _parse_yield(self, yield_data) -> Optional[int]:
        """Parse serving/yield data into integer"""
        if not yield_data:
            return None
        
        if isinstance(yield_data, (int, float)):
            return int(yield_data)
        
        if isinstance(yield_data, str):
            match = re.search(r'(\d+)', yield_data)
            return int(match.group(1)) if match else None
        
        return None
    
    def _parse_instructions(self, instructions_data) -> List[str]:
        """Parse instructions from various formats"""
        instructions = []
        
        if not instructions_data:
            return instructions
        
        for instruction in instructions_data:
            if isinstance(instruction, str):
                instructions.append(instruction.strip())
            elif isinstance(instruction, dict):
                text = instruction.get('text', '') or instruction.get('name', '')
                if text:
                    instructions.append(text.strip())
        
        return instructions
    
    def _parse_ingredients(self, ingredients_data) -> List[Dict[str, Any]]:
        """Parse ingredients from various formats"""
        ingredients = []
        
        if not ingredients_data:
            return ingredients
        
        for ingredient in ingredients_data:
            if isinstance(ingredient, str):
                # Simple parsing of ingredient string
                ingredient_text = ingredient.strip()
                ingredients.append({"name": ingredient_text})
            elif isinstance(ingredient, dict):
                # Structured ingredient data
                name = ingredient.get('name', ingredient.get('text', ''))
                if name:
                    ingredients.append({"name": name.strip()})
        
        return ingredients
    
    def _calculate_confidence_score(self, parsed_data: ParsedRecipe) -> float:
        """Calculate confidence score based on parsed data completeness"""
        score = 0.0
        max_score = 100.0
        
        # Title presence and quality
        if parsed_data.title and len(parsed_data.title.strip()) > 3:
            score += 20
        
        # Instructions presence and quality
        if isinstance(parsed_data.instructions, str):
            # Count HTML list items to estimate instruction count
            instruction_count = parsed_data.instructions.count('<li>')
            if instruction_count >= 3:
                score += 30
            elif instruction_count >= 1:
                score += 15
        
        # Ingredients presence and quality
        if isinstance(parsed_data.ingredients, str):
            # Count HTML list items to estimate ingredient count
            ingredient_count = parsed_data.ingredients.count('<li>')
            if ingredient_count >= 3:
                score += 25
            elif ingredient_count >= 1:
                score += 10
        
        # Timing information
        if parsed_data.prep_time or parsed_data.cook_time or parsed_data.total_time:
            score += 10
        
        # Servings information
        if parsed_data.servings:
            score += 5
        
        # Description presence
        if parsed_data.description and len(parsed_data.description.strip()) > 10:
            score += 10
        
        return min(score / max_score, 1.0)
    
    def _validate_parsed_data(self, parsed_data: ParsedRecipe) -> ParsedRecipe:
        """Validate and clean parsed recipe data"""
        # Calculate confidence score
        parsed_data.confidence_score = self._calculate_confidence_score(parsed_data)
        
        # Ensure required fields have defaults
        if not parsed_data.title:
            parsed_data.title = "Untitled Recipe"
        
        if not parsed_data.instructions:
            parsed_data.instructions = ""
        
        if not parsed_data.ingredients:
            parsed_data.ingredients = ""
            
        if not parsed_data.notes:
            parsed_data.notes = ""
        
        return parsed_data