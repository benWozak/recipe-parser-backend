from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from app.models.user import SubscriptionTier

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None

class UserCreate(UserBase):
    clerk_user_id: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None

class UserSubscriptionUpdate(BaseModel):
    subscription_tier: Optional[SubscriptionTier] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    subscription_status: Optional[str] = None
    current_period_end: Optional[datetime] = None

class User(UserBase):
    id: str
    clerk_user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Subscription fields
    subscription_tier: SubscriptionTier
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    subscription_status: Optional[str] = None
    current_period_end: Optional[datetime] = None

    class Config:
        from_attributes = True