"""
Security Helpers Module
Utility helper functions for security operations
"""

import logging
import hashlib
import secrets
import string
import re
import json
import time
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from datetime import datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import models
from django.http import HttpRequest
from rest_framework.request import Request

from .utils import SecurityUtils

User = get_user_model()
logger = logging.getLogger('security.helpers')


class DataSanitizer:
    """Helper class for data sanitization"""
    
    @staticmethod
    def sanitize_string(input_string: str, max_length: int = 255) -> str:
        """Sanitize string input"""
        if not input_string:
            return ""
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\']', '', input_string)
        
        # Remove SQL injection patterns
        sql_patterns = [
            r'(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b)',
            r'(\-\-|\#|\/\*|\*\/)',
            r'(\bOR\b.*\b1\s*=\s*1\b)',
            r'(\bAND\b.*\b1\s*=\s*1\b)'
        ]
        
        for pattern in sql_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        # Remove XSS patterns
        xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'<iframe[^>]*>',
            r'<object[^>]*>',
            r'<embed[^>]*>'
        ]
        
        for pattern in xss_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        # Limit length
        sanitized = sanitized[:max_length]
        
        return sanitized.strip()
    
    @staticmethod
    def sanitize_email(email: str) -> str:
        """Sanitize email address"""
        if not email:
            return ""
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return ""
        
        return email.lower().strip()
    
    @staticmethod
    def sanitize_phone_number(phone: str) -> str:
        """Sanitize phone number"""
        if not phone:
            return ""
        
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', phone)
        
        # Check if it's a valid phone number (10-15 digits)
        if 10 <= len(digits_only) <= 15:
            return digits_only
        
        return ""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename"""
        if not filename:
            return ""
        
        # Remove path separators and dangerous characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # Remove control characters
        sanitized = re.sub(r'[\x00-\x1f\x7f]', '', sanitized)
        
        # Limit length
        sanitized = sanitized[:255]
        
        return sanitized.strip()
    
    @staticmethod
    def sanitize_json(data: Any) -> Any:
        """Sanitize JSON data"""
        try:
            if isinstance(data, str):
                # Parse and re-serialize JSON to ensure it's valid
                parsed = json.loads(data)
                return json.dumps(parsed)
            elif isinstance(data, (dict, list)):
                return json.dumps(data)
            else:
                return data
        except (json.JSONDecodeError, TypeError):
            return None
    
    @staticmethod
    def sanitize_html(html: str) -> str:
        """Sanitize HTML content"""
        if not html:
            return ""
        
        # Remove script tags and their content
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove dangerous attributes
        dangerous_attrs = ['onload', 'onerror', 'onclick', 'onmouseover', 'onfocus', 'onblur']
        for attr in dangerous_attrs:
            html = re.sub(rf'{attr}\s*=\s*["\'][^"\']*["\']', '', html, flags=re.IGNORECASE)
        
        # Remove iframe, object, embed tags
        dangerous_tags = ['iframe', 'object', 'embed', 'form', 'input', 'button']
        for tag in dangerous_tags:
            html = re.sub(rf'<{tag}[^>]*>.*?</{tag}>', '', html, flags=re.IGNORECASE | re.DOTALL)
            html = re.sub(rf'<{tag}[^>]*/>', '', html, flags=re.IGNORECASE)
        
        return html.strip()


class DataValidator:
    """Helper class for data validation"""
    
    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """Validate password strength"""
        result = {
            'is_valid': True,
            'score': 0,
            'issues': [],
            'suggestions': []
        }
        
        if not password:
            result['is_valid'] = False
            result['issues'].append('Password cannot be empty')
            return result
        
        # Length check
        if len(password) < 8:
            result['issues'].append('Password must be at least 8 characters long')
            result['is_valid'] = False
        else:
            result['score'] += 20
        
        # Uppercase check
        if not re.search(r'[A-Z]', password):
            result['issues'].append('Password must contain at least one uppercase letter')
            result['suggestions'].append('Add uppercase letters')
        else:
            result['score'] += 20
        
        # Lowercase check
        if not re.search(r'[a-z]', password):
            result['issues'].append('Password must contain at least one lowercase letter')
            result['suggestions'].append('Add lowercase letters')
        else:
            result['score'] += 20
        
        # Number check
        if not re.search(r'\d', password):
            result['issues'].append('Password must contain at least one number')
            result['suggestions'].append('Add numbers')
        else:
            result['score'] += 20
        
        # Special character check
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            result['issues'].append('Password must contain at least one special character')
            result['suggestions'].append('Add special characters')
        else:
            result['score'] += 20
        
        # Common patterns check
        common_patterns = ['password', '123456', 'qwerty', 'admin', 'letmein']
        for pattern in common_patterns:
            if pattern.lower() in password.lower():
                result['issues'].append(f'Password contains common pattern: {pattern}')
                result['score'] -= 10
                result['is_valid'] = False
        
        return result
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """Validate IP address"""
        try:
            import ipaddress
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL"""
        if not url:
            return False
        
        url_pattern = re.compile(
            r'^(https?|ftp)://'  # http://, https://, ftp://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        return url_pattern.match(url) is not None
    
    @staticmethod
    def validate_json_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate JSON data against schema"""
        result = {
            'is_valid': True,
            'errors': []
        }
        
        # Required fields check
        required_fields = schema.get('required', [])
        for field in required_fields:
            if field not in data:
                result['is_valid'] = False
                result['errors'].append(f'Missing required field: {field}')
        
        # Type validation
        field_types = schema.get('properties', {})
        for field, field_config in field_types.items():
            if field in data:
                expected_type = field_config.get('type')
                actual_value = data[field]
                
                if expected_type == 'string' and not isinstance(actual_value, str):
                    result['is_valid'] = False
                    result['errors'].append(f'Field {field} must be a string')
                elif expected_type == 'number' and not isinstance(actual_value, (int, float, Decimal)):
                    result['is_valid'] = False
                    result['errors'].append(f'Field {field} must be a number')
                elif expected_type == 'boolean' and not isinstance(actual_value, bool):
                    result['is_valid'] = False
                    result['errors'].append(f'Field {field} must be a boolean')
                elif expected_type == 'array' and not isinstance(actual_value, list):
                    result['is_valid'] = False
                    result['errors'].append(f'Field {field} must be an array')
                elif expected_type == 'object' and not isinstance(actual_value, dict):
                    result['is_valid'] = False
                    result['errors'].append(f'Field {field} must be an object')
        
        return result


class SecurityMetrics:
    """Helper class for security metrics"""
    
    @staticmethod
    def calculate_risk_score(factors: Dict[str, Any]) -> float:
        """Calculate risk score from various factors"""
        base_score = 50.0  # Default medium risk
        
        # IP-based factors
        if factors.get('is_private_ip', False):
            base_score -= 10
        else:
            base_score += 10
        
        if factors.get('is_proxy', False):
            base_score += 15
        
        if factors.get('is_vpn', False):
            base_score += 10
        
        if factors.get('is_tor', False):
            base_score += 25
        
        # Time-based factors
        if factors.get('unusual_time', False):
            base_score += 10
        
        # Frequency-based factors
        if factors.get('high_frequency', False):
            base_score += 15
        
        # Location-based factors
        if factors.get('is_high_risk_country', False):
            base_score += 20
        
        # User agent-based factors
        user_agent = factors.get('user_agent', '').lower()
        suspicious_agents = ['bot', 'spider', 'curl', 'wget', 'python', 'scanner']
        for agent in suspicious_agents:
            if agent in user_agent:
                base_score += 20
                break
        
        # Session-based factors
        if factors.get('multiple_sessions', False):
            base_score += 10
        
        # Authentication-based factors
        if factors.get('failed_attempts', 0) > 3:
            base_score += factors.get('failed_attempts', 0) * 5
        
        # Normalize to 0-100 scale
        return max(0.0, min(100.0, base_score))
    
    @staticmethod
    def calculate_threat_score(indicators: List[Dict[str, Any]]) -> float:
        """Calculate threat score from security indicators"""
        if not indicators:
            return 0.0
        
        total_score = 0.0
        weights = {
            'malware': 30,
            'phishing': 25,
            'botnet': 35,
            'ddos': 20,
            'sql_injection': 40,
            'xss': 25,
            'zero_day': 50,
            'apt': 45,
            'ransomware': 40,
            'trojan': 30
        }
        
        for indicator in indicators:
            threat_type = indicator.get('type', '').lower()
            confidence = indicator.get('confidence', 0.5)
            severity = indicator.get('severity', 'medium')
            
            # Base weight for threat type
            weight = weights.get(threat_type, 20)
            
            # Adjust for confidence
            weight *= confidence
            
            # Adjust for severity
            severity_multipliers = {
                'low': 0.5,
                'medium': 1.0,
                'high': 1.5,
                'critical': 2.0
            }
            weight *= severity_multipliers.get(severity, 1.0)
            
            total_score += weight
        
        # Normalize to 0-100 scale
        normalized_score = min(100.0, total_score)
        
        return normalized_score
    
    @staticmethod
    def calculate_security_health_score(metrics: Dict[str, Any]) -> float:
        """Calculate overall security health score"""
        weights = {
            'log_analysis': 0.25,
            'incident_response': 0.20,
            'threat_detection': 0.20,
            'vulnerability_management': 0.15,
            'compliance': 0.10,
            'user_behavior': 0.10
        }
        
        total_score = 0.0
        
        for metric, weight in weights.items():
            metric_value = metrics.get(metric, 0)
            total_score += metric_value * weight
        
        return total_score


class CacheHelper:
    """Helper class for cache operations"""
    
    @staticmethod
    def get_cached_data(key: str, default=None, timeout: int = 300):
        """Get cached data with default value"""
        try:
            return cache.get(key, default)
        except Exception as e:
            logger.error(f"Error getting cached data for key {key}: {e}")
            return default
    
    @staticmethod
    def set_cached_data(key: str, data: Any, timeout: int = 300):
        """Set cached data"""
        try:
            cache.set(key, data, timeout)
            return True
        except Exception as e:
            logger.error(f"Error setting cached data for key {key}: {e}")
            return False
    
    @staticmethod
    def delete_cached_data(key: str):
        """Delete cached data"""
        try:
            cache.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting cached data for key {key}: {e}")
            return False
    
    @staticmethod
    def increment_cached_counter(key: str, delta: int = 1, timeout: int = 300):
        """Increment cached counter"""
        try:
            return cache.incr(key, delta)
        except Exception as e:
            logger.error(f"Error incrementing cached counter for key {key}: {e}")
            return None
    
    @staticmethod
    def get_or_set_cached_data(key: str, callback: Callable, timeout: int = 300):
        """Get cached data or set using callback"""
        try:
            data = cache.get(key)
            if data is None:
                data = callback()
                cache.set(key, data, timeout)
            return data
        except Exception as e:
            logger.error(f"Error in get_or_set_cached_data for key {key}: {e}")
            return callback()


class RequestHelper:
    """Helper class for request operations"""
    
    @staticmethod
    def get_client_ip(request: Union[HttpRequest, Request]) -> str:
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        return ip or '0.0.0.0'
    
    @staticmethod
    def get_user_agent(request: Union[HttpRequest, Request]) -> str:
        """Get user agent from request"""
        return request.META.get('HTTP_USER_AGENT', '')
    
    @staticmethod
    def get_referer(request: Union[HttpRequest, Request]) -> str:
        """Get referer from request"""
        return request.META.get('HTTP_REFERER', '')
    
    @staticmethod
    def is_ajax_request(request: Union[HttpRequest, Request]) -> bool:
        """Check if request is AJAX"""
        return (
            request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest' or
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        )
    
    @staticmethod
    def is_api_request(request: Union[HttpRequest, Request]) -> bool:
        """Check if request is API request"""
        path = request.path
        return path.startswith('/api/') or path.startswith('/v1/') or path.startswith('/v2/')
    
    @staticmethod
    def get_request_fingerprint(request: Union[HttpRequest, Request]) -> str:
        """Generate request fingerprint"""
        components = [
            RequestHelper.get_client_ip(request),
            RequestHelper.get_user_agent(request),
            request.path,
            request.method,
        ]
        
        fingerprint_data = '|'.join(str(comp) for comp in components)
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()
    
    @staticmethod
    def parse_json_body(request: Union[HttpRequest, Request]) -> Dict[str, Any]:
        """Parse JSON body from request"""
        try:
            if hasattr(request, 'body'):
                return json.loads(request.body.decode('utf-8'))
            else:
                return {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    
    @staticmethod
    def get_query_params(request: Union[HttpRequest, Request]) -> Dict[str, Any]:
        """Get query parameters as dict"""
        return dict(request.GET.items())
    
    @staticmethod
    def get_headers(request: Union[HttpRequest, Request]) -> Dict[str, str]:
        """Get request headers"""
        return {
            key: value
            for key, value in request.META.items()
            if key.startswith('HTTP_')
        }


class TimeHelper:
    """Helper class for time operations"""
    
    @staticmethod
    def utc_now() -> datetime:
        """Get current UTC time"""
        return timezone.now()
    
    @staticmethod
    def to_utc(dt: datetime) -> datetime:
        """Convert datetime to UTC"""
        if dt.tzinfo is None:
            dt = timezone.make_aware(dt)
        return dt.astimezone(timezone.utc)
    
    @staticmethod
    def from_timestamp(timestamp: Union[int, float]) -> datetime:
        """Convert timestamp to datetime"""
        return timezone.make_aware(datetime.fromtimestamp(timestamp))
    
    @staticmethod
    def to_timestamp(dt: datetime) -> float:
        """Convert datetime to timestamp"""
        return dt.timestamp()
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in human readable format"""
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        elif seconds < 86400:
            hours = seconds / 3600
            return f"{hours:.1f} hours"
        else:
            days = seconds / 86400
            return f"{days:.1f} days"
    
    @staticmethod
    def get_time_range(period: str) -> Tuple[datetime, datetime]:
        """Get time range for a period"""
        now = timezone.now()
        
        if period == 'last_hour':
            start = now - timedelta(hours=1)
        elif period == 'last_24h':
            start = now - timedelta(hours=24)
        elif period == 'last_7d':
            start = now - timedelta(days=7)
        elif period == 'last_30d':
            start = now - timedelta(days=30)
        elif period == 'last_90d':
            start = now - timedelta(days=90)
        elif period == 'last_year':
            start = now - timedelta(days=365)
        else:
            start = now - timedelta(hours=1)  # Default to last hour
        
        return start, now
    
    @staticmethod
    def is_business_hours(dt: datetime = None) -> bool:
        """Check if datetime is during business hours"""
        if dt is None:
            dt = timezone.now()
        
        # Convert to local time if needed
        if dt.tzinfo != timezone.get_current_timezone():
            dt = dt.astimezone(timezone.get_current_timezone())
        
        hour = dt.hour
        weekday = dt.weekday()
        
        # Business hours: 9 AM - 6 PM, Monday - Friday
        return 9 <= hour <= 18 and 0 <= weekday <= 4


class StringHelper:
    """Helper class for string operations"""
    
    @staticmethod
    def generate_random_string(length: int = 32, 
                           include_uppercase: bool = True,
                           include_lowercase: bool = True,
                           include_digits: bool = True,
                           include_special: bool = False) -> str:
        """Generate random string"""
        chars = ''
        
        if include_uppercase:
            chars += string.ascii_uppercase
        if include_lowercase:
            chars += string.ascii_lowercase
        if include_digits:
            chars += string.digits
        if include_special:
            chars += '!@#$%^&*()_+-=[]{}|;:,.<>?'
        
        if not chars:
            chars = string.ascii_lowercase  # Fallback
        
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    @staticmethod
    def mask_string(s: str, mask_char: str = '*', visible_chars: int = 4) -> str:
        """Mask string with visible characters"""
        if not s:
            return s
        
        if len(s) <= visible_chars:
            return mask_char * len(s)
        
        return s[:visible_chars] + mask_char * (len(s) - visible_chars)
    
    @staticmethod
    def truncate_string(s: str, max_length: int, suffix: str = '...') -> str:
        """Truncate string to max length"""
        if len(s) <= max_length:
            return s
        
        return s[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def slugify(text: str) -> str:
        """Convert text to slug"""
        # Convert to lowercase and replace spaces with hyphens
        slug = text.lower().strip()
        
        # Remove special characters except hyphens and underscores
        slug = re.sub(r'[^a-z0-9\s\-_]', '', slug)
        
        # Replace spaces with hyphens
        slug = re.sub(r'\s+', '-', slug)
        
        # Remove multiple hyphens
        slug = re.sub(r'-+', '-', slug)
        
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        
        return slug
    
    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """Extract email addresses from text"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.findall(email_pattern, text)
    
    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """Extract URLs from text"""
        url_pattern = r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))*)?'
        return re.findall(url_pattern, text)
    
    @staticmethod
    def extract_ip_addresses(text: str) -> List[str]:
        """Extract IP addresses from text"""
        ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        return re.findall(ip_pattern, text)


class EncryptionHelper:
    """Helper class for encryption operations"""
    
    @staticmethod
    def generate_key(length: int = 32) -> str:
        """Generate encryption key"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_data(data: str, salt: str = None) -> str:
        """Hash data with optional salt"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        combined = f"{data}{salt}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    @staticmethod
    def verify_hash(data: str, hash_value: str, salt: str = None) -> bool:
        """Verify hash against data"""
        if salt is None:
            return SecurityUtils.generate_secure_token() == hash_value
        
        calculated_hash = EncryptionHelper.hash_data(data, salt)
        return calculated_hash == hash_value
    
    @staticmethod
    def encrypt_sensitive_field(value: str, key: str = None) -> str:
        """Encrypt sensitive field value"""
        if not value:
            return value
        
        try:
            from cryptography.fernet import Fernet
            
            if key is None:
                key = settings.SECURITY_ENCRYPTION_KEY.encode()
            
            fernet = Fernet(key)
            encrypted_value = fernet.encrypt(value.encode())
            return encrypted_value.decode()
        except Exception as e:
            logger.error(f"Error encrypting field: {e}")
            return value
    
    @staticmethod
    def decrypt_sensitive_field(encrypted_value: str, key: str = None) -> str:
        """Decrypt sensitive field value"""
        if not encrypted_value:
            return encrypted_value
        
        try:
            from cryptography.fernet import Fernet
            
            if key is None:
                key = settings.SECURITY_ENCRYPTION_KEY.encode()
            
            fernet = Fernet(key)
            decrypted_value = fernet.decrypt(encrypted_value.encode())
            return decrypted_value.decode()
        except Exception as e:
            logger.error(f"Error decrypting field: {e}")
            return encrypted_value


# Export helper classes
__all__ = [
    'DataSanitizer',
    'DataValidator',
    'SecurityMetrics',
    'CacheHelper',
    'RequestHelper',
    'TimeHelper',
    'StringHelper',
    'EncryptionHelper'
]