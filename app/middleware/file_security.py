"""
Secure file upload validation middleware for Recipe Catalogue.
Provides comprehensive file validation, content inspection, and security checks.
"""

try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    magic = None

import hashlib
import tempfile
import logging
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from PIL import Image
import io

logger = logging.getLogger(__name__)

class FileSecurityValidator:
    """Comprehensive file security validation for uploads"""
    
    # Allowed MIME types mapped to file extensions
    ALLOWED_MIME_TYPES = {
        'image/jpeg': ['.jpg', '.jpeg'],
        'image/png': ['.png'],
        'image/webp': ['.webp'],
        'image/gif': ['.gif'],
    }
    
    # Maximum file sizes (in bytes)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_IMAGE_DIMENSIONS = (4096, 4096)  # 4K max resolution
    
    # Dangerous file signatures to reject
    DANGEROUS_SIGNATURES = [
        b'\x4d\x5a',  # Windows executables (.exe, .dll)
        b'\x7f\x45\x4c\x46',  # Linux executables (ELF)
        b'\xca\xfe\xba\xbe',  # Java class files
        b'\xfe\xed\xfa',  # Mach-O executables (macOS)
        b'\x50\x4b\x03\x04',  # ZIP files (could contain executables)
        b'\x52\x61\x72\x21',  # RAR archives
        b'\x1f\x8b\x08',  # GZIP files
    ]
    
    def __init__(self):
        """Initialize the file security validator"""
        self.magic_available = MAGIC_AVAILABLE
        if not self.magic_available:
            logger.warning("python-magic not available, using fallback validation")
        else:
            try:
                # Test if python-magic is working
                magic.from_buffer(b"test", mime=True)
            except Exception as e:
                logger.warning(f"python-magic available but not working, using fallback validation: {e}")
                self.magic_available = False
    
    def validate_file_upload(self, file_data: bytes, filename: str, declared_mime_type: str) -> Dict[str, Any]:
        """
        Comprehensive file validation
        
        Args:
            file_data: Raw file bytes
            filename: Original filename
            declared_mime_type: MIME type from upload
            
        Returns:
            Dict with validation results and metadata
        """
        validation_result = {
            'valid': False,
            'errors': [],
            'warnings': [],
            'metadata': {},
            'security_score': 0  # 0-100, higher is safer
        }
        
        try:
            # Basic checks
            if not self._validate_file_size(file_data, validation_result):
                return validation_result
            
            if not self._validate_filename(filename, validation_result):
                return validation_result
            
            # Content-based validation
            if not self._validate_file_signature(file_data, validation_result):
                return validation_result
            
            # MIME type validation
            actual_mime_type = self._detect_mime_type(file_data)
            if not self._validate_mime_type(actual_mime_type, declared_mime_type, filename, validation_result):
                return validation_result
            
            # Image-specific validation
            if actual_mime_type.startswith('image/'):
                if not self._validate_image_content(file_data, validation_result):
                    return validation_result
            
            # Security scanning
            self._perform_security_scan(file_data, validation_result)
            
            # Calculate security score
            validation_result['security_score'] = self._calculate_security_score(validation_result)
            
            # Mark as valid if no critical errors
            if not any(error.get('severity') == 'critical' for error in validation_result['errors']):
                validation_result['valid'] = True
            
        except Exception as e:
            logger.error(f"File validation failed: {e}")
            validation_result['errors'].append({
                'type': 'validation_error',
                'severity': 'critical',
                'message': f"Validation process failed: {str(e)}"
            })
        
        return validation_result
    
    def _validate_file_size(self, file_data: bytes, result: Dict) -> bool:
        """Validate file size constraints"""
        file_size = len(file_data)
        result['metadata']['file_size'] = file_size
        
        if file_size == 0:
            result['errors'].append({
                'type': 'empty_file',
                'severity': 'critical',
                'message': 'File is empty'
            })
            return False
        
        if file_size > self.MAX_FILE_SIZE:
            result['errors'].append({
                'type': 'file_too_large',
                'severity': 'critical',
                'message': f'File size {file_size} bytes exceeds maximum {self.MAX_FILE_SIZE} bytes'
            })
            return False
        
        return True
    
    def _validate_filename(self, filename: str, result: Dict) -> bool:
        """Validate filename for security issues"""
        if not filename:
            result['errors'].append({
                'type': 'invalid_filename',
                'severity': 'critical',
                'message': 'Filename is empty'
            })
            return False
        
        # Check for directory traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            result['errors'].append({
                'type': 'path_traversal',
                'severity': 'critical',
                'message': 'Filename contains path traversal characters'
            })
            return False
        
        # Check for suspicious extensions
        filename_lower = filename.lower()
        suspicious_extensions = ['.exe', '.bat', '.cmd', '.scr', '.pif', '.com', '.js', '.vbs', '.jar']
        for ext in suspicious_extensions:
            if filename_lower.endswith(ext):
                result['errors'].append({
                    'type': 'dangerous_extension',
                    'severity': 'critical',
                    'message': f'Filename has dangerous extension: {ext}'
                })
                return False
        
        # Check filename length
        if len(filename) > 255:
            result['errors'].append({
                'type': 'filename_too_long',
                'severity': 'warning',
                'message': 'Filename is very long, will be truncated'
            })
        
        result['metadata']['filename'] = filename
        return True
    
    def _validate_file_signature(self, file_data: bytes, result: Dict) -> bool:
        """Validate file signature/magic bytes"""
        if len(file_data) < 8:
            result['errors'].append({
                'type': 'file_too_small',
                'severity': 'critical',
                'message': 'File too small to validate signature'
            })
            return False
        
        # Check for dangerous file signatures
        file_header = file_data[:12]
        for dangerous_sig in self.DANGEROUS_SIGNATURES:
            if file_header.startswith(dangerous_sig):
                result['errors'].append({
                    'type': 'dangerous_file_type',
                    'severity': 'critical',
                    'message': 'File contains dangerous binary signature'
                })
                return False
        
        return True
    
    def _detect_mime_type(self, file_data: bytes) -> str:
        """Detect actual MIME type from file content"""
        try:
            if self.magic_available:
                return magic.from_buffer(file_data, mime=True)
            else:
                # Fallback: basic image signature detection
                if file_data.startswith(b'\xff\xd8\xff'):
                    return 'image/jpeg'
                elif file_data.startswith(b'\x89PNG\r\n\x1a\n'):
                    return 'image/png'
                elif file_data.startswith(b'RIFF') and b'WEBP' in file_data[:12]:
                    return 'image/webp'
                elif file_data.startswith(b'GIF8'):
                    return 'image/gif'
                else:
                    return 'application/octet-stream'
        except Exception as e:
            logger.warning(f"MIME type detection failed: {e}")
            return 'application/octet-stream'
    
    def _validate_mime_type(self, actual_mime: str, declared_mime: str, filename: str, result: Dict) -> bool:
        """Validate MIME type consistency"""
        result['metadata']['actual_mime_type'] = actual_mime
        result['metadata']['declared_mime_type'] = declared_mime
        
        # Check if MIME type is allowed
        if actual_mime not in self.ALLOWED_MIME_TYPES:
            result['errors'].append({
                'type': 'unsupported_mime_type',
                'severity': 'critical',
                'message': f'MIME type {actual_mime} is not allowed'
            })
            return False
        
        # Check MIME type vs declared type
        if actual_mime != declared_mime:
            result['warnings'].append({
                'type': 'mime_type_mismatch',
                'severity': 'warning',
                'message': f'Actual MIME type {actual_mime} differs from declared {declared_mime}'
            })
        
        # Check MIME type vs file extension
        file_ext = Path(filename).suffix.lower()
        allowed_extensions = self.ALLOWED_MIME_TYPES.get(actual_mime, [])
        if file_ext not in allowed_extensions:
            result['warnings'].append({
                'type': 'extension_mismatch',
                'severity': 'warning',
                'message': f'File extension {file_ext} does not match MIME type {actual_mime}'
            })
        
        return True
    
    def _validate_image_content(self, file_data: bytes, result: Dict) -> bool:
        """Validate image-specific content and metadata"""
        try:
            with Image.open(io.BytesIO(file_data)) as img:
                # Basic image metadata
                result['metadata'].update({
                    'image_format': img.format,
                    'image_mode': img.mode,
                    'image_size': img.size,
                    'image_width': img.width,
                    'image_height': img.height
                })
                
                # Check image dimensions
                if img.width > self.MAX_IMAGE_DIMENSIONS[0] or img.height > self.MAX_IMAGE_DIMENSIONS[1]:
                    result['errors'].append({
                        'type': 'image_too_large',
                        'severity': 'warning',
                        'message': f'Image dimensions {img.size} exceed recommended maximum {self.MAX_IMAGE_DIMENSIONS}'
                    })
                
                # Check for suspicious image properties
                if hasattr(img, '_getexif') and img._getexif():
                    # Strip EXIF data for privacy
                    result['warnings'].append({
                        'type': 'exif_data_present',
                        'severity': 'info',
                        'message': 'Image contains EXIF metadata that will be stripped'
                    })
                
                # Verify image can be processed
                img.verify()
                
        except Exception as e:
            result['errors'].append({
                'type': 'image_validation_failed',
                'severity': 'critical',
                'message': f'Image validation failed: {str(e)}'
            })
            return False
        
        return True
    
    def _perform_security_scan(self, file_data: bytes, result: Dict):
        """Perform basic security scanning"""
        # Check for embedded scripts or suspicious content
        suspicious_patterns = [
            b'<script',
            b'javascript:',
            b'vbscript:',
            b'onload=',
            b'onerror=',
            b'<?php',
            b'<%',
            b'#!/bin/',
            b'cmd.exe',
            b'powershell'
        ]
        
        file_data_lower = file_data.lower()
        for pattern in suspicious_patterns:
            if pattern in file_data_lower:
                result['warnings'].append({
                    'type': 'suspicious_content',
                    'severity': 'warning',
                    'message': f'File contains potentially suspicious content pattern'
                })
                break
        
        # Calculate entropy (high entropy might indicate encrypted/compressed malware)
        entropy = self._calculate_entropy(file_data[:1024])  # Check first 1KB
        result['metadata']['entropy'] = entropy
        
        if entropy > 7.5:  # Very high entropy
            result['warnings'].append({
                'type': 'high_entropy',
                'severity': 'info',
                'message': 'File has high entropy (might be compressed/encrypted)'
            })
    
    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data"""
        if not data:
            return 0.0
        
        # Count byte frequencies
        frequencies = {}
        for byte in data:
            frequencies[byte] = frequencies.get(byte, 0) + 1
        
        # Calculate entropy
        data_len = len(data)
        entropy = 0.0
        for count in frequencies.values():
            p = count / data_len
            if p > 0:
                entropy -= p * (p.bit_length() - 1)
        
        return entropy
    
    def _calculate_security_score(self, result: Dict) -> int:
        """Calculate security score (0-100, higher is safer)"""
        score = 100
        
        # Deduct points for errors and warnings
        for error in result['errors']:
            if error['severity'] == 'critical':
                score -= 50
            elif error['severity'] == 'warning':
                score -= 20
        
        for warning in result['warnings']:
            if warning['severity'] == 'warning':
                score -= 10
            elif warning['severity'] == 'info':
                score -= 5
        
        return max(0, score)

    def sanitize_filename(self, filename: str) -> str:
        """Generate a safe filename for storage"""
        # Remove path components
        safe_name = Path(filename).name
        
        # Remove or replace dangerous characters
        safe_chars = []
        for char in safe_name:
            if char.isalnum() or char in '.-_':
                safe_chars.append(char)
            else:
                safe_chars.append('_')
        
        safe_name = ''.join(safe_chars)
        
        # Limit length
        if len(safe_name) > 100:
            name_part = safe_name[:95]
            ext_part = Path(safe_name).suffix[-5:]  # Keep extension
            safe_name = name_part + ext_part
        
        return safe_name

# Global instance
file_security_validator = FileSecurityValidator()