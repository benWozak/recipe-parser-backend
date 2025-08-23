from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class CollectionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Collection name")
    description: Optional[str] = Field(None, max_length=1000, description="Optional collection description")

class CollectionCreate(CollectionBase):
    pass

class CollectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)

class CollectionSchema(CollectionBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = {"from_attributes": True}


class CollectionWithStats(CollectionSchema):
    recipe_count: int = Field(0, description="Number of recipes in this collection")
    
class CollectionListResponse(BaseModel):
    collections: List[CollectionSchema]
    total: int
    skip: int
    limit: int