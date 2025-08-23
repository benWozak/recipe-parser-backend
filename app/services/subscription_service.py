import stripe
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from app.core.config import settings
from app.models.user import User, SubscriptionTier
from app.schemas.user import UserSubscriptionUpdate

logger = logging.getLogger(__name__)

# Initialize Stripe with secret key
stripe.api_key = settings.STRIPE_SECRET_KEY

class SubscriptionService:
    """Service for managing Stripe subscriptions and user tiers"""
    
    @staticmethod
    def create_customer(user: User) -> Optional[str]:
        """Create a Stripe customer for a user"""
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name,
                metadata={
                    'user_id': user.id,
                    'clerk_user_id': user.clerk_user_id
                }
            )
            logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
            return customer.id
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer for user {user.id}: {str(e)}")
            return None

    @staticmethod
    def create_checkout_session(user: User, db: Session) -> Optional[str]:
        """Create a Stripe checkout session for premium subscription"""
        try:
            # Create customer if they don't have one
            if not user.stripe_customer_id:
                customer_id = SubscriptionService.create_customer(user)
                if not customer_id:
                    return None
                user.stripe_customer_id = customer_id
                db.commit()
            
            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=user.stripe_customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': settings.STRIPE_PRICE_ID_PREMIUM,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=f"{settings.ALLOWED_ORIGINS[0]}/subscription/success",
                cancel_url=f"{settings.ALLOWED_ORIGINS[0]}/subscription/cancel",
                metadata={
                    'user_id': user.id,
                }
            )
            
            logger.info(f"Created checkout session {session.id} for user {user.id}")
            return session.url
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session for user {user.id}: {str(e)}")
            return None

    @staticmethod
    def create_billing_portal_session(user: User) -> Optional[str]:
        """Create a Stripe billing portal session for subscription management"""
        if not user.stripe_customer_id:
            logger.warning(f"User {user.id} has no Stripe customer ID")
            return None
        
        try:
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=f"{settings.ALLOWED_ORIGINS[0]}/profile"
            )
            
            logger.info(f"Created billing portal session for user {user.id}")
            return session.url
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create billing portal session for user {user.id}: {str(e)}")
            return None

    @staticmethod
    def update_user_subscription(
        user: User, 
        subscription_data: Dict[str, Any], 
        db: Session
    ) -> bool:
        """Update user subscription based on Stripe webhook data"""
        try:
            subscription_id = subscription_data.get('id')
            status = subscription_data.get('status')
            current_period_end = subscription_data.get('current_period_end')
            
            # Convert timestamp to datetime
            period_end_dt = None
            if current_period_end:
                period_end_dt = datetime.fromtimestamp(current_period_end)
            
            # Determine subscription tier based on status
            if status in ['active', 'trialing']:
                tier = SubscriptionTier.PREMIUM
            else:
                tier = SubscriptionTier.FREE
            
            # Update user
            user.stripe_subscription_id = subscription_id
            user.subscription_status = status
            user.subscription_tier = tier
            user.current_period_end = period_end_dt
            
            db.commit()
            
            logger.info(f"Updated subscription for user {user.id}: tier={tier.value}, status={status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update subscription for user {user.id}: {str(e)}")
            db.rollback()
            return False

    @staticmethod
    def handle_subscription_deleted(subscription_data: Dict[str, Any], db: Session) -> bool:
        """Handle subscription deletion webhook"""
        try:
            subscription_id = subscription_data.get('id')
            customer_id = subscription_data.get('customer')
            
            # Find user by customer ID or subscription ID
            user = db.query(User).filter(
                (User.stripe_customer_id == customer_id) |
                (User.stripe_subscription_id == subscription_id)
            ).first()
            
            if not user:
                logger.warning(f"No user found for deleted subscription {subscription_id}")
                return False
            
            # Downgrade to free tier
            user.subscription_tier = SubscriptionTier.FREE
            user.subscription_status = 'cancelled'
            user.stripe_subscription_id = None
            user.current_period_end = None
            
            db.commit()
            
            logger.info(f"Handled subscription deletion for user {user.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle subscription deletion: {str(e)}")
            db.rollback()
            return False

    @staticmethod
    def is_premium_user(user: User) -> bool:
        """Check if user has premium access"""
        return user.subscription_tier == SubscriptionTier.PREMIUM

    @staticmethod
    def get_subscription_info(user: User) -> Dict[str, Any]:
        """Get subscription information for a user"""
        return {
            'tier': user.subscription_tier.value,
            'status': user.subscription_status,
            'current_period_end': user.current_period_end,
            'has_stripe_subscription': bool(user.stripe_subscription_id),
            'is_premium': SubscriptionService.is_premium_user(user)
        }