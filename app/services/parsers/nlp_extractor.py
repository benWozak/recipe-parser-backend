import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from .text_processor import TextProcessor, RecipePattern

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None


@dataclass
class EnhancedIngredient:
    """Enhanced ingredient with parsed components"""
    name: str
    quantity: Optional[str] = None
    unit: Optional[str] = None
    preparation: Optional[str] = None  # e.g., "chopped", "diced"
    raw_text: str = ""
    confidence: float = 0.0


@dataclass
class EnhancedInstruction:
    """Enhanced instruction with parsed components"""
    text: str
    step_number: Optional[int] = None
    cooking_method: Optional[str] = None  # e.g., "bake", "fry"
    temperature: Optional[str] = None
    duration: Optional[str] = None
    confidence: float = 0.0


class NLPExtractor:
    """Advanced NLP-based recipe extraction using spaCy"""
    
    def __init__(self):
        self.text_processor = TextProcessor()
        self.nlp = None  # Will be loaded on first use
        
        # Enhanced patterns for ingredient parsing
        self.quantity_patterns = [
            r'(\d+(?:\.\d+)?)\s*-?\s*(\d+(?:\.\d+)?)?',  # 1-2, 1.5, etc.
            r'(\d+)\s*/\s*(\d+)',  # 1/2, 3/4
            r'(half|quarter|third)',  # word numbers
            r'(a\s+few|several|some|handful)',  # approximate quantities
        ]
        
        self.unit_patterns = {
            'volume': ['cup', 'cups', 'c', 'tablespoon', 'tablespoons', 'tbsp', 'tsp', 'teaspoon', 'teaspoons', 
                      'ml', 'milliliter', 'milliliters', 'l', 'liter', 'liters', 'fl oz', 'fluid ounce'],
            'weight': ['lb', 'lbs', 'pound', 'pounds', 'oz', 'ounce', 'ounces', 'g', 'gram', 'grams', 
                      'kg', 'kilogram', 'kilograms'],
            'count': ['piece', 'pieces', 'slice', 'slices', 'clove', 'cloves', 'bunch', 'bunches',
                     'can', 'cans', 'jar', 'jars', 'package', 'packages', 'bag', 'bags']
        }
        
        self.preparation_methods = [
            'chopped', 'diced', 'minced', 'sliced', 'grated', 'shredded', 'crushed',
            'mashed', 'pureed', 'julienned', 'cubed', 'quartered', 'halved',
            'peeled', 'trimmed', 'cleaned', 'washed', 'dried'
        ]
        
        self.cooking_methods = [
            'bake', 'baking', 'roast', 'roasting', 'fry', 'frying', 'sauté', 'sautéing',
            'boil', 'boiling', 'simmer', 'simmering', 'steam', 'steaming', 'grill', 'grilling',
            'broil', 'broiling', 'braise', 'braising', 'stew', 'stewing', 'poach', 'poaching'
        ]
    
    def _load_spacy_model(self):
        """Load spaCy model on first use"""
        if not SPACY_AVAILABLE:
            self.nlp = None
            return
            
        if self.nlp is None:
            try:
                # Try to load English model (requires: python -m spacy download en_core_web_sm)
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                try:
                    # Fallback to blank model if en_core_web_sm not installed
                    self.nlp = spacy.blank("en")
                    # Add basic components
                    if "tagger" not in self.nlp.pipe_names:
                        self.nlp.add_pipe("tagger")
                    if "parser" not in self.nlp.pipe_names:
                        self.nlp.add_pipe("parser")
                except Exception:
                    # If spaCy can't create even a blank model, disable it
                    self.nlp = None
    
    def extract_enhanced_recipe(self, text: str) -> Dict[str, Any]:
        """Extract recipe with enhanced NLP processing"""
        # First get basic extraction
        basic_pattern = self.text_processor.extract_recipe_from_text(text)
        
        # Load spaCy model
        self._load_spacy_model()
        
        # Enhance with NLP
        enhanced_ingredients = self._parse_ingredients_with_nlp(basic_pattern.ingredients, text)
        enhanced_instructions = self._parse_instructions_with_nlp(basic_pattern.instructions, text)
        
        # Extract additional information
        cooking_time = self._extract_cooking_time(text)
        temperature = self._extract_temperature(text)
        
        return {
            'title': basic_pattern.title,
            'confidence': basic_pattern.confidence,
            'ingredients': enhanced_ingredients,
            'instructions': enhanced_instructions,
            'cooking_time': cooking_time,
            'temperature': temperature,
            'hashtags': self.text_processor.extract_hashtags(text),
            'mentions': self.text_processor.extract_mentions(text),
            'recipe_type': self.text_processor.detect_recipe_type(text)
        }
    
    def _parse_ingredients_with_nlp(self, ingredients: List[str], full_text: str) -> List[EnhancedIngredient]:
        """Parse ingredients using NLP for better component extraction"""
        enhanced_ingredients = []
        
        for ingredient_text in ingredients:
            enhanced = self._parse_single_ingredient(ingredient_text)
            enhanced_ingredients.append(enhanced)
        
        return enhanced_ingredients
    
    def _parse_single_ingredient(self, ingredient_text: str) -> EnhancedIngredient:
        """Parse a single ingredient into components"""
        original_text = ingredient_text.strip()
        text = original_text.lower()
        
        # Initialize result
        ingredient = EnhancedIngredient(
            name="",
            raw_text=original_text,
            confidence=0.5
        )
        
        # Extract quantity
        quantity_match = None
        for pattern in self.quantity_patterns:
            match = re.search(pattern, text)
            if match:
                quantity_match = match
                ingredient.quantity = match.group(0)
                break
        
        # Extract unit
        for unit_type, units in self.unit_patterns.items():
            for unit in units:
                if f" {unit}" in text or text.startswith(unit):
                    ingredient.unit = unit
                    break
            if ingredient.unit:
                break
        
        # Extract preparation method
        for prep in self.preparation_methods:
            if prep in text:
                ingredient.preparation = prep
                break
        
        # Extract ingredient name (what's left after removing quantity, unit, preparation)
        name_text = text
        
        # Remove quantity
        if quantity_match:
            name_text = name_text.replace(quantity_match.group(0), "", 1)
        
        # Remove unit
        if ingredient.unit:
            name_text = name_text.replace(ingredient.unit, "", 1)
        
        # Remove preparation
        if ingredient.preparation:
            name_text = name_text.replace(ingredient.preparation, "", 1)
        
        # Clean up name
        name_text = re.sub(r'\s+', ' ', name_text).strip()
        name_text = re.sub(r'^(of|,|-)', '', name_text).strip()
        
        ingredient.name = name_text if name_text else original_text
        
        # Calculate confidence based on parsing success
        confidence = 0.3  # Base confidence
        if ingredient.quantity:
            confidence += 0.2
        if ingredient.unit:
            confidence += 0.2
        if len(ingredient.name.split()) >= 1:
            confidence += 0.3
        
        ingredient.confidence = min(confidence, 1.0)
        
        return ingredient
    
    def _parse_instructions_with_nlp(self, instructions: List[str], full_text: str) -> List[EnhancedInstruction]:
        """Parse instructions using NLP for better component extraction"""
        enhanced_instructions = []
        
        for i, instruction_text in enumerate(instructions):
            enhanced = self._parse_single_instruction(instruction_text, i + 1)
            enhanced_instructions.append(enhanced)
        
        return enhanced_instructions
    
    def _parse_single_instruction(self, instruction_text: str, step_num: int) -> EnhancedInstruction:
        """Parse a single instruction into components"""
        text = instruction_text.strip()
        text_lower = text.lower()
        
        instruction = EnhancedInstruction(
            text=text,
            step_number=step_num,
            confidence=0.5
        )
        
        # Extract cooking method
        for method in self.cooking_methods:
            if method in text_lower:
                instruction.cooking_method = method
                break
        
        # Extract temperature
        temp_patterns = [
            r'(\d+)\s*°?\s*f',  # 350°F, 350 F
            r'(\d+)\s*degrees?\s*f',  # 350 degrees F
            r'(\d+)\s*°?\s*c',  # 180°C
        ]
        
        for pattern in temp_patterns:
            match = re.search(pattern, text_lower)
            if match:
                instruction.temperature = match.group(0)
                break
        
        # Extract duration
        duration_patterns = [
            r'(\d+(?:-\d+)?)\s*minutes?',
            r'(\d+(?:-\d+)?)\s*hours?',
            r'(\d+)\s*-\s*(\d+)\s*min',
            r'for\s+(\d+(?:-\d+)?)\s*(?:minutes?|mins?|hours?|hrs?)',
            r'until\s+\w+',  # "until golden"
        ]
        
        for pattern in duration_patterns:
            match = re.search(pattern, text_lower)
            if match:
                instruction.duration = match.group(0)
                break
        
        # Calculate confidence
        confidence = 0.4  # Base confidence
        if instruction.cooking_method:
            confidence += 0.2
        if instruction.temperature:
            confidence += 0.2
        if instruction.duration:
            confidence += 0.2
        
        instruction.confidence = min(confidence, 1.0)
        
        return instruction
    
    def _extract_cooking_time(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract total cooking time from text"""
        text_lower = text.lower()
        
        time_patterns = [
            r'total\s+time:?\s*(\d+(?:-\d+)?)\s*(minutes?|hours?|mins?|hrs?)',
            r'cooking\s+time:?\s*(\d+(?:-\d+)?)\s*(minutes?|hours?|mins?|hrs?)',
            r'takes?\s+(\d+(?:-\d+)?)\s*(minutes?|hours?|mins?|hrs?)',
            r'ready\s+in\s+(\d+(?:-\d+)?)\s*(minutes?|hours?|mins?|hrs?)'
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return {
                    'duration': match.group(1),
                    'unit': match.group(2),
                    'raw_text': match.group(0)
                }
        
        return None
    
    def _extract_temperature(self, text: str) -> Optional[str]:
        """Extract cooking temperature from text"""
        text_lower = text.lower()
        
        temp_patterns = [
            r'(\d+)\s*°?\s*f(?:ahrenheit)?',
            r'(\d+)\s*degrees?\s*f(?:ahrenheit)?',
            r'(\d+)\s*°?\s*c(?:elsius)?',
            r'preheat.*?(\d+)\s*°?\s*[fc]'
        ]
        
        for pattern in temp_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(0)
        
        return None
    
    
    def extract_ingredients_from_text(self, text: str) -> List[EnhancedIngredient]:
        """Extract just ingredients from free text"""
        # Use basic text processor first
        basic_pattern = self.text_processor.extract_recipe_from_text(text)
        
        # Enhance with NLP
        return self._parse_ingredients_with_nlp(basic_pattern.ingredients, text)
    
    def extract_instructions_from_text(self, text: str) -> List[EnhancedInstruction]:
        """Extract just instructions from free text"""
        # Use basic text processor first
        basic_pattern = self.text_processor.extract_recipe_from_text(text)
        
        # Enhance with NLP
        return self._parse_instructions_with_nlp(basic_pattern.instructions, text)