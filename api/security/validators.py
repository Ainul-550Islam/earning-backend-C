"""
Enhanced Security Validators Module
Comprehensive validation functions for security operations
Author: System Security Team
Version: 2.0.0
"""

import re
import hashlib
import ipaddress
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied
import logging

from .models import IPBlacklist, ThreatIntelligence, DeviceInfo, TrustedDevice, PasswordHistory
from .vpn_detector import VPNDetector, VPNServiceError
from api.security.models import SecurityLog
# DeviceInfo stub — replace with real import if available
try:
    from api.security.models import DeviceInfo
except ImportError:
    class DeviceInfo:
        pass



User = get_user_model()

logger = logging.getLogger(__name__)


class SecurityValidationError(ValidationError):
    """Custom validation error for security operations"""
    pass


class SecurityPermissionDenied(PermissionDenied):
    """Custom permission denied error for security operations"""
    pass


def validate_password_strength(password, user=None):
    """
    Validate password strength according to security policy
    
    Args:
        password (str): Password to validate
        user (User, optional): User context for validation
    
    Returns:
        dict: Validation result with strength score and recommendations
    
    Raises:
        SecurityValidationError: If password doesn't meet minimum requirements
    """
    if not password:
        raise SecurityValidationError("Password cannot be empty")
    
    # Get password policy settings
    policy = get_password_policy()
    min_length = policy.get('min_length', 8)
    max_length = policy.get('max_length', 128)
    
    # Basic length validation
    if len(password) < min_length:
        raise SecurityValidationError(f"Password must be at least {min_length} characters long")
    
    if len(password) > max_length:
        raise SecurityValidationError(f"Password cannot exceed {max_length} characters")
    
    # Initialize validation results
    validation_result = {
        'is_valid': True,
        'strength_score': 0,
        'warnings': [],
        'recommendations': [],
        'failed_requirements': []
    }
    
    # Check character requirements
    has_uppercase = bool(re.search(r'[A-Z]', password))
    has_lowercase = bool(re.search(r'[a-z]', password))
    has_numbers = bool(re.search(r'\d', password))
    has_special_chars = bool(re.search(r'[!@#$%^&*()_+\-=\[\]{};:"\\|,.<>\/?]', password))
    
    # Validate required character types
    if policy.get('require_uppercase', True) and not has_uppercase:
        validation_result['failed_requirements'].append('uppercase_letter')
        validation_result['is_valid'] = False
    
    if policy.get('require_lowercase', True) and not has_lowercase:
        validation_result['failed_requirements'].append('lowercase_letter')
        validation_result['is_valid'] = False
    
    if policy.get('require_numbers', True) and not has_numbers:
        validation_result['failed_requirements'].append('number')
        validation_result['is_valid'] = False
    
    if policy.get('require_special_chars', True) and not has_special_chars:
        validation_result['failed_requirements'].append('special_character')
        validation_result['is_valid'] = False
    
    # Calculate strength score (0-100)
    strength_score = 0
    
    # Length contribution (0-30 points)
    length_score = min(len(password) / max_length * 30, 30)
    strength_score += length_score
    
    # Character variety contribution (0-40 points)
    char_variety_score = 0
    if has_uppercase:
        char_variety_score += 10
    if has_lowercase:
        char_variety_score += 10
    if has_numbers:
        char_variety_score += 10
    if has_special_chars:
        char_variety_score += 10
    strength_score += char_variety_score
    
    # Complexity contribution (0-30 points)
    complexity_score = 0
    
    # Check for sequential characters
    if not has_sequential_chars(password):
        complexity_score += 10
    
    # Check for repeated characters
    if not has_repeated_chars(password):
        complexity_score += 10
    
    # Check for common patterns
    if not has_common_patterns(password):
        complexity_score += 10
    
    strength_score += complexity_score
    
    validation_result['strength_score'] = int(strength_score)
    
    # Determine strength level
    if strength_score >= 80:
        strength_level = 'very_strong'
    elif strength_score >= 60:
        strength_level = 'strong'
    elif strength_score >= 40:
        strength_level = 'medium'
    elif strength_score >= 20:
        strength_level = 'weak'
    else:
        strength_level = 'very_weak'
    
    validation_result['strength_level'] = strength_level
    
    # Generate recommendations
    if not has_uppercase:
        validation_result['recommendations'].append('Add uppercase letters')
    if not has_lowercase:
        validation_result['recommendations'].append('Add lowercase letters')
    if not has_numbers:
        validation_result['recommendations'].append('Add numbers')
    if not has_special_chars:
        validation_result['recommendations'].append('Add special characters')
    
    if len(password) < 12:
        validation_result['recommendations'].append('Use a longer password (12+ characters)')
    
    if has_sequential_chars(password):
        validation_result['warnings'].append('Contains sequential characters')
    
    if has_repeated_chars(password):
        validation_result['warnings'].append('Contains repeated characters')
    
    if has_common_patterns(password):
        validation_result['warnings'].append('Contains common patterns')
    
    # Check against password history if user provided
    if user and policy.get('prevent_reuse', True):
        reuse_limit = policy.get('reuse_limit', 12)
        if is_password_reused(password, user, reuse_limit):
            validation_result['is_valid'] = False
            validation_result['failed_requirements'].append('password_reuse')
            validation_result['recommendations'].append('Use a new password (not used in recent history)')
    
    # Check if password contains username
    if user and user.username.lower() in password.lower():
        validation_result['warnings'].append('Password contains username')
        if policy.get('no_username_inclusion', True):
            validation_result['is_valid'] = False
            validation_result['failed_requirements'].append('username_inclusion')
    
    # Final validation
    if not validation_result['is_valid']:
        error_message = f"Password validation failed: {', '.join(validation_result['failed_requirements'])}"
        raise SecurityValidationError(error_message)
    
    return validation_result


