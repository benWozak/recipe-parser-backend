"""
Startup validation and checks for the HomeChef Companion backend
"""

import logging
import sys
from typing import List, Tuple
from app.core.config import settings

logger = logging.getLogger(__name__)

class StartupValidationError(Exception):
    """Raised when startup validation fails"""
    pass

def validate_secret_key() -> Tuple[bool, List[str]]:
    """
    Validate the SECRET_KEY configuration
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    
    # Check if key exists
    if not settings.SECRET_KEY:
        issues.append("SECRET_KEY is not set")
        return False, issues
    
    # Check for default values
    default_values = [
        "your-secret-key-here",
        "your-secret-key-here-generate-a-strong-random-key",
        "your-secret-key-here-use-generate_secret_key.py-script"
    ]
    
    if settings.SECRET_KEY in default_values:
        issues.append("SECRET_KEY is using a default value. Please generate a secure key.")
        return False, issues
    
    # Check minimum length (32 bytes = 256 bits)
    min_length = 32
    if len(settings.SECRET_KEY.encode('utf-8')) < min_length:
        issues.append(f"SECRET_KEY is too short. Minimum {min_length} bytes required.")
    
    # Check for weak patterns
    weak_patterns = ['password', 'secret', 'key', '123', 'abc', 'test']
    if any(pattern in settings.SECRET_KEY.lower() for pattern in weak_patterns):
        issues.append("SECRET_KEY contains weak patterns. Please generate a new key.")
    
    return len(issues) == 0, issues

def validate_database_url() -> Tuple[bool, List[str]]:
    """
    Validate the DATABASE_URL configuration
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    
    if not settings.DATABASE_URL:
        issues.append("DATABASE_URL is not set")
        return False, issues
    
    # Check for default/placeholder values
    if "localhost" in settings.DATABASE_URL and "recipecatalogue" in settings.DATABASE_URL:
        if settings.DATABASE_URL == "postgresql://user:password@localhost/recipecatalogue":
            issues.append("DATABASE_URL is using default placeholder values")
    
    # Ensure SSL for production databases
    if "neon.tech" in settings.DATABASE_URL and "sslmode=require" not in settings.DATABASE_URL:
        issues.append("Neon Postgres requires SSL. Add '?sslmode=require' to DATABASE_URL")
    
    return len(issues) == 0, issues

def validate_cors_origins() -> Tuple[bool, List[str]]:
    """
    Validate CORS origins configuration
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    warnings = []
    
    if not settings.ALLOWED_ORIGINS:
        issues.append("ALLOWED_ORIGINS is not set")
        return False, issues
    
    # Check for localhost-only in what might be production
    if all("localhost" in origin for origin in settings.ALLOWED_ORIGINS):
        warnings.append("All CORS origins are localhost. Update for production deployment.")
    
    # Note: warnings don't fail validation, just log them
    if warnings:
        logger.warning("CORS validation warnings: %s", "; ".join(warnings))
    
    return True, issues

def validate_authentication() -> Tuple[bool, List[str]]:
    """
    Validate authentication configuration
    
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []
    warnings = []
    
    # Check Clerk configuration
    if not settings.CLERK_SECRET_KEY or settings.CLERK_SECRET_KEY.startswith("sk_test_your_clerk"):
        warnings.append("CLERK_SECRET_KEY needs to be configured for authentication to work")
    
    if not settings.CLERK_PUBLISHABLE_KEY or settings.CLERK_PUBLISHABLE_KEY.startswith("pk_test_your_clerk"):
        warnings.append("CLERK_PUBLISHABLE_KEY needs to be configured for frontend integration")
    
    # Note: These are warnings for now since the app can start without Clerk
    if warnings:
        logger.warning("Authentication configuration warnings: %s", "; ".join(warnings))
    
    return True, issues

def perform_startup_validation(strict: bool = False) -> bool:
    """
    Perform all startup validations
    
    Args:
        strict: If True, warnings are treated as errors
        
    Returns:
        True if all validations pass, False otherwise
        
    Raises:
        StartupValidationError: If critical validations fail
    """
    logger.info("Starting application validation...")
    
    all_issues = []
    all_warnings = []
    
    validations = [
        ("Secret Key", validate_secret_key),
        ("Database URL", validate_database_url),
        ("CORS Origins", validate_cors_origins),
        ("Authentication", validate_authentication),
    ]
    
    for name, validator in validations:
        try:
            is_valid, issues = validator()
            if not is_valid:
                logger.error(f"{name} validation failed: {'; '.join(issues)}")
                all_issues.extend([f"{name}: {issue}" for issue in issues])
            else:
                logger.info(f"{name} validation passed")
        except Exception as e:
            error_msg = f"{name} validation error: {str(e)}"
            logger.error(error_msg)
            all_issues.append(error_msg)
    
    # Report results
    if all_issues:
        error_summary = "\n".join([f"  - {issue}" for issue in all_issues])
        logger.error(f"Startup validation failed with {len(all_issues)} issues:\n{error_summary}")
        
        if strict:
            raise StartupValidationError(f"Startup validation failed: {'; '.join(all_issues)}")
        return False
    
    logger.info("All startup validations passed successfully")
    return True

def check_required_environment():
    """Quick check for absolutely required environment variables"""
    required_vars = {
        'DATABASE_URL': settings.DATABASE_URL,
        'SECRET_KEY': settings.SECRET_KEY,
    }
    
    missing = [var for var, value in required_vars.items() if not value]
    
    if missing:
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.error(error_msg)
        raise StartupValidationError(error_msg)
    
    logger.info("Required environment variables present")

# FastAPI event handlers can use these functions
async def startup_event():
    """FastAPI startup event handler"""
    try:
        check_required_environment()
        perform_startup_validation(strict=False)  # Don't be strict on startup
        logger.info("Application startup validation completed successfully")
    except StartupValidationError as e:
        logger.error(f"Startup validation failed: {str(e)}")
        # In production, you might want to sys.exit(1) here
        # For now, we'll just log and continue
    except Exception as e:
        logger.error(f"Unexpected error during startup validation: {str(e)}")

if __name__ == "__main__":
    # Command line validation
    logging.basicConfig(level=logging.INFO)
    try:
        success = perform_startup_validation(strict=True)
        if success:
            print("✅ All startup validations passed")
            sys.exit(0)
        else:
            print("❌ Startup validation failed")
            sys.exit(1)
    except StartupValidationError as e:
        print(f"❌ Critical validation error: {str(e)}")
        sys.exit(1)