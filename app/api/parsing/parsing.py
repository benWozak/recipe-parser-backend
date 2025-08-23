from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import uuid
import asyncio
import json
import logging
from app.core.database import get_db
from app.core.config import settings
from app.api.auth.auth import get_current_user
from app.models.user import User
from app.schemas.recipe import RecipeCreate
from app.services.parsing_service import ParsingService
from app.services.parsers import ValidationPipeline, ValidationStatus
from app.services.parsers.url_parser import WebsiteProtectionError
from app.services.parsers.progress_events import progress_stream, ProgressPhase, ProgressStatus
from app.middleware.rate_limit import limiter
from app.middleware.file_security import file_security_validator
from app.utils.security_logger import security_logger
from app.core.tier_enforcement import require_premium, check_parsing_limit
from app.services.usage_tracking_service import UsageTrackingService
from pydantic import BaseModel

router = APIRouter()

class URLParseRequest(BaseModel):
    url: str
    collection_id: Optional[str] = None

class InstagramParseRequest(BaseModel):
    url: str
    collection_id: Optional[str] = None

class BatchInstagramRequest(BaseModel):
    urls: List[str]
    max_results: Optional[int] = 20
    collection_id: Optional[str] = None

class ProfileParseRequest(BaseModel):
    username: str
    max_posts: Optional[int] = 10

class HashtagSearchRequest(BaseModel):
    hashtag: str
    max_posts: Optional[int] = 20

class ValidationApprovalRequest(BaseModel):
    validation_id: str
    user_edits: Optional[Dict[str, Any]] = None

class ValidationRejectionRequest(BaseModel):
    validation_id: str
    reason: str

class URLParseStreamRequest(BaseModel):
    url: str
    collection_id: Optional[str] = None

@router.post("/url")
@limiter.limit(settings.PARSING_RATE_LIMIT)
@check_parsing_limit
async def parse_recipe_from_url(
    url_request: URLParseRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parsing_service = ParsingService(db)
    try:
        recipe_data = await parsing_service.parse_from_url(url_request.url, current_user.id, url_request.collection_id)
        return recipe_data
    except WebsiteProtectionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_type": "website_protection",
                "message": str(e),
                "suggestions": [
                    "Try copying and pasting the recipe text manually",
                    "Take a screenshot and use image parsing instead",
                    "Look for the same recipe on a different website",
                    "Some websites block automated access to protect their content"
                ]
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse recipe from URL: {str(e)}"
        )