def validate_ip_not_blocked(ip_address, user=None, request=None):
    """
    Validate that IP address is not blocked or suspicious
    
    Args:
        ip_address (str): IP address to validate
        user (User, optional): User context
        request: HTTP request context
    
    Returns:
        dict: Validation result with IP reputation and risk assessment
    
    Raises:
        SecurityPermissionDenied: If IP is blocked or high-risk
    """
    if not ip_address:
        raise SecurityValidationError("IP address is required")
    
    try:
        # Validate IP address format
        ip_obj = ipaddress.ip_address(ip_address)
    except ValueError:
        raise SecurityValidationError(f"Invalid IP address format: {ip_address}")
    
    # Initialize validation result
    validation_result = {
        'is_valid': True,
        'is_blocked': False,
        'risk_level': 'low',
        'risk_score': 0,
        'warnings': [],
        'threat_intelligence': None,
        'vpn_detected': False,
        'proxy_detected': False,
        'country_restriction': False
    }
    
    # Check against IP blacklist
    blacklist_entry = IPBlacklist.objects.filter(
        ip_address=ip_address,
        is_active=True
    ).first()
    
    if blacklist_entry:
        validation_result['is_blocked'] = True
        validation_result['risk_level'] = 'critical'
        validation_result['risk_score'] = 100
        validation_result['warnings'].append(f"IP is blacklisted: {blacklist_entry.reason}")
        
        # Check if blacklist entry is expired
        if blacklist_entry.expires_at and blacklist_entry.expires_at < timezone.now():
            validation_result['warnings'].append("Blacklist entry is expired")
        else:
            raise SecurityPermissionDenied(f"IP address {ip_address} is blocked: {blacklist_entry.reason}")
    
    # Check threat intelligence
    threat_entry = ThreatIntelligence.objects.filter(
        indicators__contains=[ip_address],
        is_active=True,
        expires_at__gt=timezone.now()
    ).first()
    
    if threat_entry:
        validation_result['threat_intelligence'] = {
            'threat_type': threat_entry.threat_type,
            'severity': threat_entry.severity,
            'confidence': threat_entry.confidence,
            'source': threat_entry.source,
            'description': threat_entry.description
        }
        
        # Adjust risk score based on threat intelligence
        if threat_entry.severity == 'critical':
            validation_result['risk_level'] = 'critical'
            validation_result['risk_score'] = 90
        elif threat_entry.severity == 'high':
            validation_result['risk_level'] = 'high'
            validation_result['risk_score'] = 70
        elif threat_entry.severity == 'medium':
            validation_result['risk_level'] = 'medium'
            validation_result['risk_score'] = 50
        else:
            validation_result['risk_level'] = 'low'
            validation_result['risk_score'] = 30
        
        validation_result['warnings'].append(f"IP found in threat intelligence: {threat_entry.threat_type}")
        
        # Block if high confidence threat
        if threat_entry.confidence >= 0.8 and threat_entry.severity in ['critical', 'high']:
            raise SecurityPermissionDenied(f"IP address {ip_address} is flagged as high threat: {threat_entry.threat_type}")
    
    # Check for VPN/Proxy usage
    try:
        vpn_detector = VPNDetector()
        vpn_result = vpn_detector.is_vpn(ip_address, include_details=True)
        
        if vpn_result.get('is_vpn'):
            validation_result['vpn_detected'] = True
            validation_result['risk_level'] = 'medium'
            validation_result['risk_score'] = max(validation_result['risk_score'], 40)
            validation_result['warnings'].append("VPN detected")
        
        if vpn_result.get('is_proxy'):
            validation_result['proxy_detected'] = True
            validation_result['risk_level'] = 'medium'
            validation_result['risk_score'] = max(validation_result['risk_score'], 40)
            validation_result['warnings'].append("Proxy detected")
        
        # Store VPN/proxy details
        if vpn_result.get('details'):
            validation_result['vpn_details'] = vpn_result['details']
    
    except VPNServiceError as e:
        logger.warning(f"VPN detection failed for IP {ip_address}: {str(e)}")
        validation_result['warnings'].append("VPN detection service unavailable")
    
    # Check country restrictions
    if request and hasattr(request, 'META'):
        country = request.META.get('HTTP_CF_IPCOUNTRY') or request.META.get('HTTP_X_COUNTRY_CODE')
        if country:
            from .models import CountryBlockRule
            country_block = CountryBlockRule.objects.filter(
                country_code=country.upper(),
                is_active=True
            ).first()
            
            if country_block:
                validation_result['country_restriction'] = True
                validation_result['risk_level'] = 'high'
                validation_result['risk_score'] = max(validation_result['risk_score'], 80)
                validation_result['warnings'].append(f"Country {country} is blocked: {country_block.reason}")
                
                if not country_block.expires_at or country_block.expires_at > timezone.now():
                    raise SecurityPermissionDenied(f"Access from country {country} is blocked")
    
    # Check for suspicious patterns
    if is_private_ip(ip_address):
        validation_result['warnings'].append("Private IP address")
        validation_result['risk_score'] = max(validation_result['risk_score'], 20)
    
    if is_loopback_ip(ip_address):
        validation_result['warnings'].append("Loopback IP address")
        validation_result['risk_score'] = max(validation_result['risk_score'], 10)
    
    # Check recent security events from this IP
    from .models import SecurityLog
    recent_events = SecurityLog.objects.filter(
        ip_address=ip_address,
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).count()
    
    if recent_events > 100:
        validation_result['warnings'].append(f"High activity from IP: {recent_events} events in 24h")
        validation_result['risk_level'] = 'medium'
        validation_result['risk_score'] = max(validation_result['risk_score'], 45)
    
    # Check for failed login attempts from this IP
    failed_logins = SecurityLog.objects.filter(
        ip_address=ip_address,
        security_type='login_failure',
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).count()
    
    if failed_logins > 10:
        validation_result['warnings'].append(f"High failed login attempts: {failed_logins} in 1h")
        validation_result['risk_level'] = 'high'
        validation_result['risk_score'] = max(validation_result['risk_score'], 65)
    
    # Final assessment
    if validation_result['risk_score'] >= 80:
        validation_result['is_valid'] = False
        raise SecurityPermissionDenied(f"IP address {ip_address} is considered high risk")
    
    return validation_result


