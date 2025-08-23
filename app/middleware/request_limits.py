from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Callable
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to limit request size and implement basic DoS protection.
    """
    
    def __init__(self, app, max_request_size: int = None):
        super().__init__(app)
        self.max_request_size = max_request_size or settings.MAX_REQUEST_SIZE
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check Content-Length header if present
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                content_length = int(content_length)
                if content_length > self.max_request_size:
                    logger.warning(
                        f"Request size limit exceeded: {content_length} bytes "
                        f"from IP {request.client.host if request.client else 'unknown'}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Request size too large. Maximum allowed: {self.max_request_size} bytes"
                    )
            except ValueError:
                # Invalid Content-Length header
                pass
        
        # Special handling for file upload endpoints
        if request.url.path.endswith("/image") and request.method == "POST":
            # Use file upload size limit for image uploads
            max_size = settings.MAX_UPLOAD_SIZE
            if content_length and int(content_length) > max_size:
                logger.warning(
                    f"File upload size limit exceeded: {content_length} bytes "
                    f"from IP {request.client.host if request.client else 'unknown'}"
                )
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Maximum allowed: {max_size} bytes"
                )
        
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # Log any unexpected errors for monitoring
            logger.error(f"Request processing error: {str(e)}")
            raise

def create_request_limit_middleware():
    """
    Create the request size limit middleware.
    """
    logger.info(f"Request size limiting enabled with max size: {settings.MAX_REQUEST_SIZE} bytes")
    return RequestSizeLimitMiddleware