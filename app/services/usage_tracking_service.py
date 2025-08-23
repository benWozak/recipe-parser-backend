from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Optional
import logging

from app.models.user import User
from app.models.usage_tracking import UsageTracking
from app.core.tier_enforcement import TierEnforcement

logger = logging.getLogger(__name__)

class UsageTrackingService:
    """Service for tracking and enforcing usage limits"""
    
    @staticmethod
    def get_current_month_key() -> str:
        """Get the current month key in YYYY-MM format"""
        return datetime.now().strftime("%Y-%m")
    
    @staticmethod
    def increment_usage(user: User, action_type: str, db: Session) -> bool:
        """Increment usage counter for a user action"""
        try:
            month_key = UsageTrackingService.get_current_month_key()
            
            # Find or create usage record
            usage_record = db.query(UsageTracking).filter(
                UsageTracking.user_id == user.id,
                UsageTracking.action_type == action_type,
                UsageTracking.month_year == month_key
            ).first()
            
            if usage_record:
                usage_record.count += 1
            else:
                usage_record = UsageTracking(
                    user_id=user.id,
                    action_type=action_type,
                    month_year=month_key,
                    count=1
                )
                db.add(usage_record)
            
            db.commit()
            logger.info(f"Incremented {action_type} usage for user {user.id}, new count: {usage_record.count}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to increment usage for user {user.id}, action {action_type}: {str(e)}")
            db.rollback()
            return False
    
    @staticmethod
    def get_usage_count(user: User, action_type: str, db: Session) -> int:
        """Get current month usage count for a user action"""
        month_key = UsageTrackingService.get_current_month_key()
        
        usage_record = db.query(UsageTracking).filter(
            UsageTracking.user_id == user.id,
            UsageTracking.action_type == action_type,
            UsageTracking.month_year == month_key
        ).first()
        
        return usage_record.count if usage_record else 0
    
    @staticmethod
    def check_parsing_limit(user: User, db: Session) -> bool:
        """Check if user has parsing attempts remaining this month"""
        limits = TierEnforcement.get_user_limits(user)
        monthly_limit = limits['monthly_parsing_limit']
        
        if monthly_limit is None:  # Unlimited for premium
            return True
        
        current_usage = UsageTrackingService.get_usage_count(user, 'recipe_parse', db)
        return current_usage < monthly_limit
    
    @staticmethod
    def get_user_usage_summary(user: User, db: Session) -> Dict[str, Dict]:
        """Get usage summary for a user"""
        month_key = UsageTrackingService.get_current_month_key()
        limits = TierEnforcement.get_user_limits(user)
        
        # Get current usage counts
        parsing_usage = UsageTrackingService.get_usage_count(user, 'recipe_parse', db)
        ocr_usage = UsageTrackingService.get_usage_count(user, 'image_ocr', db)
        
        # Count total recipes
        from app.models.recipe import Recipe
        recipe_count = db.query(Recipe).filter(Recipe.user_id == user.id).count()
        
        return {
            'recipes': {
                'current': recipe_count,
                'limit': limits['max_recipes'],
                'unlimited': limits['max_recipes'] is None
            },
            'parsing': {
                'current': parsing_usage,
                'limit': limits['monthly_parsing_limit'],
                'unlimited': limits['monthly_parsing_limit'] is None,
                'month': month_key
            },
            'image_ocr': {
                'current': ocr_usage,
                'available': limits['has_image_ocr']
            },
            'meal_plans': {
                'can_save': limits['can_save_meal_plans'],
                'max_weeks': limits['max_meal_plan_weeks']
            },
            'ai_features': {
                'available': limits['has_ai_features']
            }
        }