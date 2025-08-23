from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_clerk_token
from app.core.config import settings
from app.models.user import User
from app.schemas.user import User as UserSchema
from app.middleware.rate_limit import limiter
import json
import hmac
import hashlib
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Clerk webhook signature"""
    if not signature or not secret:
        return False
    
    # Clerk uses HMAC-SHA256 with hex encoding
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Remove 'sha256=' prefix if present
    if signature.startswith('sha256='):
        signature = signature[7:]
    
    return hmac.compare_digest(expected_signature, signature)

def create_user_from_data(user_data: dict, db: Session) -> User:
    """Create a new user from Clerk user data"""
    email = user_data.get("email_addresses", [{}])[0].get("email_address")
    name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
    
    if not user_data.get("id"):
        raise ValueError("User ID is required")
    
    user = User(
        clerk_user_id=user_data.get("id"),
        email=email,
        name=name or None
    )
    db.add(user)
    return user

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    authorization: str = request.headers.get("Authorization")
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    try:
        # Parse authorization header
        auth_parts = authorization.split()
        if len(auth_parts) != 2:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header format",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        scheme, token = auth_parts
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Verify token with Clerk
        clerk_data = await verify_clerk_token(token)
        clerk_user_id = clerk_data.get("user_id")
        
        # Get or create user in database
        user = db.query(User).filter(User.clerk_user_id == clerk_user_id).first()
        if not user:
            # Auto-create user if they don't exist
            payload = clerk_data.get("payload", {})
            
            # Extract user info from verified JWT claims
            email = payload.get("email") or payload.get("email_addresses", [{}])[0].get("email_address")
            if not email:
                email = f"{clerk_user_id}@clerk.local"  # Fallback email
            
            # Extract name from various possible claim locations
            name = (payload.get("name") or 
                   payload.get("full_name") or 
                   f"{payload.get('given_name', '')} {payload.get('family_name', '')}".strip() or
                   "Unknown User")
            
            user = User(
                clerk_user_id=clerk_user_id,
                email=email,
                name=name
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        return user
    
    except HTTPException:
        # Re-raise HTTP exceptions from token validation
        raise
    except Exception as e:
        # Log unexpected errors but don't expose details
        logger.error(f"Unexpected authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"}
        )

@router.post("/webhook")
@limiter.limit(settings.AUTH_RATE_LIMIT)
async def clerk_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    
    # Verify webhook signature
    signature = request.headers.get("clerk-signature") or request.headers.get("svix-signature")
    if not signature:
        logger.warning("Webhook received without signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature"
        )
    
    if not settings.CLERK_WEBHOOK_SECRET:
        logger.error("CLERK_WEBHOOK_SECRET not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured"
        )
    
    if not verify_webhook_signature(payload, signature, settings.CLERK_WEBHOOK_SECRET):
        logger.warning("Invalid webhook signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )
    
    try:
        data = json.loads(payload)
        event_type = data.get("type")
        user_data = data.get("data")
        
        if not event_type or not user_data:
            logger.warning("Invalid webhook payload structure")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payload structure"
            )
        
        try:
            if event_type == "user.created":
                user = create_user_from_data(user_data, db)
                db.commit()
                logger.info(f"Created user via webhook: {user.clerk_user_id}")
                
            elif event_type == "user.updated":
                user = db.query(User).filter(User.clerk_user_id == user_data.get("id")).first()
                if user:
                    email = user_data.get("email_addresses", [{}])[0].get("email_address")
                    name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
                    
                    user.email = email
                    user.name = name or None
                    db.commit()
                    logger.info(f"Updated user via webhook: {user.clerk_user_id}")
                else:
                    logger.warning(f"User not found for update: {user_data.get('id')}")
            
            elif event_type == "user.deleted":
                # Optional: Handle user deletion
                user = db.query(User).filter(User.clerk_user_id == user_data.get("id")).first()
                if user:
                    db.delete(user)
                    db.commit()
                    logger.info(f"Deleted user via webhook: {user.clerk_user_id}")
        
        except Exception as e:
            db.rollback()
            logger.error(f"Database error processing webhook: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error"
            )
        
        return {"status": "success"}
    
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in webhook payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected webhook error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )

@router.get("/me", response_model=UserSchema)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user