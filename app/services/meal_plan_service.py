from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from typing import List, Optional
from app.models.meal_plan import MealPlan, MealPlanEntry
from app.schemas.meal_plan import MealPlanCreate, MealPlanUpdate

class MealPlanService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_meal_plans(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[MealPlan]:
        return self.db.query(MealPlan).filter(
            MealPlan.user_id == user_id
        ).offset(skip).limit(limit).all()

    def get_meal_plan(self, meal_plan_id: str, user_id: str) -> Optional[MealPlan]:
        return self.db.query(MealPlan).filter(
            and_(MealPlan.id == meal_plan_id, MealPlan.user_id == user_id)
        ).first()

    def create_meal_plan(self, meal_plan_data: MealPlanCreate, user_id: str) -> MealPlan:
        meal_plan_dict = meal_plan_data.dict(exclude={'entries'})
        meal_plan = MealPlan(**meal_plan_dict, user_id=user_id)
        
        self.db.add(meal_plan)
        self.db.flush()

        for entry_data in meal_plan_data.entries:
            entry = MealPlanEntry(**entry_data.dict(), meal_plan_id=meal_plan.id)
            self.db.add(entry)

        self.db.commit()
        self.db.refresh(meal_plan)
        return meal_plan

    def update_meal_plan(
        self,
        meal_plan_id: str,
        meal_plan_update: MealPlanUpdate,
        user_id: str
    ) -> Optional[MealPlan]:
        meal_plan = self.get_meal_plan(meal_plan_id, user_id)
        if not meal_plan:
            return None

        update_data = meal_plan_update.dict(exclude_unset=True, exclude={'entries'})
        for field, value in update_data.items():
            setattr(meal_plan, field, value)

        if meal_plan_update.entries is not None:
            for entry in meal_plan.entries:
                self.db.delete(entry)
            
            for entry_data in meal_plan_update.entries:
                entry = MealPlanEntry(**entry_data.dict(), meal_plan_id=meal_plan.id)
                self.db.add(entry)

        self.db.commit()
        self.db.refresh(meal_plan)
        return meal_plan

    def delete_meal_plan(self, meal_plan_id: str, user_id: str) -> bool:
        meal_plan = self.get_meal_plan(meal_plan_id, user_id)
        if not meal_plan:
            return False
        
        self.db.delete(meal_plan)
        self.db.commit()
        return True

    def get_active_meal_plan(self, user_id: str) -> Optional[MealPlan]:
        """Get the user's currently active meal plan with recipe details."""
        return self.db.query(MealPlan).options(
            joinedload(MealPlan.entries).joinedload(MealPlanEntry.recipe)
        ).filter(
            and_(MealPlan.user_id == user_id, MealPlan.is_active == True)
        ).first()

    def set_active_meal_plan(self, meal_plan_id: str, user_id: str) -> Optional[MealPlan]:
        """Set a meal plan as active, deactivating any previously active meal plan."""
        # First verify the meal plan exists and belongs to the user
        meal_plan = self.get_meal_plan(meal_plan_id, user_id)
        if not meal_plan:
            return None

        # Deactivate any currently active meal plan for this user
        current_active = self.get_active_meal_plan(user_id)
        if current_active and current_active.id != meal_plan_id:
            current_active.is_active = False

        # Set the new meal plan as active
        meal_plan.is_active = True
        
        self.db.commit()
        self.db.refresh(meal_plan)
        return meal_plan