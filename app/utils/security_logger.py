"""
Security event logging for Recipe Catalogue.
Provides structured logging for security events, file uploads, and audit trails.
"""

import logging
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from app.core.config import settings

class SecurityLogger:
    """Enhanced security logging with structured events"""
    
    def __init__(self, log_dir: str = "logs"):
        """Initialize security logger"""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Set up security event logger
        self.security_logger = logging.getLogger('security')
        self.security_logger.setLevel(getattr(logging, settings.SECURITY_LOG_LEVEL))
        
        # Set up file upload logger
        self.upload_logger = logging.getLogger('uploads')
        self.upload_logger.setLevel(logging.INFO)
        
        # Configure handlers if not already configured
        if not self.security_logger.handlers:
            self._configure_security_handler()
        
        if not self.upload_logger.handlers:
            self._configure_upload_handler()
    
    def _configure_security_handler(self):
        """Configure security event file handler"""
        security_log_file = self.log_dir / "security_events.log"
        handler = logging.FileHandler(security_log_file)
        
        # JSON formatter for structured logs
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.security_logger.addHandler(handler)
    
    def _configure_upload_handler(self):
        """Configure file upload audit handler"""
        upload_log_file = self.log_dir / "file_uploads.log"
        handler = logging.FileHandler(upload_log_file)
        
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "event": "file_upload", "data": %(message)s}',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.upload_logger.addHandler(handler)
    
    def log_security_event(self, event_type: str, user_id: Optional[str], details: Dict[str, Any], severity: str = "INFO"):
        """
        Log security events with structured data
        
        Args:
            event_type: Type of security event (e.g., 'file_upload_rejected', 'validation_failed')
            user_id: ID of user involved in event
            details: Additional event details
            severity: Log severity level
        """
        if not settings.LOG_SECURITY_EVENTS:
            return
        
        event_data = {
            "event_type": event_type,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "severity": severity,
            "details": details,
            "source": "recipe_catalogue"
        }
        
        log_message = json.dumps(event_data)
        
        if severity == "CRITICAL":
            self.security_logger.critical(log_message)
        elif severity == "ERROR":
            self.security_logger.error(log_message)
        elif severity == "WARNING":
            self.security_logger.warning(log_message)
        else:
            self.security_logger.info(log_message)
    
    def log_file_upload_attempt(self, user_id: str, filename: str, file_size: int, 
                               mime_type: str, validation_result: Dict[str, Any]):
        """Log file upload attempts with validation results"""
        if not settings.LOG_FILE_UPLOADS:
            return
        
        upload_data = {
            "user_id": user_id,
            "filename": filename,
            "file_size": file_size,
            "mime_type": mime_type,
            "validation_passed": validation_result.get('valid', False),
            "security_score": validation_result.get('security_score', 0),
            "errors": validation_result.get('errors', []),
            "warnings": validation_result.get('warnings', []),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.upload_logger.info(json.dumps(upload_data))
    
    def log_file_upload_success(self, user_id: str, original_filename: str, 
                               processed_filename: str, processing_metadata: Dict[str, Any]):
        """Log successful file processing"""
        if not settings.LOG_FILE_UPLOADS:
            return
        
        success_data = {
            "user_id": user_id,
            "original_filename": original_filename,
            "processed_filename": processed_filename,
            "processing_metadata": processing_metadata,
            "status": "success",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.upload_logger.info(json.dumps(success_data))
    
    def log_file_validation_failure(self, user_id: str, filename: str, 
                                   validation_errors: list, security_score: int):
        """Log file validation failures for security monitoring"""
        self.log_security_event(
            event_type="file_validation_failure",
            user_id=user_id,
            details={
                "filename": filename,
                "validation_errors": validation_errors,
                "security_score": security_score,
                "action": "upload_rejected"
            },
            severity="WARNING"
        )
    
    def log_suspicious_file_upload(self, user_id: str, filename: str, 
                                  suspicious_indicators: list, security_score: int):
        """Log suspicious file upload attempts"""
        self.log_security_event(
            event_type="suspicious_file_upload",
            user_id=user_id,
            details={
                "filename": filename,
                "suspicious_indicators": suspicious_indicators,
                "security_score": security_score,
                "action": "upload_blocked"
            },
            severity="ERROR"
        )
    
    def log_command_injection_attempt(self, user_id: str, input_data: str, source: str):
        """Log potential command injection attempts"""
        self.log_security_event(
            event_type="command_injection_attempt",
            user_id=user_id,
            details={
                "input_data": input_data[:100],  # Truncate for security
                "source": source,
                "action": "input_sanitized"
            },
            severity="CRITICAL"
        )
    
    def log_rate_limit_exceeded(self, user_id: str, endpoint: str, attempts: int):
        """Log rate limit violations"""
        self.log_security_event(
            event_type="rate_limit_exceeded",
            user_id=user_id,
            details={
                "endpoint": endpoint,
                "attempts": attempts,
                "action": "request_blocked"
            },
            severity="WARNING"
        )
    
    def log_file_processing_error(self, user_id: str, filename: str, error_details: str):
        """Log file processing errors for investigation"""
        self.log_security_event(
            event_type="file_processing_error",
            user_id=user_id,
            details={
                "filename": filename,
                "error": error_details,
                "action": "processing_failed"
            },
            severity="ERROR"
        )
    
    def generate_security_report(self, hours: int = 24) -> Dict[str, Any]:
        """Generate security event summary report"""
        try:
            security_log_file = self.log_dir / "security_events.log"
            if not security_log_file.exists():
                return {"error": "No security log file found"}
            
            cutoff_time = time.time() - (hours * 3600)
            events = []
            
            with open(security_log_file, 'r') as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        event_time = datetime.fromisoformat(
                            json.loads(event['message'])['timestamp']
                        ).timestamp()
                        
                        if event_time > cutoff_time:
                            events.append(json.loads(event['message']))
                    except (json.JSONDecodeError, KeyError):
                        continue
            
            # Aggregate statistics
            event_types = {}
            severity_counts = {}
            user_activity = {}
            
            for event in events:
                event_type = event.get('event_type', 'unknown')
                severity = event.get('severity', 'INFO')
                user_id = event.get('user_id', 'anonymous')
                
                event_types[event_type] = event_types.get(event_type, 0) + 1
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
                user_activity[user_id] = user_activity.get(user_id, 0) + 1
            
            return {
                "report_period_hours": hours,
                "total_events": len(events),
                "event_types": event_types,
                "severity_distribution": severity_counts,
                "top_users": sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:10],
                "recent_critical_events": [
                    event for event in events[-50:] 
                    if event.get('severity') in ['CRITICAL', 'ERROR']
                ]
            }
            
        except Exception as e:
            return {"error": f"Failed to generate security report: {str(e)}"}

# Global security logger instance
security_logger = SecurityLogger()