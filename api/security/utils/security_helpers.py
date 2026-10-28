"""
Security Helper Utilities
Additional utility functions for security models and services
Created: 2025-04-25
"""

import logging
import hashlib
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


# ==================== DEVICE FINGERPRINTING UTILITIES ====================

def generate_device_fingerprint(user_agent: str, ip_address: str = None, 
                           screen_resolution: str = None, timezone_offset: str = None,
                           language: str = None, platform: str = None) -> str:
    """
    Generate a unique device fingerprint for device identification
    """
    try:
        # Collect device characteristics
        fingerprint_data = {
            'user_agent': user_agent or '',
            'ip_address': ip_address or '',
            'screen_resolution': screen_resolution or '',
            'timezone_offset': timezone_offset or '',
            'language': language or '',
            'platform': platform or '',
            'timestamp': timezone.now().isoformat()
        }
        
        # Create fingerprint string
        fingerprint_string = '|'.join([
            fingerprint_data['user_agent'],
            fingerprint_data['ip_address'],
            fingerprint_data['screen_resolution'],
            fingerprint_data['timezone_offset'],
            fingerprint_data['language'],
            fingerprint_data['platform']
        ])
        
        # Generate SHA-256 hash
        fingerprint_hash = hashlib.sha256(fingerprint_string.encode()).hexdigest()
        
        return fingerprint_hash
        
    except Exception as e:
        logger.error(f"Error generating device fingerprint: {e}")
        # Return fallback fingerprint
        return hashlib.sha256(f"fallback_{timezone.now().timestamp()}".encode()).hexdigest()


def extract_device_info(user_agent: str) -> Dict[str, Any]:
    """
    Extract device information from user agent string
    """
    try:
        device_info = {
            'browser': 'Unknown',
            'browser_version': 'Unknown',
            'os': 'Unknown',
            'os_version': 'Unknown',
            'device_type': 'unknown',
            'is_mobile': False,
            'is_tablet': False,
            'is_bot': False
        }
        
        if not user_agent:
            return device_info
        
        user_agent_lower = user_agent.lower()
        
        # Browser detection
        browsers = {
            'chrome': r'chrome/([\d.]+)',
            'firefox': r'firefox/([\d.]+)',
            'safari': r'safari/([\d.]+)',
            'edge': r'edg/([\d.]+)',
            'opera': r'opera/([\d.]+)'
        }
        
        for browser, pattern in browsers.items():
            match = re.search(pattern, user_agent_lower)
            if match:
                device_info['browser'] = browser.capitalize()
                device_info['browser_version'] = match.group(1)
                break
        
        # OS detection
        os_patterns = {
            'windows': r'windows nt ([\d.]+)',
            'mac': r'mac os x ([\d._]+)',
            'linux': r'linux ([\d.]+)',
            'android': r'android ([\d.]+)',
            'ios': r'iphone os ([\d._]+)|ipad; cpu os ([\d._]+)'
        }
        
        for os_name, pattern in os_patterns.items():
            match = re.search(pattern, user_agent_lower)
            if match:
                device_info['os'] = os_name.capitalize()
                device_info['os_version'] = match.group(1)
                break
        
        # Device type detection
        mobile_indicators = ['mobile', 'android', 'iphone', 'ipad']
        tablet_indicators = ['ipad', 'tablet']
        
        if any(indicator in user_agent_lower for indicator in mobile_indicators):
            device_info['device_type'] = 'mobile'
            device_info['is_mobile'] = True
        elif any(indicator in user_agent_lower for indicator in tablet_indicators):
            device_info['device_type'] = 'tablet'
            device_info['is_tablet'] = True
        elif 'windows' in user_agent_lower or 'mac' in user_agent_lower or 'linux' in user_agent_lower:
            device_info['device_type'] = 'desktop'
        
        # Bot detection
        bot_indicators = ['bot', 'crawler', 'spider', 'scraper', 'curl', 'wget']
        if any(indicator in user_agent_lower for indicator in bot_indicators):
            device_info['is_bot'] = True
        
        return device_info
        
    except Exception as e:
        logger.error(f"Error extracting device info: {e}")
        return {
            'browser': 'Unknown',
            'device_type': 'unknown',
            'is_bot': False
        }


# ==================== PASSWORD SECURITY UTILITIES ====================

