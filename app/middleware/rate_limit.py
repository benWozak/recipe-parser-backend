from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def get_rate_limit_key(request: Request) -> str:
    """
    Generate rate limit key based on client IP address.
    In the future, this could be enhanced to use user ID for authenticated requests.
    """
    return get_remote_address(request)

# Initialize the rate limiter with in-memory storage (default)
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[settings.DEFAULT_RATE_LIMIT] if settings.RATE_LIMIT_ENABLED else []
)

def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom handler for rate limit exceeded errors.
    Returns a structured JSON response without revealing internal details.
    """
    logger.warning(
        f"Rate limit exceeded for IP: {get_remote_address(request)}, "
        f"Path: {request.url.path}, "
        f"Method: {request.method}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "Rate limit exceeded",
            "message": "Too many requests. Please try again later.",
            "retry_after": exc.retry_after if hasattr(exc, 'retry_after') else 60
        },
        headers={"Retry-After": str(exc.retry_after if hasattr(exc, 'retry_after') else 60)}
    )

def create_rate_limit_middleware():
    """
    Create and configure the SlowAPI middleware.
    Only adds middleware if rate limiting is enabled in settings.
    """
    if not settings.RATE_LIMIT_ENABLED:
        logger.info("Rate limiting is disabled in settings")
        return None
    
    logger.info("Rate limiting middleware enabled with in-memory storage")
    return SlowAPIMiddleware