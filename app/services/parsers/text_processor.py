import re
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass


@dataclass
class RecipePattern:
    """Pattern matching result for recipe components"""
    ingredients: str  # HTML formatted ingredients
    instructions: str  # HTML formatted instructions
    title: str
    confidence: float
    servings: Optional[str] = None


class TextProcessor:
    """Utility class for extracting recipe components from unstructured text"""
    
    def __init__(self):
        # Common recipe keywords and patterns
        self.ingredient_keywords = [
            'ingredients?', 'recipe', 'you[\'ll]? need', 'shopping list',
            'what you need', 'grocery list', 'supplies'
        ]
        
        self.instruction_keywords = [
            'instructions?', 'directions?', 'method', 'steps?', 'how to make',
            'preparation', 'cooking method', 'recipe', 'procedure'
        ]
        
        # Common measurement units
        self.measurement_units = [
            'cup', 'cups', 'tbsp', 'tablespoon', 'tablespoons', 'tsp', 'teaspoon', 'teaspoons',
            'oz', 'ounce', 'ounces', 'lb', 'pound', 'pounds', 'g', 'gram', 'grams',
            'kg', 'kilogram', 'kilograms', 'ml', 'milliliter', 'milliliters',
            'l', 'liter', 'liters', 'pinch', 'dash', 'handful', 'clove', 'cloves',
            'slice', 'slices', 'piece', 'pieces', 'can', 'cans', 'jar', 'jars',
            'package', 'packages', 'bunch', 'bunches'
        ]
        
        # Common cooking actions for instructions
        self.cooking_actions = [
            'mix', 'stir', 'combine', 'whisk', 'beat', 'fold', 'chop', 'dice',
            'mince', 'slice', 'cut', 'heat', 'cook', 'bake', 'fry', 'sauté',
            'boil', 'simmer', 'roast', 'grill', 'season', 'add', 'remove',
            'serve', 'garnish', 'blend', 'process', 'knead', 'roll', 'pour'
        ]
    
    def extract_recipe_from_text(self, text: str) -> RecipePattern:
        """Main method to extract recipe components from text"""
        # Clean and prepare text
        cleaned_text = self._clean_text(text)
        
        # Try to identify title
        title = self._extract_title(cleaned_text)
        
        # Split text into potential sections
        sections = self._split_into_sections(cleaned_text)
        
        # Extract servings info first (before processing ingredients)
        servings = self._extract_servings_info(cleaned_text)
        
        # Extract ingredients and instructions with better categorization
        ingredients_structured = self._extract_ingredients_structured(sections, cleaned_text)
        instructions_structured = self._extract_instructions_structured(sections)
        
        # Calculate confidence score
        confidence = self._calculate_confidence_structured(ingredients_structured, instructions_structured, cleaned_text)
        
        return RecipePattern(
            ingredients=ingredients_structured,
            instructions=instructions_structured,
            title=title,
            confidence=confidence,
            servings=servings
        )
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for processing"""
        # Preserve line breaks for better section detection
        text = re.sub(r'\r\n', '\n', text)  # Normalize Windows line breaks
        text = re.sub(r'\n{3,}', '\n\n', text)  # Limit excessive line breaks
        
        # Remove common social media artifacts but keep structure
        text = re.sub(r'http[s]?://\S+', '', text)  # Remove URLs
        
        return text.strip()
    
    def _extract_title(self, text: str) -> str:
        """Extract potential recipe title from text"""
        lines = text.split('\n')
        
        # Look for short lines that might be titles
        for line in lines[:3]:  # Check first 3 lines
            line = line.strip()
            if 5 <= len(line) <= 50 and not self._looks_like_ingredient(line):
                # Check if it contains recipe-like words
                recipe_words = ['recipe', 'easy', 'homemade', 'delicious', 'simple']
                if any(word in line.lower() for word in recipe_words):
                    return line
        
        # Fallback: use first meaningful line
        for line in lines:
            line = line.strip()
            if len(line) > 5 and len(line.split()) >= 2:
                return line[:50]  # Truncate if too long
        
        return "Recipe from Instagram"
    
    def _split_into_sections(self, text: str) -> Dict[str, List[str]]:
        """Split text into potential ingredient and instruction sections"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        sections = {
            'ingredients': [],
            'instructions': [],
            'other': []
        }
        
        current_section = 'other'
        
        for line in lines:
            line_lower = line.lower()
            
            # Check if line indicates start of ingredients section
            if any(keyword in line_lower for keyword in self.ingredient_keywords):
                current_section = 'ingredients'
                continue
            
            # Check if line indicates start of instructions section
            if any(keyword in line_lower for keyword in self.instruction_keywords):
                current_section = 'instructions'
                continue
            
            # Add line to current section
            sections[current_section].append(line)
        
        return sections
    
    def _extract_ingredients(self, sections: Dict[str, List[str]]) -> List[str]:
        """Extract ingredients from text sections"""
        ingredients = []
        
        # First, check explicit ingredients section
        if sections['ingredients']:
            for line in sections['ingredients']:
                if self._looks_like_ingredient(line):
                    ingredients.append(line)
        
        # If no explicit section, look in all text
        if not ingredients:
            all_lines = sections['ingredients'] + sections['other']
            for line in all_lines:
                if self._looks_like_ingredient(line):
                    ingredients.append(line)
        
        return ingredients[:20]  # Limit to reasonable number
    
    def _extract_instructions(self, sections: Dict[str, List[str]]) -> List[str]:
        """Extract instructions from text sections"""
        instructions = []
        
        # First, check explicit instructions section
        if sections['instructions']:
            for line in sections['instructions']:
                if self._looks_like_instruction(line):
                    instructions.append(line)
        
        # If no explicit section, look in all text
        if not instructions:
            all_lines = sections['instructions'] + sections['other']
            for line in all_lines:
                if self._looks_like_instruction(line):
                    instructions.append(line)
        
        return instructions[:15]  # Limit to reasonable number
    
    def _looks_like_ingredient(self, line: str) -> bool:
        """Determine if a line looks like an ingredient"""
        line_lower = line.lower().strip()
        
        # Skip empty lines or very short lines
        if len(line_lower) < 3:
            return False
        
        # Check for bullet points or list indicators first
        if re.match(r'^\s*[-•*]\s+', line):
            # Remove bullet point for further analysis
            line_clean = re.sub(r'^\s*[-•*]\s+', '', line_lower)
            if len(line_clean.split()) <= 8 and len(line_clean) > 3:
                return True
        
        # Check for measurement units
        if any(unit in line_lower for unit in self.measurement_units):
            return True
        
        # Check for numbers (quantities) with reasonable length
        if re.search(r'\d+', line) and len(line.split()) <= 8:
            # Must have some food-related words or be reasonably short
            food_indicators = [
                'oil', 'salt', 'pepper', 'sugar', 'flour', 'butter', 'milk',
                'egg', 'cheese', 'chicken', 'beef', 'fish', 'onion', 'garlic',
                'tomato', 'water', 'vinegar', 'lemon', 'herbs', 'spice', 'vanilla',
                'baking', 'powder', 'soda', 'chocolate', 'chips'
            ]
            if any(food in line_lower for food in food_indicators):
                return True
        
        return False
    
    def _looks_like_instruction(self, line: str) -> bool:
        """Determine if a line looks like a cooking instruction"""
        line_lower = line.lower().strip()
        
        # Skip empty lines or very short lines
        if len(line_lower) < 5:
            return False
        
        # Check for instruction patterns first
        instruction_patterns = [
            r'^\d+\.',  # Numbered steps
            r'^step \d+',  # Step numbered
            r'^\d+\)\s+',  # 1) format
            r'^first|^then|^next|^finally',  # Sequence words
        ]
        
        if any(re.search(pattern, line_lower) for pattern in instruction_patterns):
            return True
        
        # Check for cooking action words
        if any(action in line_lower for action in self.cooking_actions):
            # Must be reasonably long to be an instruction
            if len(line.split()) >= 3:
                return True
        
        # Check for time/temperature indicators
        if re.search(r'until|for \d+|°|degrees|minutes?|hours?|oven|bake', line_lower):
            if len(line.split()) >= 3:
                return True
        
        return False
    
    def _calculate_confidence(self, ingredients: List[str], instructions: List[str], full_text: str) -> float:
        """Calculate confidence score for recipe extraction"""
        score = 0.0
        
        # Base score for having ingredients and instructions
        if ingredients:
            score += 0.3
        if instructions:
            score += 0.3
        
        # Bonus for reasonable quantities
        if len(ingredients) >= 3:
            score += 0.2
        if len(instructions) >= 2:
            score += 0.2
        
        # Check for recipe-related keywords in full text
        recipe_keywords = [
            'recipe', 'cook', 'bake', 'ingredients', 'instructions',
            'delicious', 'homemade', 'easy', 'simple', 'tasty'
        ]
        
        keyword_count = sum(1 for keyword in recipe_keywords if keyword in full_text.lower())
        score += min(keyword_count * 0.05, 0.2)
        
        # Penalty for very short content
        if len(full_text.split()) < 10:
            score *= 0.5
        
        return min(score, 1.0)
    
    def extract_hashtags(self, text: str) -> List[str]:
        """Extract hashtags from text"""
        hashtags = re.findall(r'#(\w+)', text)
        return hashtags
    
    def extract_mentions(self, text: str) -> List[str]:
        """Extract mentions from text"""
        mentions = re.findall(r'@(\w+)', text)
        return mentions
    
    def detect_recipe_type(self, text: str) -> Optional[str]:
        """Try to detect the type of recipe from text"""
        text_lower = text.lower()
        
        recipe_types = {
            'dessert': ['cake', 'cookie', 'pie', 'dessert', 'sweet', 'chocolate', 'sugar'],
            'main_dish': ['chicken', 'beef', 'fish', 'pasta', 'rice', 'dinner', 'lunch'],
            'breakfast': ['breakfast', 'pancake', 'eggs', 'toast', 'cereal', 'morning'],
            'soup': ['soup', 'broth', 'stew', 'chili'],
            'salad': ['salad', 'greens', 'lettuce', 'fresh'],
            'beverage': ['drink', 'smoothie', 'juice', 'coffee', 'tea']
        }
        
        for category, keywords in recipe_types.items():
            if any(keyword in text_lower for keyword in keywords):
                return category
        
        return None
    
    def _extract_servings_info(self, text: str) -> Optional[str]:
        """Extract serving information from text"""
        servings_patterns = [
            r'makes?\s+(\d+(?:\s*to\s*\d+)?)\s*servings?',
            r'serves?\s+(\d+(?:\s*to\s*\d+)?)',
            r'(\d+(?:\s*-\s*\d+)?)\s*servings?',
            r'yield:?\s*(\d+(?:\s*to\s*\d+)?)',
        ]
        
        text_lower = text.lower()
        for pattern in servings_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return match.group(1)
        return None
    
    def _extract_ingredients_enhanced(self, sections: Dict[str, List[str]]) -> List[str]:
        """Enhanced ingredient extraction that handles categories and filters out instructions"""
        ingredients = []
        
        # Process ingredients section
        all_ingredient_lines = sections['ingredients'] + sections['other']
        
        for line in all_ingredient_lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip servings info
            if re.search(r'makes?\s+\d+.*servings?|serves?\s+\d+', line.lower()):
                continue
                
            # Skip obvious instructions (long sentences with cooking verbs)
            if self._looks_like_instruction_not_ingredient(line):
                continue
                
            # Check if it's a category header
            if self._looks_like_category_header(line):
                # Add category as a section marker (you might want to handle this differently)
                ingredients.append(f"--- {line} ---")
                continue
                
            # Check if it looks like an ingredient
            if self._looks_like_ingredient(line):
                ingredients.append(line)
        
        return ingredients[:25]  # Reasonable limit
    
    def _extract_instructions_enhanced(self, sections: Dict[str, List[str]]) -> List[str]:
        """Enhanced instruction extraction"""
        instructions = []
        
        # Look in all sections for instructions
        all_lines = sections['instructions'] + sections['other'] + sections['ingredients']
        
        for line in all_lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip category headers and serving info
            if (self._looks_like_category_header(line) or 
                re.search(r'makes?\s+\d+.*servings?|serves?\s+\d+', line.lower())):
                continue
                
            # Check if it looks like an instruction
            if self._looks_like_instruction_not_ingredient(line):
                instructions.append(line)
        
        return instructions[:15]
    
    def _looks_like_category_header(self, line: str) -> bool:
        """Check if line looks like a category header (e.g., 'Dressing', 'Chicken Salad')"""
        line = line.strip()
        
        # Don't treat instruction section headers as ingredient categories
        instruction_headers = ['instructions', 'directions', 'method', 'steps', 'preparation']
        if any(header in line.lower() for header in instruction_headers):
            return False
        
        # Single words or short phrases that are common recipe section headers
        category_indicators = [
            'dressing', 'sauce', 'marinade', 'filling', 'topping', 'garnish',
            'salad', 'chicken', 'beef', 'fish', 'vegetables', 'base', 'mix',
            'for serving', 'assembly', 'crust', 'batter'
        ]
        
        # Must be relatively short and not contain measurements
        if (len(line.split()) <= 3 and 
            not re.search(r'\d+', line) and 
            not any(unit in line.lower() for unit in self.measurement_units) and
            len(line) > 3):
            
            # Check if it matches common category patterns
            line_lower = line.lower()
            if any(cat in line_lower for cat in category_indicators):
                return True
                
            # Or if it's a simple noun phrase without articles and colons (like "Chicken Salad:")
            if (not line_lower.startswith(('a ', 'an ', 'the ')) and
                not any(verb in line_lower for verb in ['make', 'add', 'mix', 'cook', 'heat']) and
                line.endswith(':')):
                return True
        
        return False
    
    def _looks_like_instruction_not_ingredient(self, line: str) -> bool:
        """Check if line looks like an instruction rather than an ingredient"""
        line_lower = line.lower().strip()
        
        # Skip empty or very short lines
        if len(line_lower) < 10:
            return False
        
        # Strong instruction indicators
        instruction_starters = [
            'make the', 'in a', 'add the', 'combine', 'mix', 'stir', 'blend',
            'season with', 'pour', 'toss', 'cook', 'heat', 'bake', 'fry'
        ]
        
        if any(line_lower.startswith(starter) for starter in instruction_starters):
            return True
        
        # Check for cooking actions in longer sentences
        if (len(line.split()) >= 5 and 
            any(action in line_lower for action in self.cooking_actions)):
            return True
        
        # Check for instruction patterns
        if re.search(r'until|for \d+|degrees?|minutes?|hours?|°[cf]', line_lower):
            return True
        
        return False
    
    def _extract_ingredients_structured(self, sections: Dict[str, List[str]], full_text: str) -> str:
        """Extract ingredients as HTML content"""
        # Filter out description text from processing
        description_text = self._extract_description_text(full_text)
        
        all_lines = sections['ingredients'] + sections['other']
        
        # Structure: categorized ingredients with HTML formatting
        current_category = None
        categorized_ingredients = []
        current_items = []
        
        for line in all_lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip description text
            if description_text and line in description_text:
                continue
                
            # Skip serving info
            if re.search(r'makes?\s+\d+.*servings?|serves?\s+\d+', line.lower()):
                continue
                
            # Skip obvious instructions
            if self._looks_like_instruction_not_ingredient(line):
                continue
                
            # Check if it's a category header
            if self._looks_like_category_header(line) and not self._looks_like_instruction_not_ingredient(line):
                # Save previous category if it has items
                if current_category and current_items:
                    categorized_ingredients.append((current_category, current_items))
                
                # Start new category
                current_category = line.rstrip(':')
                current_items = []
                continue
                
            # Check if it looks like an ingredient
            if self._looks_like_ingredient(line):
                current_items.append(line)
        
        # Add final category
        if current_category and current_items:
            categorized_ingredients.append((current_category, current_items))
        
        # If no categories found, treat all as one list
        if not categorized_ingredients and current_items:
            categorized_ingredients.append((None, current_items))
        
        # Convert to HTML
        return self._ingredients_to_html(categorized_ingredients)
    
    def _extract_instructions_structured(self, sections: Dict[str, List[str]]) -> str:
        """Extract instructions as HTML content"""
        all_lines = sections['instructions'] + sections['other'] + sections['ingredients']
        
        instructions = []
        
        for line in all_lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip category headers and serving info
            if (self._looks_like_category_header(line) or 
                re.search(r'makes?\s+\d+.*servings?|serves?\s+\d+', line.lower())):
                continue
                
            # Check if it looks like an instruction
            if self._looks_like_instruction_not_ingredient(line):
                instructions.append(line)
        
        # Convert to HTML ordered list
        return self._instructions_to_html(instructions[:15])
    
    def _extract_description_text(self, full_text: str) -> Optional[str]:
        """Extract the main description text to avoid including it in ingredients"""
        lines = full_text.split('\n')
        
        # Look for long descriptive paragraphs (usually at the beginning)
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            # Skip title-like lines and serving info
            if (len(line) > 50 and 
                not re.search(r'makes?\s+\d+.*servings?|serves?\s+\d+', line.lower()) and
                not self._looks_like_ingredient(line) and
                not self._looks_like_instruction_not_ingredient(line)):
                return line
        
        return None
    
    def _ingredients_to_html(self, categorized_ingredients: List[Tuple[Optional[str], List[str]]]) -> str:
        """Convert categorized ingredients to HTML"""
        if not categorized_ingredients:
            return ""
        
        html_parts = []
        
        for category, items in categorized_ingredients:
            if category:
                # Add category as heading
                html_parts.append(f"<h3>{category}</h3>")
            
            if items:
                # Add ingredients as unordered list
                list_items = "".join(f"<li>{item}</li>" for item in items)
                html_parts.append(f"<ul>{list_items}</ul>")
        
        return "".join(html_parts)
    
    def _instructions_to_html(self, instructions: List[str]) -> str:
        """Convert instructions to HTML ordered list"""
        if not instructions:
            return ""
        
        # Clean up instructions that already have numbers
        cleaned_instructions = []
        for instruction in instructions:
            # Remove existing numbering (1., 2., etc.)
            cleaned = re.sub(r'^\d+\.\s*', '', instruction.strip())
            if cleaned:
                cleaned_instructions.append(cleaned)
        
        if not cleaned_instructions:
            return ""
        
        # Create ordered list
        list_items = "".join(f"<li>{instruction}</li>" for instruction in cleaned_instructions)
        return f"<ol>{list_items}</ol>"
    
    def _calculate_confidence_structured(self, ingredients: str, instructions: str, full_text: str) -> float:
        """Calculate confidence score for structured recipe extraction"""
        score = 0.0
        
        # Count HTML elements to estimate content
        ingredients_count = ingredients.count('<li>')
        instructions_count = instructions.count('<li>')
        
        # Base score for having content
        if ingredients_count > 0:
            score += 0.3
        if instructions_count > 0:
            score += 0.3
        
        # Bonus for reasonable quantities
        if ingredients_count >= 3:
            score += 0.2
        if instructions_count >= 2:
            score += 0.2
        
        # Check for recipe-related keywords
        recipe_keywords = [
            'recipe', 'cook', 'bake', 'ingredients', 'instructions',
            'delicious', 'homemade', 'easy', 'simple', 'tasty'
        ]
        keyword_count = sum(1 for keyword in recipe_keywords if keyword in full_text.lower())
        score += min(keyword_count * 0.05, 0.15)
        
        return min(score, 1.0)