def calculate_password_strength(password: str) -> Tuple[int, List[str]]:
    """
    Calculate password strength and return score with feedback
    """
    try:
        score = 0
        feedback = []
        
        # Length check
        if len(password) >= 8:
            score += 1
        else:
            feedback.append("Password should be at least 8 characters")
        
        if len(password) >= 12:
            score += 1
        
        # Complexity checks
        if re.search(r'[a-z]', password):
            score += 1
        else:
            feedback.append("Include lowercase letters")
        
        if re.search(r'[A-Z]', password):
            score += 1
        else:
            feedback.append("Include uppercase letters")
        
        if re.search(r'\d', password):
            score += 1
        else:
            feedback.append("Include numbers")
        
        if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            score += 1
        else:
            feedback.append("Include special characters")
        
        # Additional strength factors
        if len(password) >= 16:
            score += 1
        
        # Common patterns penalty
        common_patterns = [
            r'123', r'abc', r'qwe', r'password', r'admin',
            r'letmein', r'welcome', r'login'
        ]
        
        for pattern in common_patterns:
            if re.search(pattern, password, re.IGNORECASE):
                score -= 1
                feedback.append("Avoid common patterns")
        
        # Normalize score to 1-6 range
        score = max(1, min(6, score))
        
        return score, feedback
        
    except Exception as e:
        logger.error(f"Error calculating password strength: {e}")
        return 1, ["Error calculating strength"]


def hash_password(password: str, algorithm: str = 'pbkdf2_sha256') -> str:
    """
    Hash password using specified algorithm
    """
    try:
        if algorithm == 'pbkdf2_sha256':
            from django.contrib.auth.hashers import PBKDF2PasswordHasher
            hasher = PBKDF2PasswordHasher()
            return hasher.encode(password)
        elif algorithm == 'bcrypt':
            from django.contrib.auth.hashers import BCryptSHA256PasswordHasher
            hasher = BCryptSHA256PasswordHasher()
            return hasher.encode(password)
        elif algorithm == 'argon2':
            from django.contrib.auth.hashers import Argon2PasswordHasher
            hasher = Argon2PasswordHasher()
            return hasher.encode(password)
        else:
            # Fallback to SHA-256 (not recommended for production)
            return hashlib.sha256(password.encode()).hexdigest()
            
    except Exception as e:
        logger.error(f"Error hashing password: {e}")
        return hashlib.sha256(password.encode()).hexdigest()


# ==================== POLICY VALIDATION UTILITIES ====================

