from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Union

class Settings(BaseSettings):
    # Application Secret Key - must be set via environment variable
    SECRET_KEY: str = ""
    
    # Database Configuration - must be set via environment variable
    DATABASE_URL: str = ""
    
    # Clerk Authentication Settings - must be set via environment variables
    CLERK_SECRET_KEY: str = ""
    CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_WEBHOOK_SECRET: str = ""
    CLERK_ISSUER: str = ""
    
    # CORS Configuration - must be set via environment variable
    ALLOWED_ORIGINS: Union[List[str], str] = []
    
    # Production domains (add your production URLs here)
    PRODUCTION_ORIGINS: Union[List[str], str] = []
    
    # External API Keys
    GOOGLE_CLOUD_VISION_CREDENTIALS: str = ""
    OPENAI_API_KEY: str = ""
    
    # Stripe Configuration
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PRICE_ID_PREMIUM: str = ""  # Price ID for premium subscription
    
    # JWT Validation Settings
    JWT_CLOCK_SKEW_TOLERANCE_SECONDS: int = 5
    
    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED: bool = True
    
    # Default rate limits (requests per minute)
    DEFAULT_RATE_LIMIT: str = "100/minute"
    
    # Critical endpoint rate limits (more restrictive)
    AUTH_RATE_LIMIT: str = "10/minute"
    PARSING_RATE_LIMIT: str = "5/minute"
    FILE_UPLOAD_RATE_LIMIT: str = "3/minute"
    INSTAGRAM_BATCH_RATE_LIMIT: str = "2/hour"
    
    # Standard endpoint rate limits
    RECIPE_RATE_LIMIT: str = "60/minute"
    COLLECTION_RATE_LIMIT: str = "30/minute"
    USER_RATE_LIMIT: str = "20/minute"
    
    # Request size limits (in bytes)
    MAX_REQUEST_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024   # 10MB
    
    # File Upload Security Settings
    MIN_FILE_SECURITY_SCORE: int = 70  # Minimum security score (0-100) for file uploads
    MAX_FILE_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB max per file
    ALLOWED_IMAGE_FORMATS: List[str] = ["JPEG", "PNG", "WebP", "GIF"]
    MAX_IMAGE_DIMENSIONS: tuple = (4096, 4096)  # 4K max resolution
    
    # Security Logging
    SECURITY_LOG_LEVEL: str = "INFO"
    LOG_SECURITY_EVENTS: bool = True
    LOG_FILE_UPLOADS: bool = True
    
    @field_validator('ALLOWED_ORIGINS', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    @field_validator('PRODUCTION_ORIGINS', mode='before')
    @classmethod
    def parse_production_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',')]
        return v
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra environment variables

settings = Settings()