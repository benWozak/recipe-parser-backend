from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import stripe
import json
import hmac
import hashlib
import logging

from app.core.database import get_db
from app.core.config import settings
from app.api.auth.auth import get_current_user
from app.models.user import User
from app.services.subscription_service import SubscriptionService
from app.services.usage_tracking_service import UsageTrackingService
from app.middleware.rate_limit import limiter

router = APIRouter()
logger = logging.getLogger(__name__)

def verify_stripe_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Stripe webhook signature"""
    if not signature or not secret:
        return False
    
    try:
        # Stripe uses HMAC-SHA256 with hex encoding
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Stripe signature format: "t=timestamp,v1=signature"
        sig_elements = signature.split(',')
        sig_hash = None
        
        for element in sig_elements:
            if element.startswith('v1='):
                sig_hash = element[3:]
                break
        
        if not sig_hash:
            return False
            
        return hmac.compare_digest(expected_signature, sig_hash)
    except Exception as e:
        logger.error(f"Error verifying Stripe signature: {str(e)}")
        return False

@router.post("/webhook")
@limiter.limit("10/minute")  # Rate limit webhook endpoint
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events"""
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    
    if not signature:
        logger.warning("Stripe webhook received without signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature"
        )
    
    if not settings.STRIPE_SECRET_KEY:
        logger.error("STRIPE_SECRET_KEY not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured"
        )
    
    if not verify_stripe_signature(payload, signature, settings.STRIPE_SECRET_KEY):
        logger.warning("Invalid Stripe webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )
    
    try:
        event = json.loads(payload)
        event_type = event.get('type')
        data = event.get('data', {}).get('object', {})
        
        logger.info(f"Processing Stripe webhook: {event_type}")
        
        if event_type == 'customer.subscription.created':
            await handle_subscription_created(data, db)
        elif event_type == 'customer.subscription.updated':
            await handle_subscription_updated(data, db)
        elif event_type == 'customer.subscription.deleted':
            await handle_subscription_deleted(data, db)
        elif event_type == 'invoice.payment_succeeded':
            await handle_payment_succeeded(data, db)
        elif event_type == 'invoice.payment_failed':
            await handle_payment_failed(data, db)
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
        
        return {"status": "success"}
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in Stripe webhook payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON"
        )
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )

async def handle_subscription_created(subscription_data: dict, db: Session):
    """Handle subscription creation"""
    customer_id = subscription_data.get('customer')
    
    # Find user by customer ID
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        logger.warning(f"No user found for customer {customer_id}")
        return
    
    success = SubscriptionService.update_user_subscription(user, subscription_data, db)
    if success:
        logger.info(f"Successfully created subscription for user {user.id}")
    else:
        logger.error(f"Failed to create subscription for user {user.id}")

async def handle_subscription_updated(subscription_data: dict, db: Session):
    """Handle subscription updates"""
    customer_id = subscription_data.get('customer')
    subscription_id = subscription_data.get('id')
    
    # Find user by customer ID or subscription ID
    user = db.query(User).filter(
        (User.stripe_customer_id == customer_id) |
        (User.stripe_subscription_id == subscription_id)
    ).first()
    
    if not user:
        logger.warning(f"No user found for subscription {subscription_id}")
        return
    
    success = SubscriptionService.update_user_subscription(user, subscription_data, db)
    if success:
        logger.info(f"Successfully updated subscription for user {user.id}")
    else:
        logger.error(f"Failed to update subscription for user {user.id}")

async def handle_subscription_deleted(subscription_data: dict, db: Session):
    """Handle subscription deletion"""
    success = SubscriptionService.handle_subscription_deleted(subscription_data, db)
    if success:
        logger.info("Successfully handled subscription deletion")
    else:
        logger.error("Failed to handle subscription deletion")

async def handle_payment_succeeded(invoice_data: dict, db: Session):
    """Handle successful payment"""
    customer_id = invoice_data.get('customer')
    subscription_id = invoice_data.get('subscription')
    
    if not subscription_id:
        return  # Not a subscription payment
    
    # Find user and ensure they have active premium status
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        logger.warning(f"No user found for payment success webhook, customer {customer_id}")
        return
    
    # Refresh subscription data from Stripe to ensure we have latest info
    try:
        subscription = stripe.Subscription.retrieve(subscription_id)
        SubscriptionService.update_user_subscription(user, subscription, db)
        logger.info(f"Payment succeeded for user {user.id}, subscription refreshed")
    except stripe.error.StripeError as e:
        logger.error(f"Failed to retrieve subscription {subscription_id}: {str(e)}")

async def handle_payment_failed(invoice_data: dict, db: Session):
    """Handle failed payment"""
    customer_id = invoice_data.get('customer')
    subscription_id = invoice_data.get('subscription')
    
    if not subscription_id:
        return  # Not a subscription payment
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        logger.warning(f"No user found for payment failed webhook, customer {customer_id}")
        return
    
    logger.warning(f"Payment failed for user {user.id}, subscription {subscription_id}")
    
    # The subscription status will be updated via subscription.updated webhook
    # We just log the payment failure here

@router.post("/create-checkout-session")
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def create_checkout_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a Stripe checkout session for premium subscription"""
    
    # Check if user already has premium
    if SubscriptionService.is_premium_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has premium subscription"
        )
    
    checkout_url = SubscriptionService.create_checkout_session(current_user, db)
    if not checkout_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )
    
    return {"checkout_url": checkout_url}

@router.post("/create-portal-session")
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def create_portal_session(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Create a Stripe billing portal session"""
    
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no Stripe customer account"
        )
    
    portal_url = SubscriptionService.create_billing_portal_session(current_user)
    if not portal_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create billing portal session"
        )
    
    return {"portal_url": portal_url}

@router.get("/status")
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def get_subscription_status(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Get current user's subscription status"""
    return SubscriptionService.get_subscription_info(current_user)

@router.get("/usage")
@limiter.limit(settings.DEFAULT_RATE_LIMIT)
async def get_usage_stats(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's usage statistics and limits"""
    return UsageTrackingService.get_user_usage_summary(current_user, db)