from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from pydantic import BaseModel, validator
from datetime import datetime
from app.utils.id_utils import generate_id
from .base_parser import ParsedRecipe


class ValidationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class ValidationIssue(BaseModel):
    """Represents a validation issue found during parsing"""
    type: str  # "missing_ingredients", "low_confidence", "unclear_instructions", etc.
    severity: str  # "warning", "error", "info"
    message: str
    field: Optional[str] = None  # Which field has the issue
    suggestion: Optional[str] = None  # Suggested fix


class ParsedRecipeValidation(BaseModel):
    """Extended parsed recipe with validation metadata"""
    id: str
    parsed_recipe: ParsedRecipe
    validation_status: ValidationStatus
    issues: List[ValidationIssue]
    created_at: datetime
    user_id: Optional[str] = None
    original_source: str
    parsing_metadata: Dict[str, Any] = {}
    
    class Config:
        use_enum_values = True


class ValidationPipeline:
    """Pipeline for validating and managing parsed recipes"""
    
    def __init__(self):
        # In-memory storage for demo (in production, use database)
        self.pending_recipes: Dict[str, ParsedRecipeValidation] = {}
        
        # Validation thresholds
        self.confidence_thresholds = {
            'minimum': 0.2,
            'review_required': 0.5,
            'auto_approve': 0.8
        }
        
        # Required fields for complete recipes
        self.required_fields = ['title', 'instructions', 'ingredients']
        self.recommended_fields = ['description', 'prep_time', 'cook_time', 'servings']
    
    def validate_parsed_recipe(self, 
                              parsed_recipe: ParsedRecipe, 
                              source_url: str,
                              user_id: Optional[str] = None,
                              parsing_metadata: Dict[str, Any] = None) -> ParsedRecipeValidation:
        """Validate a parsed recipe and return validation result"""
        
        validation_id = generate_id()
        issues = []
        
        # Run validation checks
        issues.extend(self._check_required_fields(parsed_recipe))
        issues.extend(self._check_confidence_scores(parsed_recipe))
        issues.extend(self._check_content_quality(parsed_recipe))
        issues.extend(self._check_data_consistency(parsed_recipe))
        
        # Determine validation status
        status = self._determine_validation_status(parsed_recipe, issues)
        
        validation_result = ParsedRecipeValidation(
            id=validation_id,
            parsed_recipe=parsed_recipe,
            validation_status=status,
            issues=issues,
            created_at=datetime.utcnow(),
            user_id=user_id,
            original_source=source_url,
            parsing_metadata=parsing_metadata or {}
        )
        
        # Store for review if needed
        if status in [ValidationStatus.PENDING, ValidationStatus.NEEDS_REVIEW]:
            self.pending_recipes[validation_id] = validation_result
        
        return validation_result
    
    def _check_required_fields(self, recipe: ParsedRecipe) -> List[ValidationIssue]:
        """Check if required fields are present"""
        issues = []
        
        if not recipe.title or len(recipe.title.strip()) < 3:
            issues.append(ValidationIssue(
                type="missing_title",
                severity="error",
                message="Recipe title is missing or too short",
                field="title",
                suggestion="Add a descriptive title for the recipe"
            ))
        
        # Check if ingredients exist (now HTML string)
        if not recipe.ingredients or recipe.ingredients.strip() == "":
            issues.append(ValidationIssue(
                type="missing_ingredients",
                severity="error",
                message="No ingredients found",
                field="ingredients",
                suggestion="Add at least one ingredient"
            ))
        
        # Check if instructions exist (now HTML string)
        if not recipe.instructions or recipe.instructions.strip() == "":
            issues.append(ValidationIssue(
                type="missing_instructions",
                severity="error",
                message="No cooking instructions found",
                field="instructions",
                suggestion="Add step-by-step cooking instructions"
            ))
        
        return issues
    
    def _check_confidence_scores(self, recipe: ParsedRecipe) -> List[ValidationIssue]:
        """Check confidence scores and flag low-confidence parsing"""
        issues = []
        
        if recipe.confidence_score < self.confidence_thresholds['minimum']:
            issues.append(ValidationIssue(
                type="very_low_confidence",
                severity="error",
                message=f"Very low parsing confidence ({recipe.confidence_score:.2f})",
                field="confidence_score",
                suggestion="Consider manual review of all extracted data"
            ))
        elif recipe.confidence_score < self.confidence_thresholds['review_required']:
            issues.append(ValidationIssue(
                type="low_confidence",
                severity="warning",
                message=f"Low parsing confidence ({recipe.confidence_score:.2f})",
                field="confidence_score",
                suggestion="Review and verify extracted ingredients and instructions"
            ))
        
        return issues
    
    def _check_content_quality(self, recipe: ParsedRecipe) -> List[ValidationIssue]:
        """Check quality of extracted content"""
        issues = []
        
        # Check ingredient quality (now HTML string)
        if recipe.ingredients and recipe.ingredients.strip():
            # Count <li> elements as a proxy for ingredient count
            ingredient_count = recipe.ingredients.count('<li>')
            if ingredient_count == 0:
                issues.append(ValidationIssue(
                    type="unformatted_ingredients",
                    severity="warning",
                    message="Ingredients may not be properly formatted",
                    field="ingredients",
                    suggestion="Consider formatting as a bulleted list"
                ))
        
        # Check instruction quality (now HTML string)
        if recipe.instructions and recipe.instructions.strip():
            # Count <li> elements as a proxy for instruction count
            instruction_count = recipe.instructions.count('<li>')
            if instruction_count == 0:
                issues.append(ValidationIssue(
                    type="unformatted_instructions",
                    severity="warning",
                    message="Instructions may not be properly formatted",
                    field="instructions",
                    suggestion="Consider formatting as a numbered or bulleted list"
                ))
        
        # Check for missing recommended fields
        missing_recommended = []
        if not recipe.description or len(recipe.description.strip()) < 10:
            missing_recommended.append("description")
        if not recipe.prep_time and not recipe.cook_time and not recipe.total_time:
            missing_recommended.append("timing information")
        if not recipe.servings:
            missing_recommended.append("serving size")
        
        if missing_recommended:
            issues.append(ValidationIssue(
                type="missing_recommended",
                severity="info",
                message=f"Missing recommended fields: {', '.join(missing_recommended)}",
                suggestion="Consider adding these fields for a complete recipe"
            ))
        
        return issues
    
    def _check_data_consistency(self, recipe: ParsedRecipe) -> List[ValidationIssue]:
        """Check for data consistency issues"""
        issues = []
        
        # Check timing consistency
        if (recipe.prep_time and recipe.cook_time and recipe.total_time and
            recipe.total_time < max(recipe.prep_time, recipe.cook_time)):
            issues.append(ValidationIssue(
                type="timing_inconsistency",
                severity="warning",
                message="Total time seems inconsistent with prep/cook times",
                field="timing",
                suggestion="Verify timing information"
            ))
        
        # Check servings vs ingredients - handle HTML string format
        if recipe.ingredients and recipe.servings:
            ingredient_count = 0
            if isinstance(recipe.ingredients, str):
                # Count <li> elements as ingredients in HTML format
                ingredient_count = recipe.ingredients.count('<li>')
            elif isinstance(recipe.ingredients, dict):
                for category, ingredient_list in recipe.ingredients.items():
                    if isinstance(ingredient_list, list):
                        ingredient_count += len(ingredient_list)
            elif isinstance(recipe.ingredients, list):
                ingredient_count = len(recipe.ingredients)
            
            if ingredient_count < 2 and recipe.servings > 6:
                issues.append(ValidationIssue(
                    type="servings_mismatch",
                    severity="info",
                    message="High serving count with few ingredients",
                    field="servings",
                    suggestion="Verify serving size or ingredient list"
                ))
        
        return issues
    
    def _determine_validation_status(self, recipe: ParsedRecipe, issues: List[ValidationIssue]) -> ValidationStatus:
        """Determine validation status based on confidence and issues"""
        
        # Check for errors
        error_count = sum(1 for issue in issues if issue.severity == "error")
        if error_count > 0:
            return ValidationStatus.NEEDS_REVIEW
        
        # Check confidence thresholds
        if recipe.confidence_score >= self.confidence_thresholds['auto_approve']:
            warning_count = sum(1 for issue in issues if issue.severity == "warning")
            if warning_count <= 1:  # Allow one warning for auto-approval
                return ValidationStatus.APPROVED
        
        # Default to needs review for anything else
        return ValidationStatus.NEEDS_REVIEW
    
    def get_pending_recipe(self, validation_id: str) -> Optional[ParsedRecipeValidation]:
        """Get a pending recipe by ID"""
        return self.pending_recipes.get(validation_id)
    
    def approve_recipe(self, validation_id: str, user_edits: Optional[Dict[str, Any]] = None) -> ParsedRecipeValidation:
        """Approve a recipe, optionally with user edits"""
        if validation_id not in self.pending_recipes:
            raise ValueError(f"Recipe {validation_id} not found")
        
        validation_result = self.pending_recipes[validation_id]
        
        # Apply user edits if provided
        if user_edits:
            validation_result.parsed_recipe = self._apply_user_edits(
                validation_result.parsed_recipe, 
                user_edits
            )
        
        validation_result.validation_status = ValidationStatus.APPROVED
        
        # Remove from pending
        del self.pending_recipes[validation_id]
        
        return validation_result
    
    def reject_recipe(self, validation_id: str, reason: str) -> ParsedRecipeValidation:
        """Reject a recipe with reason"""
        if validation_id not in self.pending_recipes:
            raise ValueError(f"Recipe {validation_id} not found")
        
        validation_result = self.pending_recipes[validation_id]
        validation_result.validation_status = ValidationStatus.REJECTED
        
        # Add rejection reason as an issue
        validation_result.issues.append(ValidationIssue(
            type="user_rejected",
            severity="error",
            message=f"Rejected by user: {reason}",
            suggestion="Manual entry may be required"
        ))
        
        # Remove from pending
        del self.pending_recipes[validation_id]
        
        return validation_result
    
    def _apply_user_edits(self, recipe: ParsedRecipe, edits: Dict[str, Any]) -> ParsedRecipe:
        """Apply user edits to a parsed recipe"""
        # Create a copy and apply edits
        recipe_dict = recipe.dict()
        
        for field, value in edits.items():
            if field in recipe_dict:
                recipe_dict[field] = value
        
        # Update confidence score since user has reviewed
        recipe_dict['confidence_score'] = min(recipe_dict['confidence_score'] + 0.3, 1.0)
        
        return ParsedRecipe(**recipe_dict)
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation pipeline status"""
        total_pending = len(self.pending_recipes)
        
        status_counts = {}
        issue_counts = {}
        
        for validation in self.pending_recipes.values():
            status = validation.validation_status
            status_counts[status] = status_counts.get(status, 0) + 1
            
            for issue in validation.issues:
                issue_type = issue.type
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
        
        return {
            'total_pending': total_pending,
            'status_breakdown': status_counts,
            'common_issues': issue_counts,
            'thresholds': self.confidence_thresholds
        }
    
    def list_pending_recipes(self, limit: int = 50) -> List[ParsedRecipeValidation]:
        """List pending recipes for review"""
        return list(self.pending_recipes.values())[:limit]