from functools import wraps
from typing import Callable, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User, SubscriptionTier
from app.services.subscription_service import SubscriptionService

class TierLimits:
    """Define limits for each subscription tier"""
    
    FREE_TIER_LIMITS = {
        'max_recipes': 20,
        'monthly_parsing_limit': 10,
        'can_save_meal_plans': False,
        'max_meal_plan_weeks': 1,
        'has_image_ocr': False,
        'has_ai_features': False
    }
    
    PREMIUM_TIER_LIMITS = {
        'max_recipes': None,  # Unlimited
        'monthly_parsing_limit': None,  # Unlimited
        'can_save_meal_plans': True,
        'max_meal_plan_weeks': None,  # Unlimited
        'has_image_ocr': True,
        'has_ai_features': True
    }

class TierEnforcement:
    """Helper class for tier enforcement operations"""
    
    @staticmethod
    def get_user_limits(user: User) -> dict:
        """Get the limits for a user based on their subscription tier"""
        if SubscriptionService.is_premium_user(user):
            return TierLimits.PREMIUM_TIER_LIMITS
        return TierLimits.FREE_TIER_LIMITS
    
    @staticmethod
    def check_recipe_limit(user: User, db: Session) -> bool:
        """Check if user can create more recipes"""
        limits = TierEnforcement.get_user_limits(user)
        max_recipes = limits['max_recipes']
        
        if max_recipes is None:  # Unlimited
            return True
        
        # Count user's recipes
        from app.models.recipe import Recipe
        recipe_count = db.query(Recipe).filter(Recipe.user_id == user.id).count()
        
        return recipe_count < max_recipes
    
    @staticmethod
    def check_parsing_limit(user: User, db: Session) -> bool:
        """Check if user has parsing attempts remaining this month"""
        limits = TierEnforcement.get_user_limits(user)
        monthly_limit = limits['monthly_parsing_limit']
        
        if monthly_limit is None:  # Unlimited
            return True
        
        # Count parsing attempts this month
        from datetime import datetime, timedelta
        from app.models.user import User
        
        # This would require a parsing history table to track usage
        # For now, return True and implement usage tracking separately
        return True
    
    @staticmethod
    def can_save_meal_plans(user: User) -> bool:
        """Check if user can save meal plans"""
        limits = TierEnforcement.get_user_limits(user)
        return limits['can_save_meal_plans']
    
    @staticmethod
    def can_use_image_ocr(user: User) -> bool:
        """Check if user can use image OCR features"""
        limits = TierEnforcement.get_user_limits(user)
        return limits['has_image_ocr']
    
    @staticmethod
    def can_use_ai_features(user: User) -> bool:
        """Check if user can use AI features"""
        limits = TierEnforcement.get_user_limits(user)
        return limits['has_ai_features']

def require_premium(f: Callable) -> Callable:
    """Decorator to require premium subscription for an endpoint"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        # Find the current_user parameter
        current_user = kwargs.get('current_user')
        if not current_user:
            # Look for it in args (assumes it's a User object)
            for arg in args:
                if isinstance(arg, User):
                    current_user = arg
                    break
        
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to determine user authentication"
            )
        
        if not SubscriptionService.is_premium_user(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Premium subscription required for this feature"
            )
        
        return await f(*args, **kwargs)
    return decorated_function

def check_parsing_limit(f: Callable) -> Callable:
    """Decorator to check parsing limits and track usage"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        current_user = kwargs.get('current_user')
        db = kwargs.get('db')
        
        if not current_user or not db:
            # Try to find them in args
            for arg in args:
                if isinstance(arg, User):
                    current_user = arg
                elif hasattr(arg, 'query'):  # SQLAlchemy session
                    db = arg
        
        if not current_user or not db:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to determine user or database session"
            )
        
        # Import here to avoid circular imports
        from app.services.usage_tracking_service import UsageTrackingService
        
        if not UsageTrackingService.check_parsing_limit(current_user, db):
            limits = TierEnforcement.get_user_limits(current_user)
            current_usage = UsageTrackingService.get_usage_count(current_user, 'recipe_parse', db)
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Monthly parsing limit reached ({current_usage}/{limits['monthly_parsing_limit']}). Upgrade to premium for unlimited parsing."
            )
        
        # Execute the function
        result = await f(*args, **kwargs)
        
        # Track the usage after successful parsing
        UsageTrackingService.increment_usage(current_user, 'recipe_parse', db)
        
        return result
    return decorated_function

