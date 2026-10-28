"""
Security Utilities Module
Comprehensive utility functions for security operations
"""

import hashlib
import secrets
import string
import ipaddress
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.utils import timezone
from cryptography.fernet import Fernet
from base64 import b64encode, b64decode
import json

User = get_user_model()
logger = logging.getLogger('security.utils')


class SecurityUtils:
    """Security utility functions"""
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate a cryptographically secure token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def generate_password_hash(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """Generate secure password hash with salt"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        # Combine password and salt
        password_salt = f"{password}{salt}"
        
        # Generate hash
        hash_obj = hashlib.sha256(password_salt.encode())
        password_hash = hash_obj.hexdigest()
        
        return password_hash, salt
    
    @staticmethod
    def verify_password(password: str, salt: str, stored_hash: str) -> bool:
        """Verify password against stored hash"""
        password_hash, _ = SecurityUtils.generate_password_hash(password, salt)
        return password_hash == stored_hash
    
    @staticmethod
    def encrypt_sensitive_data(data: str, key: Optional[str] = None) -> str:
        """Encrypt sensitive data using Fernet"""
        try:
            if key is None:
                key = settings.SECURITY_ENCRYPTION_KEY
            
            fernet = Fernet(key.encode())
            encrypted_data = fernet.encrypt(data.encode())
            return b64encode(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Error encrypting data: {e}")
            raise
    
    @staticmethod
    def decrypt_sensitive_data(encrypted_data: str, key: Optional[str] = None) -> str:
        """Decrypt sensitive data using Fernet"""
        try:
            if key is None:
                key = settings.SECURITY_ENCRYPTION_KEY
            
            fernet = Fernet(key.encode())
            decoded_data = b64decode(encrypted_data.encode())
            decrypted_data = fernet.decrypt(decoded_data)
            return decrypted_data.decode()
        except Exception as e:
            logger.error(f"Error decrypting data: {e}")
            raise
    
    @staticmethod
    def is_valid_ip_address(ip: str) -> bool:
        """Validate IP address format"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def is_private_ip(ip: str) -> bool:
        """Check if IP address is private"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            return ip_obj.is_private
        except ValueError:
            return False
    
    @staticmethod
    def get_ip_geolocation(ip: str) -> Dict[str, Any]:
        """Get geolocation information for IP address"""
        try:
            # This is a placeholder - in real implementation, use a geolocation service
            cache_key = f"geo:{ip}"
            geo_data = cache.get(cache_key)
            
            if not geo_data:
                # Mock geolocation data
                geo_data = {
                    'ip': ip,
                    'country': 'Unknown',
                    'city': 'Unknown',
                    'latitude': 0.0,
                    'longitude': 0.0,
                    'isp': 'Unknown',
                    'is_proxy': False,
                    'is_vpn': False
                }
                cache.set(cache_key, geo_data, timeout=3600)  # Cache for 1 hour
            
            return geo_data
        except Exception as e:
            logger.error(f"Error getting geolocation for {ip}: {e}")
            return {}
    
    @staticmethod
    def generate_device_fingerprint(user_agent: str, ip: str) -> str:
        """Generate device fingerprint from user agent and IP"""
        try:
            # Create a consistent fingerprint
            fingerprint_data = f"{user_agent}:{ip}"
            hash_obj = hashlib.sha256(fingerprint_data.encode())
            return hash_obj.hexdigest()
        except Exception as e:
            logger.error(f"Error generating device fingerprint: {e}")
            return secrets.token_hex(32)
    
    @staticmethod
    def calculate_risk_score(factors: Dict[str, Any]) -> float:
        """Calculate risk score based on various factors"""
        try:
            base_score = 0.0
            
            # IP-based factors
            if factors.get('is_private_ip', False):
                base_score += 10
            else:
                base_score += 30
            
            if factors.get('is_proxy', False):
                base_score += 25
            
            if factors.get('is_vpn', False):
                base_score += 15
            
            if factors.get('is_tor', False):
                base_score += 40
            
            # User agent factors
            user_agent = factors.get('user_agent', '').lower()
            suspicious_agents = ['bot', 'spider', 'curl', 'wget', 'python']
            for agent in suspicious_agents:
                if agent in user_agent:
                    base_score += 20
                    break
            
            # Geographic factors
            if factors.get('is_high_risk_country', False):
                base_score += 25
            
            # Time-based factors
            if factors.get('unusual_time', False):
                base_score += 15
            
            # Frequency factors
            if factors.get('high_frequency', False):
                base_score += 20
            
            # Normalize to 0-100 scale
            return min(100.0, base_score)
        except Exception as e:
            logger.error(f"Error calculating risk score: {e}")
            return 50.0  # Default medium risk
    
    @staticmethod
    def sanitize_input(input_string: str) -> str:
        """Sanitize user input to prevent XSS and injection"""
        try:
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
            
            return sanitized.strip()
        except Exception as e:
            logger.error(f"Error sanitizing input: {e}")
            return ""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        try:
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return bool(re.match(pattern, email))
        except Exception:
            return False
    
    @staticmethod
    def validate_phone_number(phone: str) -> bool:
        """Validate phone number format"""
        try:
            # Remove all non-digit characters
            digits_only = re.sub(r'\D', '', phone)
            # Check if it's a valid phone number (10-15 digits)
            return 10 <= len(digits_only) <= 15
        except Exception:
            return False
    
    @staticmethod
    def generate_session_token() -> str:
        """Generate secure session token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def is_session_valid(session_data: Dict[str, Any]) -> bool:
        """Check if session is still valid"""
        try:
            created_at = session_data.get('created_at')
            if not created_at:
                return False
            
            # Check if session is older than 24 hours
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            
            session_age = timezone.now() - created_at
            return session_age < timedelta(hours=24)
        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return False
    
    @staticmethod
    def log_security_event(event_type: str, details: Dict[str, Any]) -> None:
        """Log security event for audit trail"""
        try:
            from .models import SecurityLog
            
            SecurityLog.objects.create(
                security_type=event_type,
                severity=details.get('severity', 'medium'),
                description=details.get('description', ''),
                metadata=details.get('metadata', {}),
                ip_address=details.get('ip_address'),
                user=details.get('user')
            )
        except Exception as e:
            logger.error(f"Error logging security event: {e}")
    
    @staticmethod
    def get_client_ip(request) -> str:
        """Get client IP address from request"""
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR')
            
            return ip or '0.0.0.0'
        except Exception:
            return '0.0.0.0'
    
    @staticmethod
    def mask_sensitive_info(data: str, mask_char: str = '*', visible_chars: int = 4) -> str:
        """Mask sensitive information for logging"""
        try:
            if len(data) <= visible_chars:
                return mask_char * len(data)
            
            return data[:visible_chars] + mask_char * (len(data) - visible_chars)
        except Exception:
            return mask_char * 8
    
    @staticmethod
    def generate_api_key(length: int = 32) -> str:
        """Generate API key for authentication"""
        return f"sk-{secrets.token_urlsafe(length)}"
    
    @staticmethod
    def verify_api_key(api_key: str) -> bool:
        """Verify API key format"""
        try:
            return api_key.startswith('sk-') and len(api_key) > 35
        except Exception:
            return False
    
    @staticmethod
    def cache_security_data(key: str, data: Any, timeout: int = 300) -> None:
        """Cache security-related data"""
        try:
            cache.set(f"security:{key}", data, timeout)
        except Exception as e:
            logger.error(f"Error caching security data: {e}")
    
    @staticmethod
    def get_cached_security_data(key: str) -> Any:
        """Get cached security data"""
        try:
            return cache.get(f"security:{key}")
        except Exception as e:
            logger.error(f"Error getting cached security data: {e}")
            return None
    
    @staticmethod
    def clear_security_cache(key: str) -> None:
        """Clear security cache entry"""
        try:
            cache.delete(f"security:{key}")
        except Exception as e:
            logger.error(f"Error clearing security cache: {e}")


class PasswordValidator:
    """Password validation utilities"""
    
    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """Validate password strength"""
        result = {
            'is_valid': True,
            'score': 0,
            'issues': [],
            'suggestions': []
        }
        
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
        common_patterns = ['password', '123456', 'qwerty', 'admin']
        for pattern in common_patterns:
            if pattern.lower() in password.lower():
                result['issues'].append(f'Password contains common pattern: {pattern}')
                result['score'] -= 10
                result['is_valid'] = False
        
        return result
    
    @staticmethod
    def generate_strong_password(length: int = 12) -> str:
        """Generate a strong password"""
        try:
            # Define character sets
            lowercase = string.ascii_lowercase
            uppercase = string.ascii_uppercase
            digits = string.digits
            special = '!@#$%^&*()_+-=[]{}|;:,.<>?'
            
            # Ensure at least one character from each set
            password = [
                secrets.choice(lowercase),
                secrets.choice(uppercase),
                secrets.choice(digits),
                secrets.choice(special)
            ]
            
            # Fill the rest with random characters
            all_chars = lowercase + uppercase + digits + special
            for _ in range(length - 4):
                password.append(secrets.choice(all_chars))
            
            # Shuffle the password
            secrets.SystemRandom().shuffle(password)
            
            return ''.join(password)
        except Exception as e:
            logger.error(f"Error generating password: {e}")
            return secrets.token_urlsafe(length)


class RateLimiter:
    """Rate limiting utilities"""
    
    @staticmethod
    def is_rate_limited(identifier: str, limit: int, window: int = 60) -> bool:
        """Check if identifier is rate limited"""
        try:
            cache_key = f"rate_limit:{identifier}"
            current_count = cache.get(cache_key, 0)
            
            if current_count >= limit:
                return True
            
            # Increment counter
            cache.set(cache_key, current_count + 1, window)
            return False
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False
    
    @staticmethod
    def get_rate_limit_status(identifier: str) -> Dict[str, Any]:
        """Get rate limit status for identifier"""
        try:
            cache_key = f"rate_limit:{identifier}"
            current_count = cache.get(cache_key, 0)
            
            return {
                'current_count': current_count,
                'is_limited': current_count > 0,
                'reset_time': cache.ttl(cache_key)
            }
        except Exception as e:
            logger.error(f"Error getting rate limit status: {e}")
            return {'current_count': 0, 'is_limited': False, 'reset_time': 0}


class SecurityHeaderUtils:
    """Security header utilities"""
    
    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get recommended security headers"""
        return {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Content-Security-Policy': "default-src 'self'",
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
        }
    
    @staticmethod
    def add_security_headers(response) -> None:
        """Add security headers to response"""
        try:
            headers = SecurityHeaderUtils.get_security_headers()
            for key, value in headers.items():
                response[key] = value
        except Exception as e:
            logger.error(f"Error adding security headers: {e}")


# Export main utilities
__all__ = [
    'SecurityUtils',
    'PasswordValidator', 
    'RateLimiter',
    'SecurityHeaderUtils'
]