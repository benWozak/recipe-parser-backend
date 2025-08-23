from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum

class MealType(str, Enum):
    breakfast = "breakfast"
    lunch = "lunch"
    dinner = "dinner"
    snack = "snack"

class MealPlanEntryBase(BaseModel):
    recipe_id: str
    date: date
    meal_type: MealType
    servings: int = 1

class MealPlanEntryCreate(MealPlanEntryBase):
    pass

class MealPlanEntry(MealPlanEntryBase):
    id: str
    meal_plan_id: str

    class Config:
        from_attributes = True

# Enhanced meal plan entry that includes recipe details for frontend display
class RecipeDetails(BaseModel):
    id: str
    title: str
    media: Optional[Dict[str, Any]] = None
    source_url: Optional[str] = None

    class Config:
        from_attributes = True

class MealPlanEntryWithRecipe(MealPlanEntryBase):
    id: str
    meal_plan_id: str
    recipe: Optional[RecipeDetails] = None

    class Config:
        from_attributes = True

class MealPlanBase(BaseModel):
    name: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = False

class MealPlanCreate(MealPlanBase):
    entries: List[MealPlanEntryCreate] = []

class MealPlanUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None
    entries: Optional[List[MealPlanEntryCreate]] = None

class MealPlan(MealPlanBase):
    id: str
    user_id: str
    is_active: bool
    created_at: datetime
    entries: List[MealPlanEntry] = []

    class Config:
        from_attributes = True

# Enhanced meal plan for active meal plan endpoint with recipe details
class MealPlanWithRecipeDetails(MealPlanBase):
    id: str
    user_id: str
    is_active: bool
    created_at: datetime
    entries: List[MealPlanEntryWithRecipe] = []

    class Config:
        from_attributes = True