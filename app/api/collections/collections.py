from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.config import settings
from app.api.auth.auth import get_current_user
from app.models.user import User
from app.schemas.collection import (
    CollectionSchema, 
    CollectionCreate, 
    CollectionUpdate, 
    CollectionWithStats,
    CollectionListResponse
)
from app.services.collection_service import CollectionService
from app.middleware.rate_limit import limiter

router = APIRouter()

@router.get("/", response_model=List[CollectionSchema])
async def get_collections(
    skip: int = Query(0, ge=0, description="Number of collections to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of collections to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all collections for the current user."""
    collection_service = CollectionService(db)
    collections = collection_service.get_user_collections(current_user.id, skip, limit)
    return collections

@router.get("/stats", response_model=List[CollectionWithStats])
async def get_collections_with_stats(
    skip: int = Query(0, ge=0, description="Number of collections to skip"),
    limit: int = Query(100, ge=1, le=100, description="Maximum number of collections to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all collections for the current user with recipe counts."""
    collection_service = CollectionService(db)
    collections = collection_service.get_user_collections_with_stats(current_user.id, skip, limit)
    return collections

@router.get("/{collection_id}", response_model=CollectionSchema)
async def get_collection(
    collection_id: str,
    include_recipes: bool = Query(False, description="Include recipes in the response"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific collection by ID."""
    collection_service = CollectionService(db)
    collection = collection_service.get_collection_by_id(
        collection_id, current_user.id, include_recipes=include_recipes
    )
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )
    
    return collection

@router.post("/", response_model=CollectionSchema, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.COLLECTION_RATE_LIMIT)
async def create_collection(
    collection_data: CollectionCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new collection."""
    collection_service = CollectionService(db)
    collection = collection_service.create_collection(collection_data, current_user.id)
    return collection

@router.put("/{collection_id}", response_model=CollectionSchema)
@limiter.limit(settings.COLLECTION_RATE_LIMIT)
async def update_collection(
    collection_id: str,
    collection_data: CollectionUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an existing collection."""
    collection_service = CollectionService(db)
    collection = collection_service.update_collection(
        collection_id, collection_data, current_user.id
    )
    
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )
    
    return collection

@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.COLLECTION_RATE_LIMIT)
async def delete_collection(
    collection_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a collection."""
    collection_service = CollectionService(db)
    success = collection_service.delete_collection(collection_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection not found"
        )

@router.post("/{collection_id}/recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.COLLECTION_RATE_LIMIT)
async def add_recipe_to_collection(
    collection_id: str,
    recipe_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a recipe to a collection."""
    collection_service = CollectionService(db)
    collection_service.add_recipe_to_collection(collection_id, recipe_id, current_user.id)

@router.delete("/{collection_id}/recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.COLLECTION_RATE_LIMIT)
async def remove_recipe_from_collection(
    collection_id: str,
    recipe_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a recipe from a collection."""
    collection_service = CollectionService(db)
    success = collection_service.remove_recipe_from_collection(
        collection_id, recipe_id, current_user.id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found in collection"
        )