def check_recipe_limit(f: Callable) -> Callable:
    """Decorator to check recipe creation limits"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        current_user = kwargs.get('current_user')
        db = kwargs.get('db')
        
        if not current_user or not db:
            # Try to find them in args
            for arg in args:
                if isinstance(arg, User):
                    current_user = arg
                elif hasattr(arg, 'query'):  # SQLAlchemy session
                    db = arg
        
        if not current_user or not db:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to determine user or database session"
            )
        
        if not TierEnforcement.check_recipe_limit(current_user, db):
            limits = TierEnforcement.get_user_limits(current_user)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Recipe limit reached. Free tier limited to {limits['max_recipes']} recipes. Upgrade to premium for unlimited recipes."
            )
        
        return await f(*args, **kwargs)
    return decorated_function

def check_parsing_limit(f: Callable) -> Callable:
    """Decorator to check parsing limits and track usage"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        current_user = kwargs.get('current_user')
        db = kwargs.get('db')
        
        if not current_user or not db:
            # Try to find them in args
            for arg in args:
                if isinstance(arg, User):
                    current_user = arg
                elif hasattr(arg, 'query'):  # SQLAlchemy session
                    db = arg
        
        if not current_user or not db:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to determine user or database session"
            )
        
        # Import here to avoid circular imports
        from app.services.usage_tracking_service import UsageTrackingService
        
        if not UsageTrackingService.check_parsing_limit(current_user, db):
            limits = TierEnforcement.get_user_limits(current_user)
            current_usage = UsageTrackingService.get_usage_count(current_user, 'recipe_parse', db)
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Monthly parsing limit reached ({current_usage}/{limits['monthly_parsing_limit']}). Upgrade to premium for unlimited parsing."
            )
        
        # Execute the function
        result = await f(*args, **kwargs)
        
        # Track the usage after successful parsing
        UsageTrackingService.increment_usage(current_user, 'recipe_parse', db)
        
        return result
    return decorated_function

def check_meal_plan_save(f: Callable) -> Callable:
    """Decorator to check meal plan saving permissions"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        current_user = kwargs.get('current_user')
        
        if not current_user:
            for arg in args:
                if isinstance(arg, User):
                    current_user = arg
                    break
        
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to determine user authentication"
            )
        
        if not TierEnforcement.can_save_meal_plans(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Meal plan saving is a premium feature. Free tier can view 1-week plans only."
            )
        
        return await f(*args, **kwargs)
    return decorated_function

def check_parsing_limit(f: Callable) -> Callable:
    """Decorator to check parsing limits and track usage"""
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        current_user = kwargs.get('current_user')
        db = kwargs.get('db')
        
        if not current_user or not db:
            # Try to find them in args
            for arg in args:
                if isinstance(arg, User):
                    current_user = arg
                elif hasattr(arg, 'query'):  # SQLAlchemy session
                    db = arg
        
        if not current_user or not db:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to determine user or database session"
            )
        
        # Import here to avoid circular imports
        from app.services.usage_tracking_service import UsageTrackingService
        
        if not UsageTrackingService.check_parsing_limit(current_user, db):
            limits = TierEnforcement.get_user_limits(current_user)
            current_usage = UsageTrackingService.get_usage_count(current_user, 'recipe_parse', db)
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Monthly parsing limit reached ({current_usage}/{limits['monthly_parsing_limit']}). Upgrade to premium for unlimited parsing."
            )
        
        # Execute the function
        result = await f(*args, **kwargs)
        
        # Track the usage after successful parsing
        UsageTrackingService.increment_usage(current_user, 'recipe_parse', db)
        
        return result
    return decorated_function