def validate_device_trusted(device_fingerprint, user=None, request=None):
    """
    Validate that device is trusted and not compromised
    
    Args:
        device_fingerprint (str): Device fingerprint to validate
        user (User, optional): User context
        request: HTTP request context
    
    Returns:
        dict: Validation result with device trust assessment
    
    Raises:
        SecurityPermissionDenied: If device is untrusted or suspicious
    """
    if not device_fingerprint:
        raise SecurityValidationError("Device fingerprint is required")
    
    # Initialize validation result
    validation_result = {
        'is_valid': True,
        'is_trusted': False,
        'trust_level': 'unknown',
        'trust_score': 0,
        'warnings': [],
        'device_info': None,
        'security_issues': []
    }
    
    # Get device information
    try:
        device_info = DeviceInfo.objects.filter(
            device_fingerprint=device_fingerprint
        ).first()
        
        if not device_info:
            validation_result['warnings'].append("Unknown device")
            validation_result['trust_level'] = 'unknown'
            validation_result['trust_score'] = 0
            return validation_result
        
        validation_result['device_info'] = {
            'id': str(device_info.id),
            'device_name': device_info.device_name,
            'device_type': device_info.device_type,
            'platform': device_info.platform,
            'browser': device_info.browser,
            'ip_address': device_info.ip_address,
            'created_at': device_info.created_at.isoformat(),
            'last_seen_at': device_info.last_seen_at.isoformat() if device_info.last_seen_at else None
        }
        
        # Check if device is trusted
        trusted_device = TrustedDevice.objects.filter(
            user=user,
            device_fingerprint=device_fingerprint,
            is_trusted=True
        ).first()
        
        if trusted_device:
            validation_result['is_trusted'] = True
            validation_result['trust_score'] = trusted_device.trust_score
            
            if trusted_device.trust_score >= 80:
                validation_result['trust_level'] = 'high'
            elif trusted_device.trust_score >= 50:
                validation_result['trust_level'] = 'medium'
            else:
                validation_result['trust_level'] = 'low'
            
            # Check if trust has expired
            if trusted_device.expires_at and trusted_device.expires_at < timezone.now():
                validation_result['warnings'].append("Device trust has expired")
                validation_result['trust_level'] = 'expired'
                validation_result['is_trusted'] = False
        else:
            validation_result['warnings'].append("Device is not trusted")
            validation_result['trust_level'] = 'untrusted'
            validation_result['trust_score'] = 0
    
    except Exception as e:
        logger.error(f"Error validating device {device_fingerprint}: {str(e)}")
        validation_result['warnings'].append("Error retrieving device information")
    
    # Check for suspicious device patterns
    if device_info:
        # Check if device has multiple users (suspicious)
        user_count = DeviceInfo.objects.filter(
            device_fingerprint=device_fingerprint
        ).values('user_id').distinct().count()
        
        if user_count > 3:
            validation_result['security_issues'].append(f"Device used by {user_count} different users")
            validation_result['trust_score'] = max(validation_result['trust_score'] - 30, 0)
        
        # Check for recent activity from multiple IPs
        recent_ips = SecurityLog.objects.filter(
            user=device_info.user,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).values('ip_address').distinct().count()
        
        if recent_ips > 5:
            validation_result['security_issues'].append(f"Device used from {recent_ips} different IPs recently")
            validation_result['trust_score'] = max(validation_result['trust_score'] - 20, 0)
        
        # Check device age
        if device_info.created_at > timezone.now() - timedelta(hours=24):
            validation_result['warnings'].append("New device (less than 24 hours old)")
            validation_result['trust_score'] = max(validation_result['trust_score'] - 10, 0)
        
        # Check last seen time
        if device_info.last_seen_at:
            days_since_last_seen = (timezone.now() - device_info.last_seen_at).days
            if days_since_last_seen > 30:
                validation_result['warnings'].append(f"Device not seen for {days_since_last_seen} days")
                validation_result['trust_score'] = max(validation_result['trust_score'] - 15, 0)
    
    # Check IP address associated with device
    if device_info and device_info.ip_address:
        try:
            ip_validation = validate_ip_not_blocked(device_info.ip_address, user, request)
            if not ip_validation['is_valid']:
                validation_result['security_issues'].append("Device IP is blocked or suspicious")
                validation_result['trust_score'] = max(validation_result['trust_score'] - 40, 0)
        except SecurityPermissionDenied:
            validation_result['security_issues'].append("Device IP is blocked")
            validation_result['trust_score'] = max(validation_result['trust_score'] - 60, 0)
    
    # Final assessment
    if validation_result['trust_score'] < 30:
        validation_result['is_valid'] = False
        raise SecurityPermissionDenied(f"Device {device_fingerprint} is not trusted")
    
    return validation_result


