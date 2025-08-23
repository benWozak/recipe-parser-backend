from sqlalchemy import Column, String, Date, DateTime, ForeignKey, Integer, Boolean
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.utils.id_utils import generate_id

meal_type_enum = ENUM('breakfast', 'lunch', 'dinner', 'snack', name='meal_type_enum', create_type=True)

class MealPlan(Base):
    __tablename__ = "meal_plans"

    id = Column(String, primary_key=True, default=generate_id)
    user_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    name = Column(String, nullable=False)
    start_date = Column(Date)
    end_date = Column(Date)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    entries = relationship("MealPlanEntry", back_populates="meal_plan", cascade="all, delete-orphan")

class MealPlanEntry(Base):
    __tablename__ = "meal_plan_entries"

    id = Column(String, primary_key=True, default=generate_id)
    meal_plan_id = Column(String, ForeignKey('meal_plans.id', ondelete='CASCADE'), nullable=False)
    recipe_id = Column(String, ForeignKey('recipes.id'), nullable=False)
    date = Column(Date)
    meal_type = Column(meal_type_enum)
    servings = Column(Integer, default=1)

    meal_plan = relationship("MealPlan", back_populates="entries")
    recipe = relationship("Recipe")