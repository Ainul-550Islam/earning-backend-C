"""
Enhanced Trusted Device Service with comprehensive security model integration
Author: System Security Team
Version: 2.0.0

Advanced device fingerprinting, trust management, and security analytics.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from ..models import TrustedDevice
from ..utils.cache_manager import CacheManager, handle_gracefully

logger = logging.getLogger(__name__)


class TrustedDeviceService:
    """
    Service for managing trusted devices with defensive coding patterns
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_service_instance(cls):
        """Get singleton instance of the service"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        """Initialize service with cache manager"""
        self.cache_manager = CacheManager.get_instance()
        self.logger = logging.getLogger(__name__)
    
    @handle_gracefully(default_return=None)
    def register_device(self, user, device_fingerprint: str, device_name: str = None,
                   platform: str = None, browser: str = None, 
                   ip_address: str = None, user_agent: str = None,
                   location: Dict[str, Any] = None) -> Optional[TrustedDevice]:
        """
        Register a new trusted device for a user
        """
        try:
            # Check if device already exists
            existing_device = TrustedDevice.objects.filter(
                user=user,
                device_fingerprint=device_fingerprint
            ).first()
            
            if existing_device:
                # Update existing device
                if device_name:
                    existing_device.device_name = device_name
                if platform:
                    existing_device.platform = platform
                if browser:
                    existing_device.browser = browser
                if ip_address:
                    existing_device.ip_address = ip_address
                if user_agent:
                    existing_device.user_agent = user_agent
                if location:
                    existing_device.location = location
                
                existing_device.last_seen = timezone.now()
                existing_device.save()
                
                self.logger.info(f"Updated existing trusted device: {existing_device.device_name}")
                return existing_device
            
            # Create new trusted device
            device = TrustedDevice.objects.create(
                user=user,
                device_fingerprint=device_fingerprint,
                device_name=device_name or "Unknown Device",
                platform=platform or "",
                browser=browser or "",
                ip_address=ip_address,
                user_agent=user_agent or "",
                location=location or {},
                trust_score=50.0,  # Default trust score
                is_trusted=False,  # Requires manual verification
                expires_at=timezone.now() + timedelta(days=30)  # 30 days expiry
            )
            
            self.logger.info(f"Registered new trusted device: {device.device_name} for user {user.username}")
            return device
            
        except Exception as e:
            self.logger.error(f"Error registering trusted device: {e}")
            return None
    
    @handle_gracefully(default_return=[])
    def get_user_trusted_devices(self, user, active_only: bool = True) -> List[TrustedDevice]:
        """
        Get all trusted devices for a user
        """
        try:
            cache_key = f"user_trusted_devices_{user.id}"
            cached_result = self.cache_manager.get(cache_key)
            
            if cached_result is not None:
                return cached_result
            
            queryset = TrustedDevice.objects.filter(user=user)
            
            if active_only:
                queryset = queryset.filter(is_active=True, is_trusted=True)
            
            devices = list(queryset.order_by('-last_seen'))
            
            # Cache for 15 minutes
            self.cache_manager.set(cache_key, devices, timeout=900)
            
            return devices
            
        except Exception as e:
            self.logger.error(f"Error getting trusted devices: {e}")
            return []
    
    @handle_gracefully(default_return=False)
    def update_trust_score(self, device_id: int, trust_score: float) -> bool:
        """
        Update trust score for a device
        """
        try:
            device = TrustedDevice.objects.get(id=device_id)
            return device.update_trust_score(trust_score)
            
        except TrustedDevice.DoesNotExist:
            self.logger.error(f"Device not found: {device_id}")
            return False
        except Exception as e:
            self.logger.error(f"Error updating trust score: {e}")
            return False
    
    @handle_gracefully(default_return=False)
    def revoke_trust(self, device_id: int, reason: str = "") -> bool:
        """
        Revoke trust from a device
        """
        try:
            device = TrustedDevice.objects.get(id=device_id)
            device.is_trusted = False
            device.trust_score = 0.0
            device.expires_at = timezone.now()  # Expire immediately
            
            # Add reason to security flags
            if not device.security_flags:
                device.security_flags = {}
            
            device.security_flags['trust_revoked'] = {
                'reason': reason,
                'revoked_at': timezone.now().isoformat(),
                'revoked_by': 'system'
            }
            
            device.save()
            
            # Clear cache
            cache_key = f"user_trusted_devices_{device.user.id}"
            self.cache_manager.delete(cache_key)
            
            self.logger.info(f"Revoked trust for device: {device.device_name}")
            return True
            
        except TrustedDevice.DoesNotExist:
            self.logger.error(f"Device not found: {device_id}")
            return False
        except Exception as e:
            self.logger.error(f"Error revoking trust: {e}")
            return False
    
    @handle_gracefully(default_return=False)
    def verify_device_fingerprint(self, device_fingerprint: str, user_id: int = None) -> Dict[str, Any]:
        """
        Verify device fingerprint against known patterns
        """
        try:
            result = {
                'fingerprint': device_fingerprint,
                'is_known': False,
                'trust_score': 0.0,
                'risk_level': 'unknown',
                'recommendations': []
            }
            
            # Check if fingerprint exists in trusted devices
            if user_id:
                trusted_device = TrustedDevice.objects.filter(
                    device_fingerprint=device_fingerprint,
                    user_id=user_id,
                    is_trusted=True
                ).first()
                
                if trusted_device:
                    result.update({
                        'is_known': True,
                        'trust_score': float(trusted_device.trust_score),
                        'risk_level': 'low' if trusted_device.trust_score >= 80 else 'medium',
                        'device_name': trusted_device.device_name,
                        'last_seen': trusted_device.last_seen.isoformat(),
                        'recommendations': ['Device is trusted and verified']
                    })
            
            # Check for suspicious patterns
            suspicious_patterns = self._check_suspicious_patterns(device_fingerprint)
            if suspicious_patterns:
                result.update({
                    'risk_level': 'high',
                    'recommendations': ['Device fingerprint contains suspicious patterns']
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error verifying device fingerprint: {e}")
            return {'error': str(e)}
    
    def _check_suspicious_patterns(self, fingerprint: str) -> List[str]:
        """
        Check for suspicious patterns in device fingerprint
        """
        try:
            patterns = []
            
            # Common emulator/simulator patterns
            emulator_indicators = [
                'emulator', 'simulator', 'android_x86', 'nox', 'genymotion',
                'bluestacks', 'memu', 'qemu'
            ]
            
            # Common bot/automation patterns
            bot_indicators = [
                'selenium', 'webdriver', 'headless', 'phantomjs',
                'puppeteer', 'playwright'
            ]
            
            # Check for patterns
            fingerprint_lower = fingerprint.lower()
            
            for indicator in emulator_indicators:
                if indicator in fingerprint_lower:
                    patterns.append(f"Emulator/Simulator detected: {indicator}")
            
            for indicator in bot_indicators:
                if indicator in fingerprint_lower:
                    patterns.append(f"Bot/Automation detected: {indicator}")
            
            return patterns
            
        except Exception as e:
            self.logger.error(f"Error checking suspicious patterns: {e}")
            return []
    
    @handle_gracefully(default_return=0)
    def cleanup_expired_devices(self) -> int:
        """
        Clean up expired trusted devices
        """
        try:
            expired_count = TrustedDevice.objects.filter(
                expires_at__lt=timezone.now(),
                is_active=True
            ).update(is_active=False)
            
            self.logger.info(f"Cleaned up {expired_count} expired trusted devices")
            return expired_count
            
        except Exception as e:
            self.logger.error(f"Error cleaning up expired devices: {e}")
            return 0
    
    @handle_gracefully(default_return={})
    def get_device_statistics(self, user_id: int = None) -> Dict[str, Any]:
        """
        Get statistics about trusted devices
        """
        try:
            base_queryset = TrustedDevice.objects.all()
            
            if user_id:
                base_queryset = base_queryset.filter(user_id=user_id)
            
            stats = {
                'total_devices': base_queryset.count(),
                'trusted_devices': base_queryset.filter(is_trusted=True).count(),
                'active_devices': base_queryset.filter(is_active=True).count(),
                'expired_devices': base_queryset.filter(
                    expires_at__lt=timezone.now(),
                    is_active=True
                ).count(),
                'high_trust_devices': base_queryset.filter(
                    trust_score__gte=80,
                    is_trusted=True
                ).count(),
                'devices_by_type': {}
            }
            
            # Device type breakdown
            for device_type in ['desktop', 'mobile', 'tablet', 'tv', 'unknown']:
                count = base_queryset.filter(device_type=device_type).count()
                stats['devices_by_type'][device_type] = count
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting device statistics: {e}")
            return {'error': str(e)}