@router.post("/url/stream")
@limiter.limit(settings.PARSING_RATE_LIMIT)
@check_parsing_limit
async def parse_recipe_from_url_stream(
    stream_request: URLParseStreamRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stream real-time progress updates while parsing recipe from URL"""
    session_id = str(uuid.uuid4())
    
    async def event_stream():
        try:
            # Create progress tracking session
            progress_emitter = progress_stream.create_session(stream_request.url, session_id)
            
            # Start parsing in background task
            parsing_task = asyncio.create_task(
                parse_recipe_with_progress(stream_request, current_user, db, progress_emitter)
            )
            
            # Stream progress events
            async for event in progress_stream.subscribe_to_session(session_id):
                yield event.to_sse_format()
                
                # Stop streaming if completed or failed
                if event.phase in [ProgressPhase.COMPLETED, ProgressPhase.FAILED]:
                    break
            
            # Wait for parsing to complete and get result
            try:
                result = await parsing_task
                
                # Send final result as data event
                final_event = {
                    "event": "result",
                    "data": result
                }
                yield f"data: {json.dumps(final_event)}\n\n"
                
            except Exception as e:
                # Send error as final event
                error_event = {
                    "event": "error",
                    "data": {
                        "error_type": "parsing_failed",
                        "message": str(e)
                    }
                }
                yield f"data: {json.dumps(error_event)}\n\n"
                
        except asyncio.CancelledError:
            # Client disconnected
            pass
        except Exception as e:
            # Send error event
            error_event = {
                "event": "error", 
                "data": {
                    "error_type": "stream_error",
                    "message": str(e)
                }
            }
            yield f"data: {json.dumps(error_event)}\n\n"
        finally:
            # Cleanup session
            progress_stream.cleanup_session(session_id)
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-ID": session_id
        }
    )

async def parse_recipe_with_progress(
    request: URLParseStreamRequest,
    current_user: User,
    db: Session,
    progress_emitter
):
    """Parse recipe with progress tracking"""
    
    parsing_service = ParsingService(db)
    try:
        # Parse using URL parser with progress tracking
        recipe_data = await parsing_service.parse_from_url_with_progress(
            request.url, 
            current_user.id, 
            request.collection_id,
            progress_emitter
        )
        return recipe_data
    except WebsiteProtectionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_type": "website_protection",
                "message": str(e),
                "suggestions": [
                    "Try copying and pasting the recipe text manually",
                    "Take a screenshot and use image parsing instead",
                    "Look for the same recipe on a different website",
                    "Some websites block automated access to protect their content"
                ]
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse recipe from URL: {str(e)}"
        )

@router.post("/instagram")
@limiter.limit(settings.PARSING_RATE_LIMIT)
@check_parsing_limit
async def parse_recipe_from_instagram(
    instagram_request: InstagramParseRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    parsing_service = ParsingService(db)
    try:
        recipe_data = await parsing_service.parse_from_instagram(instagram_request.url, current_user.id, instagram_request.collection_id)
        return recipe_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse recipe from Instagram: {str(e)}"
        )

@router.post("/instagram/batch")
@limiter.limit(settings.INSTAGRAM_BATCH_RATE_LIMIT)
async def parse_batch_instagram_urls(
    batch_request: BatchInstagramRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Parse multiple Instagram URLs in batch"""
    parsing_service = ParsingService(db)
    results = []
    errors = []
    
    for url in batch_request.urls[:batch_request.max_results]:
        try:
            recipe_data = await parsing_service.parse_from_instagram(url, current_user.id, batch_request.collection_id)
            results.append({"url": url, "status": "success", "data": recipe_data})
        except Exception as e:
            errors.append({"url": url, "status": "error", "error": str(e)})
    
    return {
        "total_processed": len(batch_request.urls[:batch_request.max_results]),
        "successful": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors
    }

@router.post("/instagram/profile")
@limiter.limit(settings.INSTAGRAM_BATCH_RATE_LIMIT)
async def parse_instagram_profile(
    profile_request: ProfileParseRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Parse recipes from an Instagram profile"""
    parsing_service = ParsingService(db)
    try:
        recipes = parsing_service.instagram_parser.parse_instagram_profile(
            profile_request.username, 
            profile_request.max_posts
        )
        
        # Convert to legacy format
        recipe_data = []
        for recipe in recipes:
            data = parsing_service._convert_to_legacy_format(recipe)
            recipe_data.append(data)
        
        return {
            "username": profile_request.username,
            "recipes_found": len(recipe_data),
            "recipes": recipe_data
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse Instagram profile: {str(e)}"
        )

@router.post("/instagram/hashtag")
@limiter.limit(settings.INSTAGRAM_BATCH_RATE_LIMIT)
async def search_recipes_by_hashtag(
    hashtag_request: HashtagSearchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search for recipes using Instagram hashtags"""
    parsing_service = ParsingService(db)
    try:
        recipes = parsing_service.instagram_parser.search_recipe_hashtags(
            hashtag_request.hashtag, 
            hashtag_request.max_posts
        )
        
        # Convert to legacy format
        recipe_data = []
        for recipe in recipes:
            data = parsing_service._convert_to_legacy_format(recipe)
            recipe_data.append(data)
        
        return {
            "hashtag": hashtag_request.hashtag,
            "recipes_found": len(recipe_data),
            "recipes": recipe_data
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to search hashtag: {str(e)}"
        )

@router.post("/image")
@limiter.limit(settings.FILE_UPLOAD_RATE_LIMIT)
@require_premium
async def parse_recipe_from_image(
    request: Request,
    file: UploadFile = File(...),
    collection_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Parse recipe from uploaded image with comprehensive security validation
    """
    logger = logging.getLogger(__name__)
    
    # Read file data
    try:
        file_data = await file.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded file"
        )
    
    # Comprehensive file validation
    validation_result = file_security_validator.validate_file_upload(
        file_data=file_data,
        filename=file.filename or "unknown",
        declared_mime_type=file.content_type or "application/octet-stream"
    )
    
    # Log upload attempt
    security_logger.log_file_upload_attempt(
        user_id=current_user.id,
        filename=file.filename or "unknown",
        file_size=len(file_data),
        mime_type=file.content_type or "application/octet-stream",
        validation_result=validation_result
    )
    
    # Check validation results
    if not validation_result['valid']:
        # Log security violation
        security_logger.log_file_validation_failure(
            user_id=current_user.id,
            filename=file.filename or "unknown",
            validation_errors=validation_result['errors'],
            security_score=validation_result['security_score']
        )
        
        # Return detailed error for debugging (in production, consider generic message)
        error_messages = [error['message'] for error in validation_result['errors']]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "File validation failed",
                "details": error_messages,
                "security_score": validation_result['security_score']
            }
        )
    
    # Check security score threshold
    if validation_result['security_score'] < settings.MIN_FILE_SECURITY_SCORE:
        security_logger.log_suspicious_file_upload(
            user_id=current_user.id,
            filename=file.filename or "unknown",
            suspicious_indicators=validation_result.get('warnings', []),
            security_score=validation_result['security_score']
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "File failed security screening",
                "security_score": validation_result['security_score'],
                "required_score": settings.MIN_FILE_SECURITY_SCORE
            }
        )
    
    # Process the validated image
    parsing_service = ParsingService(db)
    try:
        recipe_data = await parsing_service.parse_from_image(
            file_data, 
            current_user.id, 
            collection_id,
            validation_metadata=validation_result['metadata']
        )
        
        # Log successful processing
        security_logger.log_file_upload_success(
            user_id=current_user.id,
            original_filename=file.filename or "unknown",
            processed_filename=recipe_data.get('media', {}).get('filename', 'unknown'),
            processing_metadata=validation_result['metadata']
        )
        
        return recipe_data
    except Exception as e:
        # Log processing error
        security_logger.log_file_processing_error(
            user_id=current_user.id,
            filename=file.filename or "unknown",
            error_details=str(e)
        )
        
        logger.error(f"Failed to parse recipe from validated image: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse recipe from image: {str(e)}"
        )

# Validation and Preview Endpoints

@router.get("/validation/pending")
async def get_pending_validations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, le=100)
):
    """Get list of recipes pending validation"""
    validation_pipeline = ValidationPipeline()
    try:
        pending_recipes = validation_pipeline.list_pending_recipes(limit)
        
        # Filter by user if needed (for now, return all)
        return {
            "total": len(pending_recipes),
            "recipes": [
                {
                    "id": recipe.id,
                    "title": recipe.parsed_recipe.title,
                    "source_url": recipe.original_source,
                    "confidence_score": recipe.parsed_recipe.confidence_score,
                    "status": recipe.validation_status,
                    "created_at": recipe.created_at,
                    "issues": [{"type": issue.type, "severity": issue.severity, "message": issue.message} 
                              for issue in recipe.issues]
                }
                for recipe in pending_recipes
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pending validations: {str(e)}"
        )

@router.get("/validation/{validation_id}")
async def get_validation_detail(
    validation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed validation information for a specific recipe"""
    validation_pipeline = ValidationPipeline()
    try:
        validation_result = validation_pipeline.get_pending_recipe(validation_id)
        if not validation_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Validation record not found"
            )
        
        return {
            "validation_id": validation_result.id,
            "recipe": {
                "title": validation_result.parsed_recipe.title,
                "description": validation_result.parsed_recipe.description,
                "source_type": validation_result.parsed_recipe.source_type,
                "source_url": validation_result.parsed_recipe.source_url,
                "ingredients": validation_result.parsed_recipe.ingredients,
                "instructions": validation_result.parsed_recipe.instructions,
                "prep_time": validation_result.parsed_recipe.prep_time,
                "cook_time": validation_result.parsed_recipe.cook_time,
                "total_time": validation_result.parsed_recipe.total_time,
                "servings": validation_result.parsed_recipe.servings,
                "confidence_score": validation_result.parsed_recipe.confidence_score,
                "media": validation_result.parsed_recipe.media
            },
            "validation": {
                "status": validation_result.validation_status,
                "created_at": validation_result.created_at,
                "issues": [
                    {
                        "type": issue.type,
                        "severity": issue.severity,
                        "message": issue.message,
                        "field": issue.field,
                        "suggestion": issue.suggestion
                    }
                    for issue in validation_result.issues
                ]
            },
            "metadata": validation_result.parsing_metadata
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get validation details: {str(e)}"
        )

@router.post("/validation/{validation_id}/approve")
@limiter.limit(settings.PARSING_RATE_LIMIT)
async def approve_validation(
    validation_id: str,
    approval_request: ValidationApprovalRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Approve a validated recipe, optionally with user edits"""
    validation_pipeline = ValidationPipeline()
    try:
        validation_result = validation_pipeline.approve_recipe(
            validation_id, 
            approval_request.user_edits
        )
        
        return {
            "status": "approved",
            "validation_id": validation_id,
            "message": "Recipe approved successfully",
            "final_recipe": {
                "title": validation_result.parsed_recipe.title,
                "description": validation_result.parsed_recipe.description,
                "confidence_score": validation_result.parsed_recipe.confidence_score
            }
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve recipe: {str(e)}"
        )

@router.post("/validation/{validation_id}/reject")
@limiter.limit(settings.PARSING_RATE_LIMIT)
async def reject_validation(
    validation_id: str,
    rejection_request: ValidationRejectionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reject a validated recipe"""
    validation_pipeline = ValidationPipeline()
    try:
        validation_result = validation_pipeline.reject_recipe(
            validation_id, 
            rejection_request.reason
        )
        
        return {
            "status": "rejected",
            "validation_id": validation_id,
            "reason": rejection_request.reason,
            "message": "Recipe rejected successfully"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject recipe: {str(e)}"
        )

@router.get("/validation/summary")
async def get_validation_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get summary of validation pipeline status"""
    validation_pipeline = ValidationPipeline()
    try:
        summary = validation_pipeline.get_validation_summary()
        return summary
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get validation summary: {str(e)}"
        )

@router.get("/progress/sessions")
async def get_active_progress_sessions(
    current_user: User = Depends(get_current_user)
):
    """Get information about active parsing sessions"""
    try:
        active_sessions = progress_stream.get_active_sessions()
        return {
            "active_sessions": len(active_sessions),
            "sessions": active_sessions
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get progress sessions: {str(e)}"
        )

@router.get("/progress/session/{session_id}")
async def get_progress_session_details(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get detailed information about a specific parsing session"""
    try:
        session = progress_stream.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        return session.get_summary()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session details: {str(e)}"
        )