# ==================== HELPER FUNCTIONS ====================

def get_password_policy():
    """Get password policy from settings or use defaults"""
    return getattr(settings, 'PASSWORD_POLICY', {
        'min_length': 8,
        'max_length': 128,
        'require_uppercase': True,
        'require_lowercase': True,
        'require_numbers': True,
        'require_special_chars': True,
        'prevent_reuse': True,
        'reuse_limit': 12,
        'no_username_inclusion': True
    })


def has_sequential_chars(password):
    """Check if password contains sequential characters"""
    for i in range(len(password) - 2):
        if ord(password[i+1]) == ord(password[i]) + 1 and ord(password[i+2]) == ord(password[i]) + 2:
            return True
    return False


def has_repeated_chars(password):
    """Check if password contains repeated characters"""
    for i in range(len(password) - 2):
        if password[i] == password[i+1] == password[i+2]:
            return True
    return False


def has_common_patterns(password):
    """Check if password contains common patterns"""
    common_patterns = [
        '123', 'abc', 'qwe', 'asd', 'zxc', 'password', 'admin',
        'user', 'login', 'welcome', 'qwerty', 'letmein'
    ]
    
    password_lower = password.lower()
    for pattern in common_patterns:
        if pattern in password_lower:
            return True
    return False


def is_password_reused(password, user, reuse_limit):
    """Check if password has been used recently"""
    if not user:
        return False
    
    # Hash the password to compare with stored hashes
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # Check recent password history
    recent_passwords = PasswordHistory.objects.filter(
        user=user
    ).order_by('-created_at')[:reuse_limit]
    
    for pwd_history in recent_passwords:
        if pwd_history.password_hash == password_hash:
            return True
    
    return False


