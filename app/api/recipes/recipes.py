from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.core.config import settings
from app.api.auth.auth import get_current_user
from app.models.user import User
from app.models.recipe import Recipe, Tag
from app.schemas.recipe import Recipe as RecipeSchema, RecipeCreate, RecipeUpdate
from app.services.recipe_service import RecipeService
from app.middleware.rate_limit import limiter
from app.core.tier_enforcement import check_recipe_limit

router = APIRouter()

@router.get("/", response_model=List[RecipeSchema])
async def get_recipes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    search: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),
    collection_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recipe_service = RecipeService(db)
    return recipe_service.get_user_recipes(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
        search=search,
        tags=tags.split(",") if tags else None,
        collection_id=collection_id
    )

@router.post("/", response_model=RecipeSchema)
@limiter.limit(settings.RECIPE_RATE_LIMIT)
@check_recipe_limit
async def create_recipe(
    recipe: RecipeCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recipe_service = RecipeService(db)
    return recipe_service.create_recipe(recipe, current_user.id)

@router.get("/{recipe_id}", response_model=RecipeSchema)
async def get_recipe(
    recipe_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recipe_service = RecipeService(db)
    recipe = recipe_service.get_recipe(recipe_id, current_user.id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )
    return recipe

@router.put("/{recipe_id}", response_model=RecipeSchema)
@limiter.limit(settings.RECIPE_RATE_LIMIT)
async def update_recipe(
    recipe_id: str,
    recipe_update: RecipeUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recipe_service = RecipeService(db)
    recipe = recipe_service.update_recipe(recipe_id, recipe_update, current_user.id)
    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )
    return recipe

@router.delete("/{recipe_id}")
@limiter.limit(settings.RECIPE_RATE_LIMIT)
async def delete_recipe(
    recipe_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    recipe_service = RecipeService(db)
    success = recipe_service.delete_recipe(recipe_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found"
        )
    return {"message": "Recipe deleted successfully"}