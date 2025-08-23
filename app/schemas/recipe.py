from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SourceType(str, Enum):
    manual = "manual"
    website = "website"
    instagram = "instagram"
    image = "image"

class TagBase(BaseModel):
    name: str
    color: Optional[str] = None

class TagCreate(TagBase):
    pass

class Tag(TagBase):
    id: str

    class Config:
        from_attributes = True

class RecipeBase(BaseModel):
    title: str
    description: Optional[str] = None
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    total_time: Optional[int] = None
    servings: Optional[int] = None
    source_type: SourceType = SourceType.manual
    source_url: Optional[str] = None
    media: Optional[Dict[str, Any]] = None
    instructions: Optional[Dict[str, Any]] = None

class RecipeCreate(RecipeBase):
    ingredients: Optional[Dict[str, Any]] = None
    tags: List[TagCreate] = []
    collection_id: Optional[str] = None

class RecipeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    prep_time: Optional[int] = None
    cook_time: Optional[int] = None
    total_time: Optional[int] = None
    servings: Optional[int] = None
    source_type: Optional[SourceType] = None
    source_url: Optional[str] = None
    media: Optional[Dict[str, Any]] = None
    instructions: Optional[Dict[str, Any]] = None
    ingredients: Optional[Dict[str, Any]] = None
    tags: Optional[List[TagCreate]] = None
    collection_id: Optional[str] = None

class Recipe(RecipeBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    ingredients: Optional[Dict[str, Any]] = None
    tags: List[Tag] = []
    collection_id: Optional[str] = None

    class Config:
        from_attributes = True