def is_private_ip(ip_address):
    """Check if IP address is private"""
    try:
        ip_obj = ipaddress.ip_address(ip_address)
        return ip_obj.is_private
    except ValueError:
        return False


def is_loopback_ip(ip_address):
    """Check if IP address is loopback"""
    try:
        ip_obj = ipaddress.ip_address(ip_address)
        return ip_obj.is_loopback
    except ValueError:
        return False


# ==================== COMPOSITE VALIDATORS ====================

def validate_security_context(user, request, require_trusted_device=False):
    """
    Comprehensive security validation for user and request context
    
    Args:
        user (User): User to validate
        request: HTTP request context
        require_trusted_device (bool): Whether to require trusted device
    
    Returns:
        dict: Comprehensive validation result
    
    Raises:
        SecurityPermissionDenied: If security validation fails
    """
    validation_result = {
        'is_valid': True,
        'user_valid': True,
        'ip_valid': True,
        'device_valid': True,
        'overall_risk_score': 0,
        'warnings': [],
        'security_issues': []
    }
    
    # Validate user
    if not user or not user.is_active:
        validation_result['user_valid'] = False
        validation_result['security_issues'].append("User is invalid or inactive")
        raise SecurityPermissionDenied("User validation failed")
    
    # Validate IP address
    ip_address = get_client_ip(request)
    if ip_address:
        try:
            ip_validation = validate_ip_not_blocked(ip_address, user, request)
            validation_result['ip_valid'] = ip_validation['is_valid']
            validation_result['overall_risk_score'] += ip_validation['risk_score']
            validation_result['warnings'].extend(ip_validation['warnings'])
        except SecurityPermissionDenied:
            validation_result['ip_valid'] = False
            validation_result['security_issues'].append("IP validation failed")
            raise
    
    # Validate device if required
    if require_trusted_device:
        device_fingerprint = get_device_fingerprint(request)
        if device_fingerprint:
            try:
                device_validation = validate_device_trusted(device_fingerprint, user, request)
                validation_result['device_valid'] = device_validation['is_valid']
                validation_result['overall_risk_score'] += (100 - device_validation['trust_score'])
                validation_result['warnings'].extend(device_validation['warnings'])
                validation_result['security_issues'].extend(device_validation['security_issues'])
            except SecurityPermissionDenied:
                validation_result['device_valid'] = False
                validation_result['security_issues'].append("Device validation failed")
                raise
        else:
            validation_result['device_valid'] = False
            validation_result['security_issues'].append("No device fingerprint available")
    
    # Final assessment
    if validation_result['overall_risk_score'] > 150:
        validation_result['is_valid'] = False
        raise SecurityPermissionDenied("Security context validation failed - high risk")
    
    return validation_result


def get_client_ip(request):
    """Extract client IP address from request"""
    if not request:
        return None
    
    # Check various headers for real IP
    ip_headers = [
        'HTTP_X_FORWARDED_FOR',
        'HTTP_X_REAL_IP',
        'HTTP_CLIENT_IP',
        'REMOTE_ADDR'
    ]
    
    for header in ip_headers:
        ip = request.META.get(header)
        if ip:
            # Handle multiple IPs in X-Forwarded-For
            if ',' in ip:
                ip = ip.split(',')[0].strip()
            return ip
    
    return None


def get_device_fingerprint(request):
    """Generate device fingerprint from request"""
    if not request:
        return None
    
    # Basic fingerprint components
    components = [
        request.META.get('HTTP_USER_AGENT', ''),
        request.META.get('HTTP_ACCEPT', ''),
        request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
        request.META.get('HTTP_ACCEPT_ENCODING', ''),
    ]
    
    # Create fingerprint
    fingerprint_data = '|'.join(components)
    fingerprint = hashlib.sha256(fingerprint_data.encode()).hexdigest()
    
    return fingerprint