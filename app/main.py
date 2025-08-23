from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.core.database import engine
from app.core.startup import startup_event
from app.models import Base
from app.api.auth import auth_router
from app.api.recipes import recipes_router
from app.api.meal_plans import meal_plans_router
from app.api.users import users_router
from app.api.parsing import parsing_router
from app.api.collections import collections_router
from app.api.subscriptions.subscriptions import router as subscriptions_router
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler, create_rate_limit_middleware
from app.middleware.request_limits import create_request_limit_middleware

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="HomeChef Companion API",
    description="Backend API for Recipe Management PWA",
    version="1.0.0"
)

# Configure rate limiting
if settings.RATE_LIMIT_ENABLED:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Add startup event handler
app.add_event_handler("startup", startup_event)

# Add security headers middleware (should be added before CORS)
app.add_middleware(SecurityHeadersMiddleware)

# Add request size limiting middleware
app.add_middleware(create_request_limit_middleware())

# Add rate limiting middleware if enabled
rate_limit_middleware = create_rate_limit_middleware()
if rate_limit_middleware:
    app.add_middleware(rate_limit_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(recipes_router, prefix="/api/recipes", tags=["recipes"])
app.include_router(meal_plans_router, prefix="/api/meal-plans", tags=["meal-plans"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(parsing_router, prefix="/api/parse", tags=["parsing"])
app.include_router(collections_router, prefix="/api/collections", tags=["collections"])
app.include_router(subscriptions_router, prefix="/api/subscriptions", tags=["subscriptions"])

# Mount static files for media serving
import os
media_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media")
if os.path.exists(media_dir):
    app.mount("/media", StaticFiles(directory=media_dir), name="media")

@app.get("/")
async def root():
    return {"message": "HomeChef Companion API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}