"""
Advanced Device Fingerprinting System
Detects and tracks devices to prevent multi-account fraud
"""
import hashlib
import json
import logging
from typing import Dict, Optional, Tuple
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


class DeviceFingerprinting:
    """
    Advanced device fingerprinting for fraud detection
    
    Tracks:
    - Device hardware fingerprint
    - Browser fingerprint
    - Canvas fingerprint
    - WebGL fingerprint
    - Audio fingerprint
    - Screen resolution and characteristics
    - Installed fonts
    - Timezone and language
    - Platform and OS details
    """
    
    CACHE_PREFIX = 'device_fp:'
    CACHE_TIMEOUT = 3600  # 1 hour
    
    # Suspicious device thresholds
    MAX_ACCOUNTS_PER_DEVICE = 1  # Maximum accounts allowed per device
    MAX_REGISTRATIONS_PER_HOUR = 3  # Maximum registrations from same device per hour
    
    def __init__(self, request_data: Dict = None):
        """
        Initialize device fingerprinting
        
        Args:
            request_data: Request data containing device information
        """
        self.request_data = request_data or {}
        self.device_hash = None
        self.fingerprint_data = {}
    
    def generate_device_hash(self, device_data: Dict) -> str:
        """
        Generate unique device hash from device characteristics
        
        Args:
            device_data: Dictionary containing device information
        
        Returns:
            Unique device hash string
        """
        # Extract key device identifiers
        identifiers = [
            device_data.get('device_id', ''),
            device_data.get('user_agent', ''),
            device_data.get('screen_resolution', ''),
            device_data.get('timezone', ''),
            device_data.get('platform', ''),
            device_data.get('canvas_fingerprint', ''),
            device_data.get('webgl_fingerprint', ''),
            device_data.get('audio_fingerprint', ''),
            str(device_data.get('cpu_cores', '')),
            str(device_data.get('device_memory', '')),
            str(device_data.get('max_touch_points', '')),
            device_data.get('languages', ''),
        ]
        
        # Create composite string
        composite = '|'.join(str(i) for i in identifiers if i)
        
        # Generate SHA-256 hash
        device_hash = hashlib.sha256(composite.encode('utf-8')).hexdigest()
        
        self.device_hash = device_hash
        return device_hash
    
    def extract_fingerprint_data(self, request) -> Dict:
        """
        Extract comprehensive fingerprint data from request
        
        Args:
            request: Django request object
        
        Returns:
            Dictionary of fingerprint data
        """
        # Get IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR', '')
        
        # Extract from request data
        data = request.data if hasattr(request, 'data') else {}
        
        fingerprint = {
            # Basic identifiers
            'device_id': data.get('device_id', ''),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'ip_address': ip_address,
            
            # Browser fingerprint
            'platform': data.get('platform', ''),
            'browser': data.get('browser', ''),
            'browser_version': data.get('browser_version', ''),
            'os': data.get('os', ''),
            'os_version': data.get('os_version', ''),
            
            # Screen characteristics
            'screen_resolution': data.get('screen_resolution', ''),
            'screen_width': data.get('screen_width'),
            'screen_height': data.get('screen_height'),
            'color_depth': data.get('color_depth'),
            'pixel_ratio': data.get('pixel_ratio'),
            
            # Hardware
            'cpu_cores': data.get('cpu_cores'),
            'device_memory': data.get('device_memory'),
            'max_touch_points': data.get('max_touch_points'),
            
            # Advanced fingerprints
            'canvas_fingerprint': data.get('canvas_fingerprint', ''),
            'webgl_fingerprint': data.get('webgl_fingerprint', ''),
            'webgl_vendor': data.get('webgl_vendor', ''),
            'webgl_renderer': data.get('webgl_renderer', ''),
            'audio_fingerprint': data.get('audio_fingerprint', ''),
            
            # Locale and timezone
            'timezone': data.get('timezone', ''),
            'timezone_offset': data.get('timezone_offset'),
            'languages': data.get('languages', ''),
            'language': data.get('language', ''),
            
            # Fonts (if provided)
            'installed_fonts': data.get('installed_fonts', []),
            
            # Plugins and features
            'plugins': data.get('plugins', []),
            'do_not_track': data.get('do_not_track'),
            'ad_blocker': data.get('ad_blocker', False),
            
            # Mobile specific
            'is_mobile': data.get('is_mobile', False),
            'device_model': data.get('device_model', ''),
            'device_manufacturer': data.get('device_manufacturer', ''),
            
            # Additional metadata
            'battery_charging': data.get('battery_charging'),
            'battery_level': data.get('battery_level'),
            'connection_type': data.get('connection_type', ''),
        }
        
        self.fingerprint_data = fingerprint
        return fingerprint
    
    def check_device_exists(self, device_hash: str) -> Tuple[bool, Dict]:
        """
        Check if device already exists in system
        
        Args:
            device_hash: Device hash to check
        
        Returns:
            Tuple of (exists: bool, device_info: dict)
        """
        from api.fraud_detection.models import DeviceFingerprint
        
        try:
            devices = DeviceFingerprint.objects.filter(device_hash=device_hash)
            
            if devices.exists():
                device = devices.first()
                
                # Get associated users
                user_count = devices.values('user').distinct().count()
                
                device_info = {
                    'exists': True,
                    'device_id': str(device.id),
                    'user_count': user_count,
                    'first_seen': device.created_at,
                    'last_seen': device.last_seen,
                    'trust_score': device.trust_score,
                    'is_vpn': device.is_vpn,
                    'is_proxy': device.is_proxy,
                    'is_bot': device.is_bot,
                }
                
                return True, device_info
            
            return False, {}
        
        except Exception as e:
            logger.error(f"Error checking device: {e}")
            return False, {}
    
    def check_registration_rate(self, device_hash: str) -> Tuple[bool, int]:
        """
        Check registration rate from this device
        
        Args:
            device_hash: Device hash
        
        Returns:
            Tuple of (is_exceeded: bool, count: int)
        """
        cache_key = f"{self.CACHE_PREFIX}reg_rate:{device_hash}"
        
        # Get current count
        count = cache.get(cache_key, 0)
        
        # Check if exceeded
        is_exceeded = count >= self.MAX_REGISTRATIONS_PER_HOUR
        
        return is_exceeded, count
    
    def increment_registration_count(self, device_hash: str) -> int:
        """
        Increment registration counter for device
        
        Args:
            device_hash: Device hash
        
        Returns:
            New count
        """
        cache_key = f"{self.CACHE_PREFIX}reg_rate:{device_hash}"
        
        count = cache.get(cache_key, 0)
        count += 1
        
        # Cache for 1 hour
        cache.set(cache_key, count, 3600)
        
        return count
    
    def validate_device_for_registration(
        self, 
        request, 
        strict_mode: bool = True
    ) -> Tuple[bool, str, Dict]:
        """
        Validate device for new registration
        
        Args:
            request: Django request object
            strict_mode: If True, blocks any suspicious activity
        
        Returns:
            Tuple of (is_valid: bool, reason: str, details: dict)
        """
        # Extract fingerprint
        fingerprint = self.extract_fingerprint_data(request)
        
        # Generate device hash
        device_hash = self.generate_device_hash(fingerprint)
        
        # Check if device exists
        exists, device_info = self.check_device_exists(device_hash)
        
        if exists:
            # Check user count
            if device_info['user_count'] >= self.MAX_ACCOUNTS_PER_DEVICE:
                return False, 'DEVICE_LIMIT_REACHED', {
                    'device_hash': device_hash,
                    'user_count': device_info['user_count'],
                    'max_allowed': self.MAX_ACCOUNTS_PER_DEVICE,
                    'message': f"This device already has {device_info['user_count']} registered account(s). Maximum {self.MAX_ACCOUNTS_PER_DEVICE} allowed."
                }
            
            # Check trust score
            if strict_mode and device_info['trust_score'] < 50:
                return False, 'LOW_TRUST_SCORE', {
                    'device_hash': device_hash,
                    'trust_score': device_info['trust_score'],
                    'message': 'This device has a low trust score due to suspicious activity.'
                }
            
            # Check VPN/Proxy
            if strict_mode and (device_info['is_vpn'] or device_info['is_proxy']):
                return False, 'VPN_PROXY_DETECTED', {
                    'device_hash': device_hash,
                    'is_vpn': device_info['is_vpn'],
                    'is_proxy': device_info['is_proxy'],
                    'message': 'VPN or Proxy usage is not allowed during registration.'
                }
            
            # Check bot
            if device_info['is_bot']:
                return False, 'BOT_DETECTED', {
                    'device_hash': device_hash,
                    'message': 'Automated registration attempts are not allowed.'
                }
        
        # Check registration rate
        is_rate_exceeded, reg_count = self.check_registration_rate(device_hash)
        
        if is_rate_exceeded:
            return False, 'REGISTRATION_RATE_EXCEEDED', {
                'device_hash': device_hash,
                'count': reg_count,
                'max_allowed': self.MAX_REGISTRATIONS_PER_HOUR,
                'message': f'Too many registration attempts from this device. Please try again later.'
            }
        
        # All checks passed
        return True, 'VALID', {
            'device_hash': device_hash,
            'fingerprint': fingerprint,
            'is_new_device': not exists
        }
    
    def save_device_fingerprint(self, user, fingerprint_data: Dict) -> 'DeviceFingerprint':
        """
        Save device fingerprint to database
        
        Args:
            user: User instance
            fingerprint_data: Fingerprint data dictionary
        
        Returns:
            DeviceFingerprint instance
        """
        from api.fraud_detection.models import DeviceFingerprint
        
        device_hash = self.generate_device_hash(fingerprint_data)
        
        # Create or update device fingerprint
        device, created = DeviceFingerprint.objects.update_or_create(
            device_hash=device_hash,
            user=user,
            defaults={
                'device_id': fingerprint_data.get('device_id', ''),
                'user_agent': fingerprint_data.get('user_agent', ''),
                'platform': fingerprint_data.get('platform', ''),
                'browser': fingerprint_data.get('browser', ''),
                'browser_version': fingerprint_data.get('browser_version', ''),
                'os': fingerprint_data.get('os', ''),
                'os_version': fingerprint_data.get('os_version', ''),
                'screen_resolution': fingerprint_data.get('screen_resolution', ''),
                'language': fingerprint_data.get('language', ''),
                'timezone': fingerprint_data.get('timezone', ''),
                'cpu_cores': fingerprint_data.get('cpu_cores'),
                'device_memory': fingerprint_data.get('device_memory'),
                'max_touch_points': fingerprint_data.get('max_touch_points'),
                'canvas_fingerprint': fingerprint_data.get('canvas_fingerprint', ''),
                'webgl_fingerprint': fingerprint_data.get('webgl_fingerprint', ''),
                'audio_fingerprint': fingerprint_data.get('audio_fingerprint', ''),
                'ip_address': fingerprint_data.get('ip_address', ''),
                'is_mobile': fingerprint_data.get('is_mobile', False),
            }
        )
        
        # Increment registration count
        self.increment_registration_count(device_hash)
        
        logger.info(f"Device fingerprint saved: {device_hash} for user {user.id}")
        
        return device
    
    def calculate_similarity(self, fp1: Dict, fp2: Dict) -> float:
        """
        Calculate similarity score between two fingerprints
        
        Args:
            fp1: First fingerprint
            fp2: Second fingerprint
        
        Returns:
            Similarity score (0-100)
        """
        # Key fields to compare
        fields = [
            'user_agent', 'screen_resolution', 'timezone',
            'canvas_fingerprint', 'webgl_fingerprint', 'audio_fingerprint',
            'cpu_cores', 'device_memory', 'platform'
        ]
        
        matches = 0
        total = 0
        
        for field in fields:
            if field in fp1 and field in fp2:
                total += 1
                if fp1[field] == fp2[field]:
                    matches += 1
        
        if total == 0:
            return 0.0
        
        similarity = (matches / total) * 100
        return round(similarity, 2)
    
    @staticmethod
    def detect_vpn_proxy(ip_address: str) -> Tuple[bool, bool, Dict]:
        """
        Detect VPN/Proxy usage
        
        Args:
            ip_address: IP address to check
        
        Returns:
            Tuple of (is_vpn: bool, is_proxy: bool, details: dict)
        """
        # This would integrate with services like:
        # - IPHub
        # - ProxyCheck.io
        # - IPQualityScore
        # For now, basic implementation
        
        from api.fraud_detection.models import IPReputation
        
        try:
            ip_rep = IPReputation.objects.get(ip_address=ip_address)
            
            is_vpn = 'vpn' in ip_rep.threat_types
            is_proxy = 'proxy' in ip_rep.threat_types
            
            details = {
                'fraud_score': ip_rep.fraud_score,
                'threat_types': ip_rep.threat_types,
                'country': ip_rep.country,
                'isp': ip_rep.isp,
            }
            
            return is_vpn, is_proxy, details
        
        except IPReputation.DoesNotExist:
            # IP not in database, assume clean for now
            # In production, you'd call an external API here
            return False, False, {}
    
    def get_device_risk_score(self, device_hash: str) -> int:
        """
        Calculate risk score for device (0-100)
        
        Args:
            device_hash: Device hash
        
        Returns:
            Risk score (higher = more risky)
        """
        from api.fraud_detection.models import DeviceFingerprint, FraudAttempt
        
        risk_score = 0
        
        try:
            device = DeviceFingerprint.objects.get(device_hash=device_hash)
            
            # Check user count (multiple accounts)
            user_count = DeviceFingerprint.objects.filter(
                device_hash=device_hash
            ).values('user').distinct().count()
            
            if user_count > 1:
                risk_score += min(user_count * 20, 40)
            
            # Check VPN/Proxy
            if device.is_vpn or device.is_proxy:
                risk_score += 30
            
            # Check bot
            if device.is_bot:
                risk_score += 50
            
            # Check fraud attempts
            fraud_count = FraudAttempt.objects.filter(
                user=device.user,
                created_at__gte=timezone.now() - timedelta(days=30)
            ).count()
            
            risk_score += min(fraud_count * 10, 30)
            
            # Inverse trust score
            risk_score += (100 - device.trust_score) * 0.2
            
        except DeviceFingerprint.DoesNotExist:
            # New device - moderate risk
            risk_score = 30
        
        return min(int(risk_score), 100)
    
# api/users/services/device_fingerprint.py

class DeviceFingerprinting:
    # ... আপনার আগের সব কোড ...

    # আপনার ভিউতে 'generate_fingerprint' মেথডটি কল করা হয়েছে, 
    # তাই 'generate_device_hash' এর পরিবর্তে এটি যোগ করুন অথবা নাম পরিবর্তন করুন
    def generate_fingerprint(self, request, device_data):
        device_hash = self.generate_device_hash(device_data)
        # এখানে ডাটাবেস থেকে ডিভাইস অবজেক্টটি রিটার্ন করুন
        from api.users.models import DeviceFingerprint
        device, _ = DeviceFingerprint.objects.get_or_create(
            device_hash=device_hash,
            defaults={'device_id': device_data.get('device_id', '')}
        )
        return device

# এই লাইনটি ভিউ এর ইমপোর্ট এরর দূর করবে
device_fingerprint_service = DeviceFingerprinting()