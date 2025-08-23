from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.config import settings
from app.api.auth.auth import get_current_user
from app.models.user import User
from app.schemas.meal_plan import MealPlan as MealPlanSchema, MealPlanCreate, MealPlanUpdate, MealPlanWithRecipeDetails
from app.services.meal_plan_service import MealPlanService
from app.middleware.rate_limit import limiter
from app.core.tier_enforcement import check_meal_plan_save

router = APIRouter()

@router.get("/", response_model=List[MealPlanSchema])
async def get_meal_plans(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meal_plan_service = MealPlanService(db)
    return meal_plan_service.get_user_meal_plans(
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )

@router.post("/", response_model=MealPlanSchema)
@limiter.limit(settings.RECIPE_RATE_LIMIT)
@check_meal_plan_save
async def create_meal_plan(
    meal_plan: MealPlanCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meal_plan_service = MealPlanService(db)
    return meal_plan_service.create_meal_plan(meal_plan, current_user.id)

@router.get("/active", response_model=MealPlanWithRecipeDetails)
async def get_active_meal_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meal_plan_service = MealPlanService(db)
    active_meal_plan = meal_plan_service.get_active_meal_plan(current_user.id)
    if not active_meal_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active meal plan found"
        )
    return active_meal_plan

@router.get("/{meal_plan_id}", response_model=MealPlanSchema)
async def get_meal_plan(
    meal_plan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meal_plan_service = MealPlanService(db)
    meal_plan = meal_plan_service.get_meal_plan(meal_plan_id, current_user.id)
    if not meal_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal plan not found"
        )
    return meal_plan

@router.put("/{meal_plan_id}", response_model=MealPlanSchema)
@limiter.limit(settings.RECIPE_RATE_LIMIT)
async def update_meal_plan(
    meal_plan_id: str,
    meal_plan_update: MealPlanUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meal_plan_service = MealPlanService(db)
    meal_plan = meal_plan_service.update_meal_plan(meal_plan_id, meal_plan_update, current_user.id)
    if not meal_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal plan not found"
        )
    return meal_plan

@router.delete("/{meal_plan_id}")
@limiter.limit(settings.RECIPE_RATE_LIMIT)
async def delete_meal_plan(
    meal_plan_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meal_plan_service = MealPlanService(db)
    success = meal_plan_service.delete_meal_plan(meal_plan_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal plan not found"
        )
    return {"message": "Meal plan deleted successfully"}

@router.put("/{meal_plan_id}/set-active", response_model=MealPlanSchema)
@limiter.limit(settings.RECIPE_RATE_LIMIT)
async def set_active_meal_plan(
    meal_plan_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meal_plan_service = MealPlanService(db)
    meal_plan = meal_plan_service.set_active_meal_plan(meal_plan_id, current_user.id)
    if not meal_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal plan not found"
        )
    return meal_plan