def validate_policy_value(value: Any, validation_rules: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate a policy value against validation rules
    """
    try:
        # Type validation
        expected_type = validation_rules.get('type')
        if expected_type:
            if expected_type == 'int' and not isinstance(value, int):
                return False, f"Value must be an integer"
            elif expected_type == 'str' and not isinstance(value, str):
                return False, f"Value must be a string"
            elif expected_type == 'bool' and not isinstance(value, bool):
                return False, f"Value must be a boolean"
            elif expected_type == 'list' and not isinstance(value, list):
                return False, f"Value must be a list"
            elif expected_type == 'dict' and not isinstance(value, dict):
                return False, f"Value must be a dictionary"
        
        # Range validation
        min_val = validation_rules.get('min')
        max_val = validation_rules.get('max')
        
        if min_val is not None and value < min_val:
            return False, f"Value must be at least {min_val}"
        
        if max_val is not None and value > max_val:
            return False, f"Value must be at most {max_val}"
        
        # Length validation for strings
        min_length = validation_rules.get('min_length')
        max_length = validation_rules.get('max_length')
        
        if isinstance(value, str):
            if min_length is not None and len(value) < min_length:
                return False, f"Value must be at least {min_length} characters"
            
            if max_length is not None and len(value) > max_length:
                return False, f"Value must be at most {max_length} characters"
        
        # Pattern validation
        pattern = validation_rules.get('pattern')
        if pattern and isinstance(value, str):
            if not re.match(pattern, value):
                return False, f"Value must match pattern: {pattern}"
        
        # Choices validation
        choices = validation_rules.get('choices')
        if choices and value not in choices:
            return False, f"Value must be one of: {choices}"
        
        return True, ""
        
    except Exception as e:
        logger.error(f"Error validating policy value: {e}")
        return False, "Validation error"


# ==================== SECURITY INSIGHT UTILITIES ====================

def calculate_risk_score(total_events: int, critical_count: int, 
                     high_count: int, medium_count: int, 
                     low_count: int) -> float:
    """
    Calculate overall risk score from event counts
    """
    try:
        if total_events == 0:
            return 0.0
        
        # Weight different severity levels
        critical_weight = 4.0
        high_weight = 3.0
        medium_weight = 2.0
        low_weight = 1.0
        
        # Calculate weighted score
        weighted_score = (
            (critical_count * critical_weight) +
            (high_count * high_weight) +
            (medium_count * medium_weight) +
            (low_count * low_weight)
        )
        
        # Normalize to 0-100 scale
        max_possible_score = total_events * critical_weight
        risk_score = (weighted_score / max_possible_score) * 100 if max_possible_score > 0 else 0
        
        return min(100.0, risk_score)
        
    except Exception as e:
        logger.error(f"Error calculating risk score: {e}")
        return 0.0


def get_security_recommendations(metrics: Dict[str, Any]) -> List[str]:
    """
    Generate security recommendations based on metrics
    """
    try:
        recommendations = []
        
        # High failure rate recommendation
        if 'failed_logins' in metrics and 'successful_logins' in metrics:
            total_logins = metrics['failed_logins'] + metrics['successful_logins']
            if total_logins > 0:
                failure_rate = metrics['failed_logins'] / total_logins
                if failure_rate > 0.1:  # 10% failure rate
                    recommendations.append(
                        "High login failure rate detected. Consider implementing stronger authentication."
                    )
        
        # High critical events recommendation
        if 'critical_count' in metrics and metrics['critical_count'] > 5:
            recommendations.append(
                "High number of critical events. Immediate investigation recommended."
            )
        
        # Suspicious activity recommendation
        if 'suspicious_activities' in metrics and metrics['suspicious_activities'] > 10:
            recommendations.append(
                "Elevated suspicious activity detected. Review security logs and user behavior."
            )
        
        # Fraud attempts recommendation
        if 'fraud_attempts' in metrics and metrics['fraud_attempts'] > 0:
            recommendations.append(
                "Fraud attempts detected. Review transaction patterns and implement additional controls."
            )
        
        # Malware detection recommendation
        if 'malware_detections' in metrics and metrics['malware_detections'] > 0:
            recommendations.append(
                "Malware detected. Update antivirus definitions and scan affected systems."
            )
        
        # Phishing attempts recommendation
        if 'phishing_attempts' in metrics and metrics['phishing_attempts'] > 0:
            recommendations.append(
                "Phishing attempts detected. Review email security and user awareness training."
            )
        
        # DDoS attacks recommendation
        if 'ddos_attacks' in metrics and metrics['ddos_attacks'] > 0:
            recommendations.append(
                "DDoS attacks detected. Review network security and implement rate limiting."
            )
        
        # Data breaches recommendation
        if 'data_breaches' in metrics and metrics['data_breaches'] > 0:
            recommendations.append(
                "Data breaches detected. Immediate incident response and breach notification required."
            )
        
        return recommendations
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {e}")
        return ["Error generating recommendations"]


# ==================== CACHE KEY UTILITIES ====================

def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate consistent cache keys with error handling
    """
    try:
        parts = [prefix]
        
        for i, arg in enumerate(args):
            parts.append(f"arg{i}:{arg}")
        
        for key in sorted(kwargs.keys()):
            value = kwargs[key]
            # Truncate long values
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            parts.append(f"{key}:{value}")
        
        key = ":".join(parts)
        
        # Ensure key length is reasonable
        if len(key) > 250:
            key_hash = hashlib.md5(key.encode()).hexdigest()
            key = f"{prefix}:hash:{key_hash}"
        
        return key
        
    except Exception as e:
        logger.error(f"Error generating cache key: {e}")
        return f"{prefix}:error:{int(timezone.now().timestamp())}"


# ==================== NOTIFICATION UTILITIES ====================

def send_security_notification(user, notification_type: str, message: str, 
                         metadata: Dict[str, Any] = None) -> bool:
    """
    Send security notification to user
    """
    try:
        # Log notification
        from ..models import SecurityLog
        SecurityLog.objects.create(
            user=user,
            action_type='SECURITY_NOTIFICATION',
            description=message,
            severity='info',
            metadata={
                'notification_type': notification_type,
                'metadata': metadata or {}
            }
        )
        
        # Here you could integrate with email, SMS, or push notification systems
        logger.info(f"Security notification sent to {user.username}: {notification_type}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error sending security notification: {e}")
        return False


# ==================== VALIDATION UTILITIES ====================

def validate_ip_address(ip_address: str) -> bool:
    """
    Validate IP address format
    """
    try:
        import ipaddress
        ipaddress.ip_address(ip_address)
        return True
    except ValueError:
        return False
    except Exception as e:
        logger.error(f"Error validating IP address: {e}")
        return False


def validate_email_format(email: str) -> bool:
    """
    Validate email format
    """
    try:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    except Exception as e:
        logger.error(f"Error validating email format: {e}")
        return False


# ==================== RATE LIMITING UTILITIES ====================

def calculate_rate_limit_key(identifier: str, action: str, window: int = 3600) -> str:
    """
    Calculate rate limiting cache key
    """
    try:
        timestamp = int(timezone.now().timestamp())
        window_start = (timestamp // window) * window
        
        return f"rate_limit:{identifier}:{action}:{window_start}"
        
    except Exception as e:
        logger.error(f"Error calculating rate limit key: {e}")
        return f"rate_limit:{identifier}:{action}:error"


def is_rate_limited(identifier: str, action: str, limit: int = 5, 
                   window: int = 3600) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if identifier is rate limited
    """
    try:
        from django.core.cache import cache
        
        cache_key = calculate_rate_limit_key(identifier, action, window)
        current_count = cache.get(cache_key, 0)
        
        is_limited = current_count >= limit
        
        return is_limited, {
            'current_count': current_count,
            'limit': limit,
            'window': window,
            'reset_time': ((int(timezone.now().timestamp()) // window) + 1) * window
        }
        
    except Exception as e:
        logger.error(f"Error checking rate limit: {e}")
        return False, {'error': str(e)}