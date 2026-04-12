"""
Enhanced Security Models with Defensive Coding Practices
Author: System Security Team
Version: 2.0.0
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q, F, Sum, Count, Avg
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.hashers import make_password, check_password
from django.db.models.signals import pre_save
from django.db import models
from django.conf import settings
from django.utils import timezone
from typing import Optional, Tuple
from datetime import datetime, timedelta
from django.core.cache import cache
from django.db.models import Q, Index
from typing import Optional, Dict, Any, List
import hashlib
import logging
import json
import uuid
import re
import ipaddress
from decimal import Decimal, ROUND_HALF_UP
import secrets
import string
import base64
import hmac
from cryptography.fernet import Fernet
import phonenumbers
import geoip2.database
from urllib.parse import urlparse
import socket
from django.db import models, transaction
from django.db.models import Q, Count
from django.db.models.signals import post_save, pre_save
from typing import Optional, Dict, Any, List, Tuple, Union
from datetime import timedelta

# ডিফল্ট ভ্যালুর জন্য ফাংশন
def get_hours_default():
    return list(range(0, 24))

def get_default_days():
    return list(range(0, 7))

# ভ্যালিডেশন রুলসের জন্য ফাংশন
def is_positive_int(v):
    return isinstance(v, int) and v > 0

def is_min_6(v):
    return isinstance(v, int) and v >= 6

def is_bool(v):
    return isinstance(v, bool)

logger = logging.getLogger(__name__)



# ==================== DEFENSIVE CODING UTILITIES ====================

class NullSafe:
    """Null Object Pattern Implementation"""
    
    @staticmethod
    def get_safe(obj, attr: str, default=None):
        try:
            return getattr(obj, attr, default) if obj is not None else default
        except Exception:
            return default
    
    @staticmethod
    def dict_get_safe(data: dict, key: str, default=None):
        if not isinstance(data, dict):
            return default
        return data.get(key, default)
    
    @staticmethod
    def call_safe(func, *args, default=None, **kwargs):
        """Safely call a function"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Function call failed: {e}")
            return default


class GracefulDegradation:
    """Graceful degradation utilities"""
    
    @staticmethod
    def with_default(default_value):
        def decorator(func):
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"{func.__name__} failed: {e}", exc_info=True)
                    return default_value
            return wrapper
        return decorator


def cache_result(timeout: int = 300):
    """Cache decorator with fallback"""
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            if not self.pk:
                return func(self, *args, **kwargs)
            
            try:
                cache_key = f"device_{self.pk}_{func.__name__}"
                result = cache.get(cache_key)
                if result is not None:
                    return result
                
                result = func(self, *args, **kwargs)
                cache.set(cache_key, result, timeout)
                return result
            except Exception as e:
                logger.warning(f"Cache failed for {func.__name__}: {e}")
                return func(self, *args, **kwargs)  # Fallback
        return wrapper
    return decorator


# ==================== ENHANCED DEVICEINFO MODEL ====================

class DeviceInfo(models.Model):
    """Store device information for fraud detection"""
    
    # Trust level choices
    TRUST_LEVELS = [
        (1, 'Low Trust'),
        (2, 'Medium Trust'),
        (3, 'High Trust'),
    ]
    
    # Risk level choices
    RISK_LEVELS = [
        ('safe', '🟢 Safe'),
        ('low', '🟡 Low Risk'),
        ('medium', '🟠 Medium Risk'),
        ('high', '🔴 High Risk'),
        ('critical', '🚨 Critical'),
    ]
    
    # Database fields
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_devices',
        null=True,
        blank=True,
        db_index=True)
    device_id = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    device_id_hash = models.CharField(max_length=64, db_index=True, unique=True, null=True, blank=True)
    device_model = models.CharField(max_length=100, default="Unknown", null=True, blank=True)
    device_brand = models.CharField(max_length=100, blank=True, default="Unknown", null=True)
    android_version = models.CharField(max_length=50, default="Unknown", null=True, blank=True)
    app_version = models.CharField(max_length=20, default='1.0.0', null=True, blank=True)
    
    # Security flags
    is_rooted = models.BooleanField(default=False, db_index=True)
    is_emulator = models.BooleanField(default=False, db_index=True)
    is_vpn = models.BooleanField(default=False, db_index=True)
    is_proxy = models.BooleanField(default=False, db_index=True)
    is_trusted = models.BooleanField(default=False, db_index=True)
    
    # Network info
    last_ip = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    fingerprint = models.TextField(blank=True, default="")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity = models.DateTimeField(auto_now=True, db_index=True)
    
    # Risk assessment
    risk_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        db_index=True
    )
    trust_level = models.IntegerField(
        default=1,
        choices=TRUST_LEVELS,
        db_index=True
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = "Device Information"
        verbose_name_plural = "Device Information"
        ordering = ['-last_activity', '-created_at']
        indexes = [
            models.Index(fields=['device_id_hash', 'user']),
            models.Index(fields=['risk_score', '-last_activity']),
            models.Index(fields=['is_rooted', 'is_emulator', 'is_vpn']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'device_id_hash'],
                name='unique_user_device'
            ),
        ]
    
    def __str__(self) -> str:
        """Safe string representation"""
        try:
            username = NullSafe.get_safe(self.user, 'username', 'Anonymous')
            device = self.device_model or "Unknown Device"
            return f"{username} - {device}"
        except Exception:
            return f"Device {self.id or 'New'}"
    
    # ==================== SAVE METHODS ====================
    
    def save(self, *args, **kwargs):
        """Enhanced save with all validations"""
        try:
            with transaction.atomic():
                # Generate hash if needed
                if self.device_id and not self.device_id_hash:
                    self.device_id_hash = self._generate_device_hash(self.device_id)
                
                # Auto-calculate risk score if new
                if not self.pk:
                    self.risk_score = self._calculate_base_risk_score()
                
                # Validate data
                self.full_clean()
                
                # Clear cache
                self._clear_cache()
                
                # Save
                super().save(*args, **kwargs)
        except Exception as e:
            logger.error(f"Save failed for device {getattr(self, 'id', 'new')}: {e}")
            raise
    
    def _clear_cache(self):
        """Clear cached data"""
        if not self.pk:
            return
            
        try:
            # Delete specific cache keys
            cache_keys = [
                f"device_{self.pk}_get_risk_level",
                f"device_{self.pk}_get_risk_level_display",
                f"device_{self.pk}_get_security_flags",
                f"device_{self.pk}_is_suspicious",
                f"device_{self.pk}_get_trust_level_display",
            ]
            cache.delete_many(cache_keys)
        except Exception as e:
            logger.debug(f"Cache clear failed: {e}")
    
    # ==================== HASHING METHODS ====================
    
    def _generate_device_hash(self, device_id: str) -> str:
        """Generate secure hash for device ID"""
        try:
            salt = secrets.token_bytes(32)
            device_bytes = device_id.encode('utf-8')
            hash_input = salt + device_bytes
            return hashlib.sha256(hash_input).hexdigest()
        except Exception as e:
            logger.error(f"Hash generation failed: {e}")
            # Fallback to simple hash
            return hashlib.sha256(device_id.encode()).hexdigest()
    
    # ==================== VALIDATION ====================
    
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        errors = {}
        
        # Validate device_id length
        if self.device_id and len(self.device_id) > 255:
            errors['device_id'] = 'Device ID too long'
        
        # Validate risk score range
        if not 0 <= self.risk_score <= 100:
            errors['risk_score'] = 'Risk score must be between 0-100'
        
        # Validate IP address format
        if self.last_ip:
            try:
                ipaddress.ip_address(self.last_ip)
            except ValueError:
                errors['last_ip'] = 'Invalid IP address format'
        
        if errors:
            raise ValidationError(errors)
    
    # ==================== RISK CALCULATION ====================
    
    def _calculate_base_risk_score(self) -> int:
        """Calculate base risk score from device attributes"""
        score = 0
        
        # Device-based risks
        risk_factors = {
            'is_rooted': 30,
            'is_emulator': 25,
            'is_vpn': 20,
            'is_proxy': 15,
        }
        
        for attr, points in risk_factors.items():
            if getattr(self, attr, False):
                score += points
        
        return min(score, 100)
    
    @GracefulDegradation.with_default(0)
    def _get_recent_security_events(self, days: int = 7) -> int:
        """Get count of recent security events"""
        try:
            from .models import SecurityLog  # Lazy import
            
            return SecurityLog.objects.filter(
                device_info=self,
                created_at__gte=timezone.now() - timedelta(days=days)
            ).count()
        except Exception as e:
            logger.error(f"Failed to get security events: {e}")
            return 0
    
    def update_risk_score(self) -> bool:
        """Update risk score with all factors"""
        try:
            # Base score from device attributes
            score = self._calculate_base_risk_score()
            
            # Add points for recent security events
            event_count = self._get_recent_security_events()
            score += min(event_count * 2, 20)
            
            # Check for duplicates
            duplicate_count = DeviceInfo.check_duplicate_devices(
                self.device_id_hash,
                exclude_user=self.user
            )
            if duplicate_count > 0:
                score += min(duplicate_count * 5, 15)
            
            # Final score capped at 100
            new_score = min(score, 100)
            
            # Update if changed
            if new_score != self.risk_score:
                self.risk_score = new_score
                self.save(update_fields=['risk_score', 'updated_at'])
                logger.info(f"Risk score updated for {self.device_id_hash[:8]}: {new_score}")
                return True
            
            return False
                
        except Exception as e:
            logger.error(f"Risk score update failed: {e}")
            return False
    
    # ==================== STATUS METHODS ====================
    
    @cache_result(timeout=60)
    def get_risk_level(self) -> str:
        """Get risk level as string"""
        if self.risk_score >= 80:
            return 'critical'
        elif self.risk_score >= 60:
            return 'high'
        elif self.risk_score >= 40:
            return 'medium'
        elif self.risk_score >= 20:
            return 'low'
        return 'safe'
    
    @cache_result(timeout=60)
    def get_risk_level_display(self) -> str:
        """Get risk level with emoji"""
        risk_display = {
            'critical': '🚨 Critical',
            'high': '🔴 High',
            'medium': '🟠 Medium',
            'low': '🟡 Low',
            'safe': '🟢 Safe',
        }
        return risk_display.get(self.get_risk_level(), '⚪ Unknown')
    
    @cache_result(timeout=60)
    def get_security_flags(self) -> List[str]:
        """Get all active security flags"""
        flags = []
        
        if self.is_rooted:
            flags.append('ROOTED')
        if self.is_emulator:
            flags.append('EMULATOR')
        if self.is_vpn:
            flags.append('VPN')
        if self.is_proxy:
            flags.append('PROXY')
        if self.risk_score >= 70:
            flags.append('HIGH_RISK')
        if self.is_trusted:
            flags.append('TRUSTED')
        if self.trust_level == 3:
            flags.append('VERIFIED')
        
        return flags
    
    @cache_result(timeout=60)
    def is_suspicious(self) -> bool:
        """Check if device is suspicious"""
        # Direct checks
        if self.is_rooted or self.is_emulator:
            return True
        
        # Risk-based check
        if self.risk_score >= 50:
            return True
        
        # Duplicate check
        if DeviceInfo.check_duplicate_devices(self.device_id_hash, self.user) > 2:
            return True
        
        return False
    
    @cache_result(timeout=60)
    def get_trust_level_display(self) -> str:
        """Get trust level with icon"""
        if self.is_trusted:
            return '🛡️ Trusted'
        
        trust_icons = {
            1: '🔴 Low Trust',
            2: '🟡 Medium Trust',
            3: '🟢 High Trust',
        }
        
        return trust_icons.get(self.trust_level, '⚪ Unknown')
    
    # ==================== FINGERPRINT METHODS ====================
    
    def get_fingerprint(self) -> Dict[str, Any]:
        """Get complete device fingerprint"""
        return {
            'device_id_hash': self.device_id_hash[:16] + '...' if self.device_id_hash else None,
            'device_model': self.device_model,
            'device_brand': self.device_brand,
            'android_version': self.android_version,
            'app_version': self.app_version,
            'security_flags': self.get_security_flags(),
            'risk_score': self.risk_score,
            'risk_level': self.get_risk_level_display(),
            'trust_level': self.get_trust_level_display(),
            'last_ip': self.last_ip,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
        }
    
    # ==================== CLASS METHODS ====================
    
    @classmethod
    @GracefulDegradation.with_default(0)
    def check_duplicate_devices(cls, device_id_hash: str, exclude_user=None) -> int:
        """Check if device is used by multiple accounts"""
        try:
            query = cls.objects.filter(device_id_hash=device_id_hash)
            
            if exclude_user:
                query = query.exclude(user=exclude_user)
            
            # Exclude devices without users
            query = query.exclude(user__isnull=True)
            
            return query.distinct().count()
            
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            return 0
    
    @classmethod
    def get_suspicious_devices(cls, threshold: int = 50) -> models.QuerySet:
        """Get all suspicious devices"""
        try:
            return cls.objects.filter(
                Q(is_rooted=True) |
                Q(is_emulator=True) |
                Q(risk_score__gte=threshold)
            ).select_related('user')[:100]  # Limit for performance
        except Exception as e:
            logger.error(f"Failed to get suspicious devices: {e}")
            return cls.objects.none()
    
    @classmethod
    def get_duplicate_report(cls) -> Dict[str, Any]:
        """Generate duplicate device report"""
        report = {
            'total_duplicates': 0,
            'devices': [],
            'top_offenders': []
        }
        
        try:
            # Find devices used by multiple users
            duplicates = cls.objects.values('device_id_hash').annotate(
                user_count=Count('user', distinct=True)
            ).filter(user_count__gt=1).order_by('-user_count')[:20]
            
            report['total_duplicates'] = duplicates.count()
            report['devices'] = list(duplicates)
            
            # Top offenders
            for dup in duplicates[:5]:
                devices = cls.objects.filter(
                    device_id_hash=dup['device_id_hash']
                ).select_related('user').values(
                    'user__username', 'device_model', 'risk_score'
                )[:5]
                
                report['top_offenders'].append({
                    'device_hash': dup['device_id_hash'][:16] + '...',
                    'user_count': dup['user_count'],
                    'devices': list(devices)
                })
                
        except Exception as e:
            logger.error(f"Duplicate report failed: {e}")
        
        return report


# ==================== SIGNALS ====================

@receiver(post_save, sender=DeviceInfo)
def device_post_save(sender, instance, created, **kwargs):
    """Handle post-save actions"""
    if created:
        logger.info(f"New device registered: {instance.device_id_hash[:8] if instance.device_id_hash else 'No ID'}")
        
        # Check for duplicates asynchronously
        try:
            if instance.device_id_hash and instance.user:
                duplicate_count = DeviceInfo.check_duplicate_devices(
                    instance.device_id_hash,
                    exclude_user=instance.user
                )
                
                if duplicate_count > 0:
                    logger.warning(
                        f"Duplicate device: {instance.device_id_hash[:8]} "
                        f"used by {duplicate_count} other users"
                    )
                    
        except Exception as e:
            logger.error(f"Post-save check failed: {e}")


@receiver(pre_save, sender=DeviceInfo)
def device_pre_save(sender, instance, **kwargs):
    """Handle pre-save actions"""
    try:
        # Update last_activity
        instance.last_activity = timezone.now()
        
        # Auto-calculate risk score if not updating manually
        update_fields = kwargs.get('update_fields', [])
        if not update_fields or 'risk_score' not in update_fields:
            if instance.pk:  # Existing device
                try:
                    old = DeviceInfo.objects.filter(pk=instance.pk).first()
                    if old and (
                        old.is_rooted != instance.is_rooted or
                        old.is_emulator != instance.is_emulator or
                        old.is_vpn != instance.is_vpn or
                        old.is_proxy != instance.is_proxy
                    ):
                        instance.risk_score = instance._calculate_base_risk_score()
                except DeviceInfo.DoesNotExist:
                    pass
    except Exception as e:
        logger.error(f"Pre-save hook failed: {e}")


# ==================== MANAGER ====================

class DeviceInfoManager(models.Manager):
    """Custom manager for DeviceInfo"""
    
    def get_queryset(self):
        return super().get_queryset().select_related('user')
    
    def active_devices(self, hours: int = 24):
        """Get devices active in last X hours"""
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(last_activity__gte=cutoff)
    
    def high_risk_devices(self):
        """Get high risk devices"""
        return self.get_queryset().filter(risk_score__gte=70)
    
    def suspicious_devices(self):
        """Get suspicious devices"""
        return self.get_queryset().filter(
            Q(is_rooted=True) | Q(is_emulator=True) | Q(risk_score__gte=50)
        )
    
    def trusted_devices(self):
        """Get trusted devices"""
        return self.get_queryset().filter(is_trusted=True)
    
    def devices_by_user(self, user):
        """Get all devices for a user"""
        if not user:
            return self.none()
        return self.get_queryset().filter(user=user)
    
    def devices_by_ip(self, ip: str):
        """Get devices by IP address"""
        if not ip:
            return self.none()
        return self.get_queryset().filter(last_ip=ip)


# Add manager to model
DeviceInfo.add_to_class('objects', DeviceInfoManager())

logger.info("DeviceInfo model loaded successfully")



class SecurityLog(models.Model):
    """Security event logging"""
    
    EVENT_TYPE_CHOICES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('failed_login', 'Failed Login'),
        ('password_change', 'Password Change'),
        ('permission_denied', 'Permission Denied'),
        ('not_found', 'Not Found'),
        ('access_denied', 'Access Denied'),
        ('success', 'Success'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    log_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    # ভিউ এর সাথে মিল রাখার জন্য এই নামগুলো ব্যবহার করুন:
    security_type = models.CharField(max_length=100, null=True, blank=True) # event_type এর বদলে এটি দিন
    severity = models.CharField(max_length=20, default='low', null=True, blank=True)
    ip_address = models.GenericIPAddressField(default='0.0.0.0', null=True, blank=True)
    # SecurityLog model এ যোগ করুন
    # resolved = models.BooleanField(default=False)
    # resolved_at = models.DateTimeField(null=True, blank=True)
    # resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    # device_info = models.ForeignKey(DeviceInfo, on_delete=models.SET_NULL, null=True, blank=True)
    
    description = models.TextField(null=True, blank=True) # এটি নতুন যোগ করুন
    risk_score = models.IntegerField(default=0) # এটি নতুন যোগ করুন
    response_time_ms = models.IntegerField(default=0) # এটি নতুন যোগ করুন
    
    user_agent = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True) # details এর বদলে metadata নাম দিন
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    # 🔴 CRITICAL: Use safe IP field
    ip_address = models.GenericIPAddressField(
        default='0.0.0.0',  # Safe default
        verbose_name=_("IP Address")
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_logs')
    
    device_info = models.ForeignKey(
        'DeviceInfo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_logs')
    
    action_taken = models.TextField(
        blank=True,
        null=True,
        verbose_name="Action Taken",
        help_text="Action taken in response to this security event"
    )
    
    resolved = models.BooleanField(
        default=False,
        verbose_name="Resolved",
        help_text="Whether this security event has been resolved"
    )
    
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Resolved At"
    )
    
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_security_logs',
        verbose_name="Resolved By")
    
    user_agent = models.TextField(blank=True, null=True)
    request_path = models.CharField(max_length=500, blank=True, null=True)
    request_method = models.CharField(max_length=10, blank=True, null=True)
    
    details = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'security_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['security_type']),
            models.Index(fields=['severity']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.security_type} - {self.ip_address} - {self.created_at}"
    
    def save(self, *args, **kwargs):
        """Override save to validate IP"""
        from api.wallet.validators import safe_ip_address
        
        # Validate IP before saving
        if self.ip_address:
            self.ip_address = safe_ip_address(self.ip_address, '0.0.0.0')
        else:
            self.ip_address = '0.0.0.0'
        
        super().save(*args, **kwargs)

# class SecurityLog(models.Model):
#     """Log all security-related events with enhanced tracking"""
#     SECURITY_TYPES = [
#         ('vpn_detected', 'VPN Detected'),
#         ('proxy_detected', 'Proxy Detected'),
#         ('rooted_device', 'Rooted Device'),
#         ('emulator', 'Emulator'),
#         ('duplicate_device', 'Duplicate Device'),
#         ('fast_clicking', 'Fast Clicking'),
#         ('suspicious_activity', 'Suspicious Activity'),
#         ('multiple_accounts', 'Multiple Accounts'),
#         ('unauthorized_access', 'Unauthorized Access'),
#         ('failed_login', 'Failed Login'),
#         ('withdrawal_attempt', 'Withdrawal Attempt'),
#         ('api_abuse', 'API Abuse'),
#         ('version_mismatch', 'Version Mismatch'),
#         ('geolocation_alert', 'Geolocation Alert'),
#         ('rate_limit_exceeded', 'Rate Limit Exceeded'),
#         ('password_breach', 'Password Breach'),
#         ('session_hijack', 'Session Hijack'),
#     ]
    
#     SEVERITY_LEVELS = [
#         ('low', 'Low'),
#         ('medium', 'Medium'),
#         ('high', 'High'),
#         ('critical', 'Critical'),
#     ]
    
#     user = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.SET_NULL,  # Keep logs even if user deleted
#         related_name='security_logs',
#         null=True,
#         blank=True
#     , null=True, blank=True)
#     security_type = models.CharField(max_length=50, choices=SECURITY_TYPES, null=True, blank=True)
#     severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='medium', null=True, blank=True)
#     ip_address = models.GenericIPAddressField(null=True, blank=True)  # Null Object Pattern
#     user_agent = models.TextField(blank=True, null=True, default="")
#     device_info = models.ForeignKey(
#         DeviceInfo,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='security_logs'
#     , null=True, blank=True)
#     description = models.TextField(default="")
#     metadata = models.JSONField(default=dict, blank=True)
#     action_taken = models.CharField(max_length=200, default="", null=True, blank=True)
#     risk_score = models.IntegerField(default=0)
#     resolved = models.BooleanField(default=False)
#     resolved_at = models.DateTimeField(null=True, blank=True)
#     resolved_by = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='resolved_security_logs'
#     , null=True, blank=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     response_time_ms = models.IntegerField(null=True, blank=True)
    
#     class Meta:
#         ordering = ['-created_at']
#         indexes = [
#             models.Index(fields=['user', 'security_type']),
#             models.Index(fields=['security_type', 'severity']),
#             models.Index(fields=['created_at']),
#             models.Index(fields=['ip_address']),
#             models.Index(fields=['resolved']),
#             models.Index(fields=['risk_score']),
#         ]
    
#     def __str__(self) -> str:
#         """Safe string representation"""
#         username = NullSafe.get_safe(self.user, 'username', 'Unknown')
#         return f"{self.security_type} - {username} - {self.created_at}"
    
#     def clean(self):
#         """Validate log entry"""
#         super().clean()
        
#         # Validate severity based on type
#         if self.security_type in ['unauthorized_access', 'session_hijack']:
#             if self.severity not in ['high', 'critical']:
#                 self.severity = 'high'
        
#         # Auto-calculate risk score
#         self._calculate_risk_score()
    
#     def _calculate_risk_score(self) -> None:
#         """Calculate risk score based on severity and type"""
#         severity_scores = {
#             'low': 10,
#             'medium': 30,
#             'high': 60,
#             'critical': 90
#         }
        
#         type_multipliers = {
#             'failed_login': 1.2,
#             'unauthorized_access': 2.0,
#             'session_hijack': 2.5,
#             'api_abuse': 1.5,
#         }
        
#         base_score = severity_scores.get(self.severity, 30)
#         multiplier = type_multipliers.get(self.security_type, 1.0)
        
#         self.risk_score = int(base_score * multiplier)
    
#     def mark_resolved(self, resolved_by=None, notes=""):
#         """Mark log as resolved"""
#         try:
#             self.resolved = True
#             self.resolved_at = timezone.now()
#             self.resolved_by = resolved_by
#             if notes:
#                 self.action_taken = f"{self.action_taken}; Resolved: {notes}" if self.action_taken else f"Resolved: {notes}"
#             self.save()
#         except Exception as e:
#             logger.error(f"Error marking log resolved: {str(e)}")
            


# ==================== SMART RISK SCORING ENGINE ====================

class RiskScore(models.Model):
    """Dynamic risk scoring system"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='risk_scores')
    current_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    previous_score = models.IntegerField(default=0)
    
    # Behavioral factors
    login_frequency = models.IntegerField(default=0)  # Logins per day
    device_diversity = models.IntegerField(default=1)  # Number of unique devices
    location_diversity = models.IntegerField(default=1)  # Number of unique locations
    
    # Risk factors
    failed_login_attempts = models.IntegerField(default=0)
    suspicious_activities = models.IntegerField(default=0)
    vpn_usage_count = models.IntegerField(default=0)
    
    # Timing factors
    last_login_time = models.DateTimeField(null=True, blank=True)
    last_suspicious_activity = models.DateTimeField(null=True, blank=True)
    
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'current_score']),
            models.Index(fields=['current_score']),
        ]
    
    def calculate_score(self) -> int:
        """Calculate comprehensive risk score"""
        try:
            score = 50  # Base score
            
            # Behavioral adjustments
            if self.login_frequency > 20:  # Too frequent
                score += 15
            elif self.login_frequency < 1:  # Too infrequent
                score += 10
            
            # Device diversity - too many devices is suspicious
            if self.device_diversity > 5:
                score += 20
            
            # Location diversity - rapid location changes
            if self.location_diversity > 3:
                score += 25
            
            # Failed login attempts
            score += min(self.failed_login_attempts * 5, 30)
            
            # Suspicious activities
            score += min(self.suspicious_activities * 8, 40)
            
            # VPN usage
            if self.vpn_usage_count > 10:
                score += 15
            
            # Time-based factors
            if self.last_suspicious_activity:
                hours_since = (timezone.now() - self.last_suspicious_activity).total_seconds() / 3600
                if hours_since < 24:  # Recent suspicious activity
                    score += 20
            
            # Cap score between 0-100
            return max(0, min(100, score))
        except Exception as e:
            logger.error(f"Error calculating risk score: {str(e)}")
            return 50  # Default safe score
    
    def update_score(self) -> None:
        """Update and save risk score"""
        self.previous_score = self.current_score
        self.current_score = self.calculate_score()
        self.calculated_at = timezone.now()
        self.save()


# ==================== SECURITY DASHBOARD & ANALYTICS ====================

class SecurityDashboard(models.Model):
    """Security analytics dashboard data"""
    date = models.DateField(unique=True)
    
    # Overview metrics
    total_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    new_users = models.IntegerField(default=0)
    
    # Security metrics
    total_threats = models.IntegerField(default=0)
    threats_blocked = models.IntegerField(default=0)
    threats_pending = models.IntegerField(default=0)
    
    # Threat breakdown
    vpn_threats = models.IntegerField(default=0)
    proxy_threats = models.IntegerField(default=0)
    rooted_threats = models.IntegerField(default=0)
    duplicate_accounts = models.IntegerField(default=0)
    fast_clicking = models.IntegerField(default=0)
    api_abuse = models.IntegerField(default=0)
    
    # Risk distribution
    low_risk_users = models.IntegerField(default=0)
    medium_risk_users = models.IntegerField(default=0)
    high_risk_users = models.IntegerField(default=0)
    critical_risk_users = models.IntegerField(default=0)
    
    # Geo metrics
    top_countries = models.JSONField(default=list)
    suspicious_countries = models.JSONField(default=list)
    
    # Device metrics
    rooted_devices = models.IntegerField(default=0)
    emulator_devices = models.IntegerField(default=0)
    
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name_plural = 'Security Dashboards'
    
    @classmethod
    def generate_daily_report(cls, date=None) -> 'SecurityDashboard':
        """Generate daily security report"""
        if date is None:
            date = timezone.now().date()
        
        try:
            # Calculate all metrics
            start_date = date
            end_date = date + timedelta(days=1)
            
            # Get total users
            total_users = settings.AUTH_USER_MODEL.objects.count()
            
            # Get active users (last 24 hours)
            active_users = settings.AUTH_USER_MODEL.objects.filter(
                last_login__gte=timezone.now() - timedelta(days=1)
            ).count()
            
            # Get new users
            new_users = settings.AUTH_USER_MODEL.objects.filter(
                date_joined__date=date
            ).count()
            
            # Get security logs for the day
            security_logs = SecurityLog.objects.filter(
                created_at__date=date
            )
            
            # Count threats by type
            threats_by_type = security_logs.values('security_type').annotate(
                count=Count('id')
            )
            
            # Create dashboard entry
            dashboard, created = cls.objects.get_or_create(date=date)
            
            # Update metrics
            dashboard.total_users = total_users
            dashboard.active_users = active_users
            dashboard.new_users = new_users
            dashboard.total_threats = security_logs.count()
            dashboard.threats_blocked = security_logs.filter(resolved=True).count()
            dashboard.threats_pending = security_logs.filter(resolved=False).count()
            
            # Update threat breakdown
            for threat in threats_by_type:
                threat_type = threat['security_type']
                count = threat['count']
                
                if threat_type == 'vpn_detected':
                    dashboard.vpn_threats = count
                elif threat_type == 'proxy_detected':
                    dashboard.proxy_threats = count
                elif threat_type == 'rooted_device':
                    dashboard.rooted_threats = count
                elif threat_type == 'duplicate_device':
                    dashboard.duplicate_accounts = count
                elif threat_type == 'fast_clicking':
                    dashboard.fast_clicking = count
                elif threat_type == 'api_abuse':
                    dashboard.api_abuse = count
            
            dashboard.save()
            return dashboard
            
        except Exception as e:
            logger.error(f"Error generating daily report: {str(e)}")
            return None


# ==================== AUTO-BLOCK SUSPICIOUS BEHAVIOR ====================

class AutoBlockRule(models.Model):
    """Rules for automatic blocking of suspicious behavior"""
    RULE_TYPES = [
        ('ip_threshold', 'IP Activity Threshold'),
        ('device_threshold', 'Device Activity Threshold'),
        ('behavior_pattern', 'Behavior Pattern'),
        ('geolocation', 'Geolocation Anomaly'),
        ('velocity', 'Velocity Check'),
    ]
    
    name = models.CharField(max_length=100, unique=True, null=True, blank=True)
    rule_type = models.CharField(max_length=50, choices=RULE_TYPES, null=True, blank=True)
    description = models.TextField()
    
    # Threshold configuration
    threshold_value = models.IntegerField(default=10)
    time_window_minutes = models.IntegerField(default=60)
    
    # Action configuration
    action_type = models.CharField(max_length=50, choices=[
        ('block', 'Block Temporarily'),
        ('ban', 'Permanent Ban'),
        ('alert', 'Send Alert'),
        ('rate_limit', 'Rate Limit'),
        ('require_2fa', 'Require 2FA'),
    ])
    action_duration_hours = models.IntegerField(default=24, null=True, blank=True)
    
    # Targeting
    apply_to_all_users = models.BooleanField(default=True)
    user_groups = models.ManyToManyField(
        'auth.Group',
        related_name='auto_block_rules'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=1)  # Higher = higher priority
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-priority', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.rule_type})"
    
    def evaluate(self, user=None, ip_address=None, device_info=None, activity_data=None) -> bool:
        """Evaluate if rule should trigger"""
        try:
            if not self.is_active:
                return False
            
            # Get evaluation method based on rule type
            evaluators = {
                'ip_threshold': self._evaluate_ip_threshold,
                'device_threshold': self._evaluate_device_threshold,
                'behavior_pattern': self._evaluate_behavior_pattern,
                'geolocation': self._evaluate_geolocation,
                'velocity': self._evaluate_velocity,
            }
            
            evaluator = evaluators.get(self.rule_type)
            if evaluator:
                return evaluator(user, ip_address, device_info, activity_data)
            
            return False
            
        except Exception as e:
            logger.error(f"Error evaluating rule {self.name}: {str(e)}")
            return False
    
    def _evaluate_ip_threshold(self, user, ip_address, device_info, activity_data) -> bool:
        """Evaluate IP-based threshold"""
        if not ip_address:
            return False
        
        time_window = timezone.now() - timedelta(minutes=self.time_window_minutes)
        
        # Count activities from this IP
        activity_count = ClickTracker.objects.filter(
            ip_address=ip_address,
            clicked_at__gte=time_window
        ).count()
        
        return activity_count >= self.threshold_value
    
    def take_action(self, user, ip_address, device_info, reason):
        """Execute the configured action"""
        try:
            if self.action_type == 'block':
                # Create temporary block
                block = UserBan.objects.create(
                    user=user,
                    reason='auto_block',
                    description=f"Auto-blocked by rule: {self.name}. Reason: {reason}",
                    banned_until=timezone.now() + timedelta(hours=self.action_duration_hours),
                    is_permanent=False,
                    metadata={'rule_id': self.id, 'reason': reason}
                )
                return block
            
            elif self.action_type == 'ban':
                # Create permanent ban
                ban = UserBan.objects.create(
                    user=user,
                    reason='auto_ban',
                    description=f"Auto-banned by rule: {self.name}. Reason: {reason}",
                    is_permanent=True,
                    metadata={'rule_id': self.id, 'reason': reason}
                )
                return ban
            
            elif self.action_type == 'alert':
                # Create security log alert
                SecurityLog.objects.create(
                    user=user,
                    security_type='suspicious_activity',
                    severity='high',
                    ip_address=ip_address,
                    device_info=device_info,
                    description=f"Alert triggered by rule {self.name}: {reason}",
                    metadata={'rule_id': self.id}
                )
                return True
            
            elif self.action_type == 'rate_limit':
                # Implement rate limiting
                from django.core.cache import cache
                cache_key = f'rate_limit:{user.id}:{self.id}'
                cache.set(cache_key, True, self.action_duration_hours * 3600)
                return True
            
            elif self.action_type == 'require_2fa':
                # Flag user for 2FA requirement
                user.profile.require_2fa = True
                user.profile.save()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error taking action for rule {self.name}: {str(e)}")
            return False


# ==================== COMPLIANCE & AUDIT TRAIL ====================

class AuditTrail(models.Model):
    """Comprehensive audit trail for all system actions"""
    ACTION_TYPES = [
        ('create', 'Create'),
        ('read', 'Read'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('other', 'Other'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_trails')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES, null=True, blank=True)
    model_name = models.CharField(max_length=100, null=True, blank=True)
    object_id = models.CharField(max_length=100, null=True, blank=True)
    object_repr = models.CharField(max_length=255, null=True, blank=True)
    
    # Changes made
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    
    # Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    session_key = models.CharField(max_length=100, null=True, blank=True)
    
    # Metadata
    request_path = models.CharField(max_length=500, null=True, blank=True)
    request_method = models.CharField(max_length=10, null=True, blank=True)
    status_code = models.IntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['action_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.action_type} {self.model_name}.{self.object_id} by {self.user}"
    
    @classmethod
    def log_action(cls, user, action_type, model_name, object_id, **kwargs):
        """Log an audit action with defensive coding"""
        try:
            return cls.objects.create(
                user=user,
                action_type=action_type,
                model_name=model_name,
                object_id=str(object_id),
                object_repr=kwargs.get('object_repr', ''),
                old_values=kwargs.get('old_values', {}),
                new_values=kwargs.get('new_values', {}),
                changed_fields=kwargs.get('changed_fields', []),
                ip_address=kwargs.get('ip_address'),
                user_agent=kwargs.get('user_agent', ''),
                session_key=kwargs.get('session_key', ''),
                request_path=kwargs.get('request_path', ''),
                request_method=kwargs.get('request_method', ''),
                status_code=kwargs.get('status_code'),
            )
        except Exception as e:
            logger.error(f"Error logging audit trail: {str(e)}")
            return None


# ==================== DATA EXPORT/IMPORT SECURITY ====================

class DataExport(models.Model):
    """Secure data export system"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('json', 'JSON'),
        ('xlsx', 'Excel'),
        ('pdf', 'PDF'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='data_exports')
    export_name = models.CharField(max_length=200, null=True, blank=True)
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='csv', null=True, blank=True)
    
    # Query parameters
    model_name = models.CharField(max_length=100, null=True, blank=True)
    filters = models.JSONField(default=dict, blank=True)
    columns = models.JSONField(default=list, blank=True)
    
    # Security
    password_hash = models.CharField(max_length=128, null=True, blank=True)
    encryption_key = models.TextField(blank=True)
    is_encrypted = models.BooleanField(default=True)
    
    # Storage
    file_path = models.CharField(max_length=500, null=True, blank=True)
    file_size = models.BigIntegerField(default=0)
    download_url = models.URLField(null=True, blank=True)
    
    # Metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', null=True, blank=True)
    total_records = models.IntegerField(default=0)
    exported_records = models.IntegerField(default=0)
    
    # Audit
    requested_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"{self.export_name} - {self.status}"
    
    def clean(self):
        """Validate export parameters"""
        super().clean()
        
        # Set expiration (default 7 days)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        
        # Validate filters JSON
        if self.filters and not isinstance(self.filters, dict):
            raise ValidationError({'filters': 'Filters must be a JSON object'})
    
    def is_expired(self):
        """Check if export has expired"""
        return timezone.now() > self.expires_at
    
    def generate_secure_download_url(self):
        """Generate secure, time-limited download URL"""
        try:
            # Create token
            token_data = {
                'export_id': self.id,
                'user_id': self.user.id,
                'expires': (timezone.now() + timedelta(hours=1)).isoformat()
            }
            
            # Encrypt token
            token_json = json.dumps(token_data)
            cipher_suite = Fernet(settings.DATA_EXPORT_SECRET_KEY)
            encrypted_token = cipher_suite.encrypt(token_json.encode())
            
            # Create URL
            token_b64 = base64.urlsafe_b64encode(encrypted_token).decode()
            self.download_url = f"{settings.DATA_EXPORT_BASE_URL}/download/{self.id}/{token_b64}"
            self.save()
            
            return self.download_url
            
        except Exception as e:
            logger.error(f"Error generating download URL: {str(e)}")
            return None


class DataImport(models.Model):
    """Secure data import system"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('validating', 'Validating'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('partially_completed', 'Partially Completed'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='data_imports')
    import_name = models.CharField(max_length=200, null=True, blank=True)
    model_name = models.CharField(max_length=100, null=True, blank=True)
    
    # File details
    file_name = models.CharField(max_length=255, null=True, blank=True)
    file_path = models.CharField(max_length=500, null=True, blank=True)
    file_size = models.BigIntegerField()
    file_hash = models.CharField(max_length=64, null=True, blank=True)  # SHA-256 hash
    
    # Processing
    total_records = models.IntegerField(default=0)
    processed_records = models.IntegerField(default=0)
    successful_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    
    # Validation
    validation_errors = models.JSONField(default=list, blank=True)
    validation_warnings = models.JSONField(default=list, blank=True)
    
    # Security
    is_verified = models.BooleanField(default=False)
    verification_hash = models.CharField(max_length=64, null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', null=True, blank=True)
    
    # Audit
    uploaded_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.import_name} - {self.status}"
    
    def validate_file(self):
        """Validate import file"""
        try:
            # Check file hash
            with open(self.file_path, 'rb') as f:
                file_data = f.read()
                calculated_hash = hashlib.sha256(file_data).hexdigest()
            
            if calculated_hash != self.file_hash:
                raise ValidationError("File hash mismatch - file may have been tampered with")
            
            # Add more validations based on file type
            if self.file_name.endswith('.csv'):
                self._validate_csv()
            elif self.file_name.endswith('.json'):
                self._validate_json()
            
            self.is_verified = True
            self.save()
            
            return True
            
        except Exception as e:
            self.validation_errors.append(str(e))
            self.status = 'failed'
            self.save()
            return False
    
    def calculate_file_hash(self, file_path):
        """Calculate SHA-256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


# ==================== NOTIFICATION & ALERT SYSTEM ====================

class SecurityNotification(models.Model):
    """Security notification system"""
    NOTIFICATION_TYPES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('in_app', 'In-App Notification'),
        ('webhook', 'Webhook'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='security_notifications',
        null=True,
        blank=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, null=True, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, default='medium', null=True, blank=True)
    
    # Content
    title = models.CharField(max_length=200, null=True, blank=True)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)  # Additional data
    
    # Delivery
    recipient = models.CharField(max_length=500, null=True, blank=True)  # Email, phone, etc.
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('read', 'Read'),
    ], default='pending')
    
    # Retry
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['priority', 'created_at']),
            models.Index(fields=['sent_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.status}"
    
    def send(self):
        """Send notification"""
        try:
            self.status = 'sending'
            self.sent_at = timezone.now()
            self.save()
            
            # Send based on type
            if self.notification_type == 'email':
                self._send_email()
            elif self.notification_type == 'sms':
                self._send_sms()
            elif self.notification_type == 'push':
                self._send_push()
            elif self.notification_type == 'in_app':
                self._send_in_app()
            elif self.notification_type == 'webhook':
                self._send_webhook()
            
            self.status = 'sent'
            self.delivered_at = timezone.now()
            self.save()
            
            return True
            
        except Exception as e:
            self.status = 'failed'
            self.error_message = str(e)
            self.retry_count += 1
            
            # Schedule retry if not exceeded max retries
            if self.retry_count < self.max_retries:
                self.next_retry_at = timezone.now() + timedelta(minutes=5 * self.retry_count)
            
            self.save()
            logger.error(f"Error sending notification: {str(e)}")
            return False
    
    @classmethod
    def send_immediate_alert(cls, user, title, message, priority='high', notification_type='email'):
        """Send immediate security alert"""
        try:
            notification = cls.objects.create(
                user=user,
                notification_type=notification_type,
                priority=priority,
                title=title,
                message=message,
                recipient=user.email if user else settings.ADMIN_EMAIL,
                status='pending'
            )
            
            # Send immediately
            notification.send()
            
            return notification
            
        except Exception as e:
            logger.error(f"Error sending immediate alert: {str(e)}")
            return None


class AlertRule(models.Model):
    """Rules for triggering security alerts"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='alert_rules',
        null=True,
        blank=True)
    name = models.CharField(max_length=100, null=True, blank=True)
    condition = models.JSONField()  # JSON logic condition
    notification_types = models.JSONField(default=list)  # List of notification types
    
    # Trigger settings
    is_active = models.BooleanField(default=True)
    cooldown_minutes = models.IntegerField(default=30)  # Prevent alert spam
    
    # Last triggered
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    trigger_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def should_trigger(self):
        """Check if alert should trigger (respecting cooldown)"""
        if not self.is_active:
            return False
        
        # Check cooldown
        if self.last_triggered_at:
            cooldown_end = self.last_triggered_at + timedelta(minutes=self.cooldown_minutes)
            if timezone.now() < cooldown_end:
                return False
        
        # Evaluate condition (simplified - in practice use json-logic or similar)
        try:
            # Here you would implement your condition evaluation logic
            # For example, check if certain thresholds are exceeded
            return self._evaluate_condition()
        except Exception as e:
            logger.error(f"Error evaluating alert condition: {str(e)}")
            return False
    
    def trigger(self, data=None):
        """Trigger the alert"""
        try:
            # Update trigger info
            self.last_triggered_at = timezone.now()
            self.trigger_count += 1
            self.save()
            
            # Create notifications
            for notification_type in self.notification_types:
                SecurityNotification.objects.create(
                    user=self.user,
                    notification_type=notification_type,
                    priority='high',
                    title=f"Alert: {self.name}",
                    message=f"Alert rule '{self.name}' was triggered.",
                    data=data or {},
                    recipient=self.user.email if self.user else settings.ADMIN_EMAIL,
                    status='pending'
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Error triggering alert: {str(e)}")
            return False


# ==================== REAL-TIME FRAUD DETECTION ENGINE ====================

class FraudPattern(models.Model):
    """Known fraud patterns for detection"""
    PATTERN_TYPES = [
        ('account_takeover', 'Account Takeover'),
        ('payment_fraud', 'Payment Fraud'),
        ('identity_fraud', 'Identity Fraud'),
        ('bot_activity', 'Bot Activity'),
        ('money_laundering', 'Money Laundering'),
    ]
    
    name = models.CharField(max_length=100, unique=True, null=True, blank=True)
    pattern_type = models.CharField(max_length=50, choices=PATTERN_TYPES, null=True, blank=True)
    description = models.TextField()
    
    # Pattern configuration
    conditions = models.JSONField()  # JSON logic for pattern matching
    weight = models.IntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(100)])
    
    # Detection settings
    confidence_threshold = models.IntegerField(default=70)  # 0-100
    auto_block = models.BooleanField(default=False)
    block_duration_hours = models.IntegerField(default=24)
    
    # Status
    is_active = models.BooleanField(default=True)
    last_match_at = models.DateTimeField(null=True, blank=True)
    match_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-weight', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.pattern_type})"
    
    def evaluate(self, user_data, activity_data, device_data):
        """Evaluate if pattern matches"""
        try:
            # Calculate match score based on conditions
            score = 0
            
            # Here you would implement complex pattern matching logic
            # This is a simplified example
            
            if self.pattern_type == 'account_takeover':
                score = self._evaluate_account_takeover(user_data, activity_data, device_data)
            elif self.pattern_type == 'payment_fraud':
                score = self._evaluate_payment_fraud(user_data, activity_data, device_data)
            # Add other pattern types...
            
            return score >= self.confidence_threshold, score
            
        except Exception as e:
            logger.error(f"Error evaluating fraud pattern: {str(e)}")
            return False, 0
    
    def record_match(self, user, score, details):
        """Record pattern match"""
        try:
            self.last_match_at = timezone.now()
            self.match_count += 1
            self.save()
            
            # Create security log
            SecurityLog.objects.create(
                user=user,
                security_type='suspicious_activity',
                severity='critical' if score > 80 else 'high',
                description=f"Fraud pattern detected: {self.name}. Score: {score}",
                metadata={
                    'pattern_id': self.id,
                    'pattern_name': self.name,
                    'score': score,
                    'details': details,
                }
            )
            
            # Auto-block if configured
            if self.auto_block and score >= self.confidence_threshold:
                AutoBlockRule.objects.filter(
                    name=f"Auto-block for {self.name}"
                ).first() or AutoBlockRule.objects.create(
                    name=f"Auto-block for {self.name}",
                    rule_type='behavior_pattern',
                    description=f"Auto-generated rule for fraud pattern: {self.name}",
                    threshold_value=1,
                    time_window_minutes=1,
                    action_type='block',
                    action_duration_hours=self.block_duration_hours,
                    apply_to_all_users=True,
                    is_active=True,
                    priority=10
                )
            
        except Exception as e:
            logger.error(f"Error recording fraud pattern match: {str(e)}")


class RealTimeDetection(models.Model):
    """Real-time fraud detection engine"""
    STATUS_CHOICES = [
        ('idle', 'Idle'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('error', 'Error'),
    ]
    
    name = models.CharField(max_length=100, unique=True, null=True, blank=True)
    detection_type = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField()
    
    # Configuration
    check_interval_seconds = models.IntegerField(default=60)
    batch_size = models.IntegerField(default=100)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='idle', null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    
    # Statistics
    total_checks = models.BigIntegerField(default=0)
    total_matches = models.BigIntegerField(default=0)
    
    # Performance
    average_processing_time = models.FloatField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.status}"
    
    def run_detection(self):
        """Run fraud detection"""
        try:
            self.status = 'running'
            self.save()
            
            start_time = timezone.now()
            
            # Get recent activities to check
            recent_time = timezone.now() - timedelta(minutes=5)
            
            # This is where you would implement your detection logic
            # For example, check recent login attempts
            recent_logins = SecurityLog.objects.filter(
                security_type='failed_login',
                created_at__gte=recent_time
            ).select_related('user', 'device_info')
            
            for login in recent_logins:
                # Evaluate fraud patterns
                fraud_detected = self._check_for_fraud(login)
                if fraud_detected:
                    self.total_matches += 1
            
            self.total_checks += 1
            self.last_run_at = timezone.now()
            
            # Calculate processing time
            processing_time = (timezone.now() - start_time).total_seconds()
            self.average_processing_time = (
                self.average_processing_time * (self.total_checks - 1) + processing_time
            ) / self.total_checks
            
            self.status = 'idle'
            self.save()
            
            return True
            
        except Exception as e:
            self.status = 'error'
            self.last_error = str(e)
            self.save()
            logger.error(f"Error in fraud detection: {str(e)}")
            return False


# ==================== GEOLOCATION & COUNTRY BLOCKING ====================

class Country(models.Model):
    """Country information for geolocation"""
    name = models.CharField(max_length=100, unique=True, null=True, blank=True)
    code = models.CharField(max_length=2, unique=True, null=True, blank=True)  # ISO 3166-1 alpha-2
    iso_code = models.CharField(max_length=3, unique=True, null=True, blank=True)  # ISO 3166-1 alpha-3
    
    # Risk assessment
    risk_level = models.CharField(max_length=20, choices=[
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('very_high', 'Very High Risk'),
    ], default='medium')
    
    # Blocking configuration
    is_blocked = models.BooleanField(default=False)
    block_reason = models.TextField(blank=True)
    
    # Statistics
    total_users = models.IntegerField(default=0)
    suspicious_activities = models.IntegerField(default=0)
    fraud_cases = models.IntegerField(default=0)
    
    # Metadata
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Countries'
    
    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def update_statistics(self):
        """Update country statistics"""
        try:
            # Count users from this country
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Assuming User model has a country field
            self.total_users = User.objects.filter(country=self.code).count()
            
            # Count suspicious activities
            self.suspicious_activities = SecurityLog.objects.filter(
                ip_geolocation__country_code=self.code,
                severity__in=['high', 'critical']
            ).count()
            
            self.save()
            
        except Exception as e:
            logger.error(f"Error updating country statistics: {str(e)}")


class GeolocationLog(models.Model):
    """Geolocation tracking for IP addresses"""
    ip_address = models.GenericIPAddressField(db_index=True)
    
    # Geolocation data
    country_code = models.CharField(max_length=2, null=True, blank=True)
    country_name = models.CharField(max_length=100, null=True, blank=True)
    region_code = models.CharField(max_length=10, null=True, blank=True)
    region_name = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    zip_code = models.CharField(max_length=20, null=True, blank=True)
    timezone = models.CharField(max_length=50, null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    # ISP/Network information
    isp = models.CharField(max_length=200, null=True, blank=True)
    organization = models.CharField(max_length=200, null=True, blank=True)
    as_number = models.CharField(max_length=50, null=True, blank=True)
    
    # Threat intelligence
    is_vpn = models.BooleanField(default=False)
    is_proxy = models.BooleanField(default=False)
    is_tor = models.BooleanField(default=False)
    is_hosting = models.BooleanField(default=False)
    threat_score = models.IntegerField(default=0)
    
    # Cached flag
    is_cached = models.BooleanField(default=True)
    cache_expires_at = models.DateTimeField()
    
    # Metadata
    queried_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-queried_at']
        indexes = [
            models.Index(fields=['ip_address', 'queried_at']),
            models.Index(fields=['country_code']),
            models.Index(fields=['is_vpn', 'is_proxy']),
        ]
    
    def __str__(self):
        return f"{self.ip_address} - {self.country_name}"
    
    def is_expired(self):
        """Check if geolocation data is expired"""
        return timezone.now() > self.cache_expires_at
    
    @classmethod
    def get_geolocation(cls, ip_address: str) -> 'GeolocationLog':
        """Get geolocation for IP address (cached)"""
        try:
            # Check cache first
            cached = cls.objects.filter(
                ip_address=ip_address,
                cache_expires_at__gt=timezone.now()
            ).first()
            
            if cached:
                return cached
            
            # Get fresh geolocation data
            geolocation_data = cls._lookup_geolocation(ip_address)
            
            # Create or update record
            geolocation, created = cls.objects.update_or_create(
                ip_address=ip_address,
                defaults={
                    **geolocation_data,
                    'is_cached': True,
                    'cache_expires_at': timezone.now() + timedelta(days=30),
                }
            )
            
            return geolocation
            
        except Exception as e:
            logger.error(f"Error getting geolocation: {str(e)}")
            # Return empty geolocation object
            return cls(ip_address=ip_address)
    
    @staticmethod
    def _lookup_geolocation(ip_address: str) -> dict:
        """Lookup geolocation data from external service"""
        # This would typically call an external API like MaxMind, ipinfo.io, etc.
        # For now, return mock data
        return {
            'country_code': 'US',
            'country_name': 'United States',
            'city': 'New York',
            'latitude': 40.7128,
            'longitude': -74.0060,
            'is_vpn': False,
            'is_proxy': False,
        }
    
    def assess_risk(self) -> dict:
        """Assess risk based on geolocation"""
        risk_score = 0
        risk_factors = []
        
        # Check VPN/Proxy
        if self.is_vpn:
            risk_score += 30
            risk_factors.append('VPN detected')
        
        if self.is_proxy:
            risk_score += 25
            risk_factors.append('Proxy detected')
        
        if self.is_tor:
            risk_score += 40
            risk_factors.append('TOR network')
        
        # Check hosting provider
        if self.is_hosting:
            risk_score += 20
            risk_factors.append('Hosting provider')
        
        # Check high-risk country
        try:
            country = Country.objects.get(code=self.country_code)
            if country.risk_level in ['high', 'very_high']:
                risk_score += 35
                risk_factors.append(f'High-risk country: {country.name}')
        except Country.DoesNotExist:
            pass
        
        # Update threat score
        self.threat_score = min(risk_score, 100)
        self.save(update_fields=['threat_score'])
        
        return {
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'threat_level': 'high' if risk_score > 70 else 'medium' if risk_score > 40 else 'low'
        }


class CountryBlockRule(models.Model):
    """Rules for blocking countries"""
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name='block_rules')
    
    # Blocking configuration
    block_type = models.CharField(max_length=20, choices=[
        ('complete', 'Complete Block'),
        ('partial', 'Partial Block'),
        ('monitor', 'Monitor Only'),
        ('require_verification', 'Require Verification'),
    ])
    
    # Scope
    block_all_ips = models.BooleanField(default=True)
    allowed_ips = models.JSONField(default=list, blank=True)  # List of allowed IPs
    allowed_asns = models.JSONField(default=list, blank=True)  # List of allowed ASNs
    
    # Verification requirements
    require_phone_verification = models.BooleanField(default=False)
    require_id_verification = models.BooleanField(default=False)
    require_address_verification = models.BooleanField(default=False)
    
    # Schedule
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_country_blocks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.country.name} - {self.block_type}"
    
    def is_active_now(self):
        """Check if rule is currently active"""
        if not self.is_active:
            return False
        
        now = timezone.now()
        if self.start_date and now < self.start_date:
            return False
        
        if self.end_date and now > self.end_date:
            return False
        
        return True
    
    def should_block_ip(self, ip_address: str, geolocation_data: dict = None) -> bool:
        """Check if IP should be blocked based on rule"""
        if not self.is_active_now():
            return False
        
        # Check if IP is in allowed list
        if ip_address in self.allowed_ips:
            return False
        
        # Get geolocation if not provided
        if geolocation_data is None:
            geolocation = GeolocationLog.get_geolocation(ip_address)
            geolocation_data = {
                'country_code': geolocation.country_code,
                'as_number': geolocation.as_number,
            }
        
        # Check country match
        if geolocation_data.get('country_code') != self.country.code:
            return False
        
        # Check ASN if specified
        if self.allowed_asns and geolocation_data.get('as_number') in self.allowed_asns:
            return False
        
        return True


# ==================== API RATE LIMITING SYSTEM ====================

class APIRateLimit(models.Model):
    """API rate limiting configuration"""
    LIMIT_TYPES = [
        ('user', 'Per User'),
        ('ip', 'Per IP'),
        ('endpoint', 'Per Endpoint'),
        ('global', 'Global'),
    ]
    
    PERIOD_CHOICES = [
        ('second', 'Per Second'),
        ('minute', 'Per Minute'),
        ('hour', 'Per Hour'),
        ('day', 'Per Day'),
        ('month', 'Per Month'),
    ]
    
    name = models.CharField(max_length=100, unique=True, null=True, blank=True)
    description = models.TextField(blank=True)
    
    # Limit configuration
    limit_type = models.CharField(max_length=20, choices=LIMIT_TYPES, null=True, blank=True)
    limit_period = models.CharField(max_length=20, choices=PERIOD_CHOICES, null=True, blank=True)
    request_limit = models.IntegerField(default=100)
    
    # Scope
    endpoint_pattern = models.CharField(max_length=500, null=True, blank=True)  # URL pattern
    user_group = models.ForeignKey(
        'auth.Group',
        on_delete=models.SET_NULL,
        null=True,
        related_name='api_rate_limits')
    
    # Response configuration
    response_status_code = models.IntegerField(default=429)
    response_message = models.TextField(default='Rate limit exceeded')
    response_headers = models.JSONField(default=dict, blank=True)
    
    # Status
    is_active = models.BooleanField(default=True)
    bypass_key_required = models.BooleanField(default=False)
    
    # Statistics
    total_blocks = models.BigIntegerField(default=0)
    last_blocked_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.limit_type}"
    
    def get_cache_key(self, identifier: str) -> str:
        """Generate cache key for rate limiting"""
        period_map = {
            'second': '%Y%m%d%H%M%S',
            'minute': '%Y%m%d%H%M',
            'hour': '%Y%m%d%H',
            'day': '%Y%m%d',
            'month': '%Y%m',
        }
        
        time_format = period_map.get(self.limit_period, '%Y%m%d%H%M')
        time_key = timezone.now().strftime(time_format)
        
        return f"rate_limit:{self.id}:{identifier}:{time_key}"
    
    def check_limit(self, identifier: str, increment: bool = True) -> dict:
        """
        Check if rate limit is exceeded
        
        Returns:
            dict: {
                'allowed': bool,
                'remaining': int,
                'reset_time': datetime,
                'limit': int,
            }
        """
        try:
            cache_key = self.get_cache_key(identifier)
            
            # Get current count from cache
            current_count = cache.get(cache_key, 0)
            
            # Check if limit is exceeded
            if current_count >= self.request_limit:
                return {
                    'allowed': False,
                    'remaining': 0,
                    'reset_time': self._get_reset_time(),
                    'limit': self.request_limit,
                }
            
            # Increment count if requested
            if increment:
                # Set cache with expiration based on period
                expiration = self._get_period_seconds()
                cache.set(cache_key, current_count + 1, expiration)
                
                # Update statistics
                self.total_blocks += 1
                self.last_blocked_at = timezone.now()
                self.save(update_fields=['total_blocks', 'last_blocked_at'])
            
            return {
                'allowed': True,
                'remaining': self.request_limit - (current_count + 1 if increment else current_count),
                'reset_time': self._get_reset_time(),
                'limit': self.request_limit,
            }
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            # Graceful degradation - allow request on error
            return {
                'allowed': True,
                'remaining': self.request_limit,
                'reset_time': timezone.now(),
                'limit': self.request_limit,
            }
    
    def _get_period_seconds(self) -> int:
        """Get cache expiration in seconds based on period"""
        period_seconds = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400,
            'month': 2592000,  # 30 days
        }
        return period_seconds.get(self.limit_period, 60)
    
    def _get_reset_time(self) -> datetime:
        """Get time when rate limit resets"""
        now = timezone.now()
        
        if self.limit_period == 'second':
            return now + timedelta(seconds=1)
        elif self.limit_period == 'minute':
            return (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        elif self.limit_period == 'hour':
            return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        elif self.limit_period == 'day':
            return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.limit_period == 'month':
            next_month = now.replace(day=28) + timedelta(days=4)
            return next_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        return now + timedelta(minutes=1)


class RateLimitLog(models.Model):
    """Log of rate limit events"""
    rate_limit = models.ForeignKey(
        APIRateLimit,
        on_delete=models.CASCADE,
        related_name='logs')
    
    # Request information
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_rate_limit_logs')
    ip_address = models.GenericIPAddressField()
    endpoint = models.CharField(max_length=500, null=True, blank=True)
    request_method = models.CharField(max_length=10, null=True, blank=True)
    
    # Rate limit status
    current_count = models.IntegerField()
    limit_exceeded = models.BooleanField(default=False)
    
    # Response
    response_status_code = models.IntegerField(null=True, blank=True)
    response_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
            models.Index(fields=['limit_exceeded']),
        ]
    
    def __str__(self):
        status = "EXCEEDED" if self.limit_exceeded else "ALLOWED"
        return f"{self.endpoint} - {status} - {self.created_at}"


# ==================== PASSWORD POLICY & HISTORY ====================

class PasswordPolicy(models.Model):
    """Password policy configuration"""
    name = models.CharField(max_length=100, default="Default Password Policy", null=True, blank=True)
    
    # Length requirements
    min_length = models.IntegerField(default=8)
    max_length = models.IntegerField(default=128)
    
    # Complexity requirements
    require_uppercase = models.BooleanField(default=True)
    require_lowercase = models.BooleanField(default=True)
    require_digits = models.BooleanField(default=True)
    require_special_chars = models.BooleanField(default=True)
    min_special_chars = models.IntegerField(default=1)
    special_chars_set = models.CharField(max_length=100, default="!@#$%^&*(, null=True, blank=True)_+-=[]{}|;:,.<>?")
    
    # History requirements
    remember_last_passwords = models.IntegerField(default=5)
    password_expiry_days = models.IntegerField(default=90)
    warn_before_expiry_days = models.IntegerField(default=7)
    
    # Lockout policy
    max_failed_attempts = models.IntegerField(default=5)
    lockout_duration_minutes = models.IntegerField(default=15)
    lockout_increment_factor = models.FloatField(default=2.0)
    
    # Validation
    allow_common_passwords = models.BooleanField(default=False)
    allow_username_in_password = models.BooleanField(default=False)
    allow_repeating_chars = models.BooleanField(default=False)
    allow_sequential_chars = models.BooleanField(default=False)
    
    # Status
    is_active = models.BooleanField(default=True)
    applies_to_all_users = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'Password Policies'
    
    def __str__(self):
        return f"{self.name} {'(Active)' if self.is_active else '(Inactive)'}"
    
    def validate_password(self, password: str, username: str = None) -> dict:
        """
        Validate password against policy
        
        Returns:
            dict: {
                'valid': bool,
                'errors': list,
                'warnings': list,
                'score': int (0-100)
            }
        """
        errors = []
        warnings = []
        score = 0
        
        # Check length
        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters long")
        elif len(password) > self.max_length:
            errors.append(f"Password cannot exceed {self.max_length} characters")
        else:
            score += 20
        
        # Check uppercase
        if self.require_uppercase and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        elif any(c.isupper() for c in password):
            score += 10
        
        # Check lowercase
        if self.require_lowercase and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        elif any(c.islower() for c in password):
            score += 10
        
        # Check digits
        if self.require_digits and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        elif any(c.isdigit() for c in password):
            score += 10
        
        # Check special characters
        if self.require_special_chars:
            special_count = sum(1 for c in password if c in self.special_chars_set)
            if special_count < self.min_special_chars:
                errors.append(f"Password must contain at least {self.min_special_chars} special character(s)")
            elif special_count > 0:
                score += 20
        
        # Check for username in password
        if username and not self.allow_username_in_password and username.lower() in password.lower():
            warnings.append("Password contains username")
            score -= 10
        
        # Check for common passwords
        if not self.allow_common_passwords and self._is_common_password(password):
            errors.append("Password is too common")
        
        # Check for repeating characters
        if not self.allow_repeating_chars and re.search(r'(.)\1{2,}', password):
            warnings.append("Password contains repeating characters")
            score -= 5
        
        # Check for sequential characters
        if not self.allow_sequential_chars and self._has_sequential_chars(password):
            warnings.append("Password contains sequential characters")
            score -= 5
        
        # Calculate final score
        score = max(0, min(100, score))
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'score': score,
        }
    
    def _is_common_password(self, password: str) -> bool:
        """Check if password is common"""
        common_passwords = [
            'password', '123456', '12345678', '1234', 'qwerty',
            'admin', 'welcome', 'password1', '123123',
        ]
        return password.lower() in common_passwords
    
    def _has_sequential_chars(self, password: str) -> bool:
        """Check for sequential characters"""
        for i in range(len(password) - 2):
            # Check numeric sequences
            if password[i:i+3].isdigit():
                if abs(ord(password[i]) - ord(password[i+1])) == 1 and \
                   abs(ord(password[i+1]) - ord(password[i+2])) == 1:
                    return True
            
            # Check alphabetical sequences
            if password[i:i+3].isalpha():
                if abs(ord(password[i].lower()) - ord(password[i+1].lower())) == 1 and \
                   abs(ord(password[i+1].lower()) - ord(password[i+2].lower())) == 1:
                    return True
        
        return False


class PasswordHistory(models.Model):
    """Password history for users"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_history')
    
    # Password data
    password_hash = models.CharField(max_length=128, null=True, blank=True)
    salt = models.CharField(max_length=128, null=True, blank=True)
    algorithm = models.CharField(max_length=50, default='pbkdf2_sha256', null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='changed_passwords')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Password Histories'
    
    def __str__(self):
        return f"{self.user.username} - {self.created_at}"
    
    @classmethod
    def is_password_used(cls, user, password: str) -> bool:
        """Check if password has been used before"""
        try:
            # Get recent passwords
            recent_passwords = cls.objects.filter(
                user=user
            ).order_by('-created_at')[:10]
            
            for password_history in recent_passwords:
                # Check if password matches any in history
                if check_password(password, password_history.password_hash):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking password history: {str(e)}")
            return False


class PasswordAttempt(models.Model):
    """Track password attempts for lockout"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_attempts')
    ip_address = models.GenericIPAddressField()
    successful = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-attempted_at']
        indexes = [
            models.Index(fields=['user', 'attempted_at']),
            models.Index(fields=['ip_address', 'attempted_at']),
        ]
    
    def __str__(self):
        status = "SUCCESS" if self.successful else "FAILED"
        return f"{self.user.username} - {status} - {self.attempted_at}"
    
    @classmethod
    def get_failed_attempts_count(cls, user, time_window_minutes=15) -> int:
        """Get count of failed attempts within time window"""
        time_ago = timezone.now() - timedelta(minutes=time_window_minutes)
        return cls.objects.filter(
            user=user,
            successful=False,
            attempted_at__gte=time_ago
        ).count()
    
    @classmethod
    def is_locked_out(cls, user) -> bool:
        """Check if user is locked out"""
        try:
            # Get password policy
            policy = PasswordPolicy.objects.filter(is_active=True).first()
            if not policy:
                return False
            
            # Check failed attempts
            failed_attempts = cls.get_failed_attempts_count(
                user, 
                time_window_minutes=policy.lockout_duration_minutes
            )
            
            return failed_attempts >= policy.max_failed_attempts
            
        except Exception as e:
            logger.error(f"Error checking lockout status: {str(e)}")
            return False


# ==================== SESSION MANAGEMENT SYSTEM ====================

class UserSession(models.Model):
    """Track user sessions for security"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sessions')
    
    # Session data
    session_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    session_data = models.TextField()
    
    # Device information
    device_info = models.ForeignKey(
        DeviceInfo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions')
    
    # Location information
    ip_address = models.GenericIPAddressField()
    geolocation = models.ForeignKey(
        GeolocationLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions')
    
    # Status
    is_active = models.BooleanField(default=True)
    is_compromised = models.BooleanField(default=False)
    force_logout = models.BooleanField(default=False)
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    # Metadata
    user_agent = models.TextField(blank=True)
    login_method = models.CharField(max_length=50, default='password', null=True, blank=True)  # password, 2fa, social, etc.
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        status = "ACTIVE" if self.is_active else "INACTIVE"
        return f"{self.user.username} - {status} - {self.created_at}"
    
    def clean(self):
        """Validate session"""
        super().clean()
        
        # Set default expiry (2 weeks)
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=14)
    
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return timezone.now() > self.expires_at
    
    def refresh(self):
        """Refresh session activity"""
        self.last_activity = timezone.now()
        # Extend expiry on activity (up to max 30 days)
        max_expiry = timezone.now() + timedelta(days=30)
        new_expiry = timezone.now() + timedelta(days=7)
        self.expires_at = min(new_expiry, max_expiry)
        self.save()
    
    def terminate(self, reason=""):
        """Terminate session"""
        self.is_active = False
        self.force_logout = True
        
        # Log termination
        SecurityLog.objects.create(
            user=self.user,
            security_type='session_hijack' if 'compromised' in reason else 'suspicious_activity',
            severity='high',
            ip_address=self.ip_address,
            device_info=self.device_info,
            description=f"Session terminated. Reason: {reason}",
            metadata={
                'session_key': self.session_key,
                'termination_reason': reason,
            }
        )
        
        self.save()
    
    @classmethod
    def get_active_sessions(cls, user):
        """Get all active sessions for user"""
        return cls.objects.filter(
            user=user,
            is_active=True,
            expires_at__gt=timezone.now()
        )
    
    @classmethod
    def terminate_all_other_sessions(cls, current_session, user):
        """Terminate all other sessions for user (except current)"""
        other_sessions = cls.get_active_sessions(user).exclude(
            session_key=current_session.session_key
        )
        
        for session in other_sessions:
            session.terminate("Terminated by new login")
        
        return other_sessions.count()


class SessionActivity(models.Model):
    """Log session activities"""
    ACTIVITY_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('refresh', 'Refresh'),
        ('password_change', 'Password Change'),
        ('profile_update', 'Profile Update'),
        ('sensitive_action', 'Sensitive Action'),
        ('session_hijack_attempt', 'Session Hijack Attempt'),
    ]
    
    session = models.ForeignKey(
        UserSession,
        on_delete=models.CASCADE,
        related_name='activities')
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES, null=True, blank=True)
    
    # Context
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    endpoint = models.CharField(max_length=500, null=True, blank=True)
    
    # Data
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', 'activity_type']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.session.user.username} - {self.activity_type} - {self.created_at}"


# ==================== TWO-FACTOR AUTHENTICATION (2FA) SYSTEM ====================

class TwoFactorMethod(models.Model):
    """2FA methods for users"""
    METHOD_TYPES = [
        ('totp', 'TOTP (Google Authenticator)'),
        ('sms', 'SMS'),
        ('email', 'Email'),
        ('backup_code', 'Backup Code'),
        ('security_key', 'Security Key (WebAuthn)'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='two_factor_methods')
    method_type = models.CharField(max_length=20, choices=METHOD_TYPES, null=True, blank=True)
    is_primary = models.BooleanField(default=False)
    is_enabled = models.BooleanField(default=False)
    
    # Method-specific data
    secret_key = models.CharField(max_length=100, null=True, blank=True)  # For TOTP
    phone_number = models.CharField(max_length=20, null=True, blank=True)  # For SMS
    email = models.EmailField(blank=True)  # For email
    backup_codes = models.JSONField(default=list, blank=True)  # List of backup codes
    
    # Security
    failed_attempts = models.IntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-is_primary', 'method_type']
        unique_together = [['user', 'method_type']]
    
    def __str__(self):
        status = "ENABLED" if self.is_enabled else "DISABLED"
        return f"{self.user.username} - {self.method_type} - {status}"
    
    def clean(self):
        """Validate 2FA method"""
        super().clean()
        
        # Ensure only one primary method
        if self.is_primary and self.is_enabled:
            TwoFactorMethod.objects.filter(
                user=self.user,
                is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
    
    def generate_backup_codes(self, count=10) -> list:
        """Generate backup codes"""
        codes = []
        for _ in range(count):
            # Generate 8-character alphanumeric code
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            # Format with hyphens for readability
            formatted_code = '-'.join([code[i:i+4] for i in range(0, len(code), 4)])
            codes.append(formatted_code)
        
        # Hash codes before storing
        hashed_codes = [hashlib.sha256(code.encode()).hexdigest() for code in codes]
        self.backup_codes = hashed_codes
        self.save()
        
        return codes
    
    def verify_backup_code(self, code: str) -> bool:
        """Verify backup code"""
        if not self.backup_codes:
            return False
        
        # Hash the provided code
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        # Check if hash exists in backup codes
        if code_hash in self.backup_codes:
            # Remove used code
            self.backup_codes.remove(code_hash)
            self.save()
            return True
        
        return False
    
    def reset(self):
        """Reset 2FA method"""
        self.secret_key = ''
        self.backup_codes = []
        self.is_enabled = False
        self.failed_attempts = 0
        self.save()


class TwoFactorAttempt(models.Model):
    """Track 2FA attempts"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='two_factor_attempts')
    method = models.ForeignKey(
        TwoFactorMethod,
        on_delete=models.CASCADE,
        related_name='attempts',)
    
    # Attempt data
    code = models.CharField(max_length=100, null=True, blank=True)
    successful = models.BooleanField(default=False)
    
    # Context
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    device_info = models.ForeignKey(
        DeviceInfo,
        on_delete=models.SET_NULL,
        null=True,)
    
    attempted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-attempted_at']
        indexes = [
            models.Index(fields=['user', 'successful']),
            models.Index(fields=['ip_address', 'attempted_at']),
        ]
    
    def __str__(self):
        status = "SUCCESS" if self.successful else "FAILED"
        return f"{self.user.username} - 2FA - {status} - {self.attempted_at}"


class TwoFactorRecoveryCode(models.Model):
    """2FA recovery codes for emergency access"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recovery_codes')
    
    # Code information
    code_hash = models.CharField(max_length=64, null=True, blank=True)  # SHA-256 hash of code
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    
    # Security
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Expiry
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        status = "USED" if self.is_used else "VALID"
        return f"{self.user.username} - Recovery Code - {status}"
    
    def is_valid(self) -> bool:
        """Check if recovery code is valid"""
        if self.is_used:
            return False
        
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        
        return True
    
    def mark_used(self, ip_address=None, user_agent=None):
        """Mark recovery code as used"""
        self.is_used = True
        self.used_at = timezone.now()
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.save()
    
    @classmethod
    def verify_code(cls, user, code: str) -> bool:
        """Verify recovery code"""
        try:
            # Hash the code
            code_hash = hashlib.sha256(code.encode()).hexdigest()
            
            # Find valid recovery code
            recovery_code = cls.objects.filter(
                user=user,
                code_hash=code_hash,
                is_used=False,
                expires_at__gt=timezone.now()
            ).first()
            
            if recovery_code:
                recovery_code.mark_used()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error verifying recovery code: {str(e)}")
            return False


# ==================== SIGNAL HANDLERS ====================

@receiver(post_save, sender=SecurityLog)
def handle_new_security_log(sender, instance, created, **kwargs):
    """Handle new security log entry"""
    if created:
        # Update user's risk score
        if instance.user:
            try:
                risk_score = RiskScore.objects.filter(user=instance.user).first()
                if risk_score:
                    risk_score.suspicious_activities += 1
                    risk_score.last_suspicious_activity = timezone.now()
                    risk_score.update_score()
            except Exception as e:
                logger.error(f"Error updating risk score: {str(e)}")
        
        # Check for auto-block rules
        if instance.severity in ['high', 'critical']:
            try:
                rules = AutoBlockRule.objects.filter(is_active=True)
                for rule in rules:
                    if rule.evaluate(instance.user, instance.ip_address, instance.device_info):
                        rule.take_action(
                            instance.user,
                            instance.ip_address,
                            instance.device_info,
                            f"Security log severity: {instance.severity}"
                        )
            except Exception as e:
                logger.error(f"Error checking auto-block rules: {str(e)}")


@receiver(post_save, sender=UserSession)
def handle_session_activity(sender, instance, created, **kwargs):
    """Handle session activity"""
    if created:
        # Log session creation
        SessionActivity.objects.create(
            session=instance,
            activity_type='login',
            ip_address=instance.ip_address,
            user_agent=instance.user_agent,
            endpoint='session/create'
        )
        
        # Check for suspicious session creation
        active_sessions = UserSession.get_active_sessions(instance.user)
        if active_sessions.count() > 5:  # Too many active sessions
            SecurityLog.objects.create(
                user=instance.user,
                security_type='suspicious_activity',
                severity='medium',
                ip_address=instance.ip_address,
                device_info=instance.device_info,
                description=f"Multiple active sessions detected: {active_sessions.count()}",
                metadata={'session_count': active_sessions.count()}
            )


@receiver(post_save, sender=TwoFactorAttempt)
def handle_2fa_attempt(sender, instance, created, **kwargs):
    """Handle 2FA attempt"""
    if created and not instance.successful:
        # Increment failed attempts
        if instance.method:
            instance.method.failed_attempts += 1
            instance.method.save()
        
        # Check for excessive failed attempts
        time_window = timezone.now() - timedelta(minutes=15)
        failed_attempts = TwoFactorAttempt.objects.filter(
            user=instance.user,
            successful=False,
            attempted_at__gte=time_window
        ).count()
        
        if failed_attempts >= 5:
            SecurityLog.objects.create(
                user=instance.user,
                security_type='suspicious_activity',
                severity='high',
                ip_address=instance.ip_address,
                device_info=instance.device_info,
                description=f"Multiple failed 2FA attempts: {failed_attempts}",
                metadata={'failed_attempts': failed_attempts}
            )


# ==================== MODEL METHODS WITH DEFENSIVE CODING ====================

def get_safe_model_field(model_instance, field_name, default=None):
    """Safely get model field value"""
    try:
        return getattr(model_instance, field_name, default)
    except (AttributeError, ValueError, TypeError):
        return default


def safe_model_save(model_instance, **kwargs):
    """Safely save model instance"""
    try:
        model_instance.full_clean()
        model_instance.save(**kwargs)
        return True
    except ValidationError as e:
        logger.error(f"Validation error saving {model_instance}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error saving {model_instance}: {e}")
        return False


# ==================== ENHANCED EXISTING MODELS ====================

class UserBan(models.Model):
    """UserBan model implementing defensive coding principles"""
    
    # 1. Null Object Pattern and default values
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE, 
        related_name='security_bans',
        verbose_name="User",
        help_text="The user who is banned")
    
    reason = models.TextField(
        verbose_name="Reason",
        help_text="Detailed reason for the ban",
        default="No reason provided",  # Default value
        blank=False,
        null=False
    )
    
    is_permanent = models.BooleanField(
        default=False,
        verbose_name="Permanent Ban",
        help_text="Check if this is a permanent ban"
    )
    
    banned_until = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="Ban Until",
        help_text="End date for temporary ban"
    )
    
    banned_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Banned At",
        help_text="When the ban started"
    )
    
    is_active_ban = models.BooleanField(
        default=True,
        verbose_name="Active Ban",
        help_text="Whether this ban is currently active"
    )
    
    # 2. Model-level constraints
    class Meta:
        db_table = 'security_userban'
        verbose_name = 'User Ban'
        verbose_name_plural = 'User Bans'
        
        # Ensure only one active ban per user
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'is_active_ban'],
                condition=models.Q(is_active_ban=True),
                name='unique_active_ban_per_user'
            )
        ]
        indexes = [
            models.Index(fields=['user', 'is_active_ban']),
            models.Index(fields=['banned_until']),
            models.Index(fields=['banned_at']),
        ]
    
    # 3. Validation in clean method
    def clean(self) -> None:
        """Validate model data before saving"""
        errors = {}
        
        # Type validation and logical constraints
        if self.is_permanent and self.banned_until:
            errors['banned_until'] = "Permanent bans cannot have an expiration date."
        
        if not self.is_permanent and not self.banned_until:
            errors['banned_until'] = "Temporary bans must have an expiration date."
        
        if self.banned_until and self.banned_until <= timezone.now():
            errors['banned_until'] = "Ban expiration must be in the future."
        
        # Graceful degradation: Log issues but don't crash
        if errors:
            logger.warning(f"UserBan validation errors: {errors}")
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs) -> None:
        """Override save with defensive programming"""
        try:
            # Auto-clean before saving
            self.full_clean()
            
            # Set sensible defaults
            if self.is_permanent:
                self.banned_until = None
            
            # Ensure consistency
            if self.banned_until and self.banned_until <= timezone.now():
                self.is_active_ban = False
            
            super().save(*args, **kwargs)
            
        except Exception as e:
            # Graceful degradation: Log error but don't crash
            logger.error(f"Failed to save UserBan: {e}")
            raise
    
    # 4. Business logic methods with type hints
    def is_currently_active(self) -> bool:
        """Check if ban is currently active"""
        if not self.is_active_ban:
            return False
        
        if self.is_permanent:
            return True
        
        if self.banned_until:
            return timezone.now() < self.banned_until
        
        return False
    
    def get_remaining_duration(self) -> Optional[timedelta]:
        """Get remaining ban duration with null safety"""
        if not self.is_currently_active():
            return None
        
        if self.is_permanent:
            return None  # Infinite duration
        
        if self.banned_until:
            return self.banned_until - timezone.now()
        
        return None
    
    def deactivate_ban(self, reason: str = "Manually deactivated") -> Tuple[bool, str]:
        """Safely deactivate a ban with error handling"""
        try:
            if not self.is_active_ban:
                return False, "Ban is already inactive"
            
            self.is_active_ban = False
            self.reason = f"{self.reason} | Deactivated: {reason}"
            self.save()
            
            logger.info(f"Ban {self.id} deactivated for user {self.user.id}")
            return True, "Ban successfully deactivated"
            
        except Exception as e:
            logger.error(f"Failed to deactivate ban {self.id}: {e}")
            return False, f"Error deactivating ban: {str(e)}"
    
    # 5. Factory method for creating bans
    @classmethod
    def create_temporary_ban(cls, user, reason: str, days: int = 7) -> 'UserBan':
        """Factory method for creating temporary bans"""
        if days <= 0:
            raise ValueError("Ban duration must be positive")
        
        # Check for existing active bans first
        existing_ban = cls.objects.filter(
            user=user,
            is_active_ban=True
        ).first()
        
        if existing_ban:
            raise ValidationError(f"User {user.id} already has an active ban")
        
        return cls(
            user=user,
            reason=reason,
            is_permanent=False,
            banned_until=timezone.now() + timedelta(days=days),
            is_active_ban=True
        )
    
    @classmethod
    def create_permanent_ban(cls, user, reason: str) -> 'UserBan':
        """Factory method for creating permanent bans"""
        # Check for existing active bans
        existing_ban = cls.objects.filter(
            user=user,
            is_active_ban=True
        ).first()
        
        if existing_ban:
            raise ValidationError(f"User {user.id} already has an active ban")
        
        return cls(
            user=user,
            reason=reason,
            is_permanent=True,
            banned_until=None,
            is_active_ban=True
        )
    
    # 6. Query methods for common operations
    @classmethod
    def get_active_bans(cls, user_id: Optional[int] = None):
        """Get all currently active bans"""
        queryset = cls.objects.filter(is_active_ban=True)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by expiration for temporary bans
        now = timezone.now()
        return queryset.filter(
            models.Q(is_permanent=True) |
            models.Q(banned_until__gt=now)
        )
    
    @classmethod
    def is_user_banned(cls, user_id: int) -> Tuple[bool, Optional['UserBan']]:
        """Check if a user is currently banned"""
        try:
            active_bans = cls.get_active_bans(user_id=user_id)
            ban = active_bans.first()
            return (ban is not None, ban)
        except Exception as e:
            # Graceful degradation: Log error but return safe default
            logger.error(f"Error checking ban status for user {user_id}: {e}")
            return (False, None)
    
    @classmethod
    def cleanup_expired_bans(cls) -> int:
        """Clean up expired temporary bans - returns count of cleaned bans"""
        try:
            now = timezone.now()
            expired_bans = cls.objects.filter(
                is_active_ban=True,
                is_permanent=False,
                banned_until__lte=now
            )
            
            count = expired_bans.count()
            expired_bans.update(is_active_ban=False)
            
            if count > 0:
                logger.info(f"Cleaned up {count} expired bans")
            
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired bans: {e}")
            return 0
    
    # 7. String representation and admin methods
    def __str__(self) -> str:
        ban_type = "Permanent" if self.is_permanent else "Temporary"
        status = "Active" if self.is_currently_active() else "Inactive"
        return f"{ban_type} Ban for {self.user} - {status}"
    
    @property
    def duration_info(self) -> str:
        """User-friendly duration information"""
        if self.is_permanent:
            return "Permanent"
        
        if not self.banned_until:
            return "Unknown duration"
        
        remaining = self.get_remaining_duration()
        if remaining:
            days = remaining.days
            return f"{days} day(s) remaining"
        
        return "Expired"


@receiver(pre_save, sender=UserBan)
def validate_ban_consistency(sender, instance, **kwargs):
    """Signal handler for additional validation"""
    if instance.is_permanent:
        instance.banned_until = None
    
    # Ensure banned_until is in future for temporary bans
    if instance.banned_until and instance.banned_until <= timezone.now():
        instance.is_active_ban = False




class EnhancedUserBan(UserBan):
    """Enhanced UserBan with defensive coding"""
    
    class Meta:
        proxy = True
    
    def is_active(self) -> bool:
        """Check if ban is currently active with defensive coding"""
        try:
            if self.is_permanent:
                return True
            
            if self.banned_until and timezone.now() < self.banned_until:
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error checking ban status: {str(e)}")
            return False  # Graceful degradation
    
    def time_remaining(self) -> str:
        """Get remaining ban time with defensive coding"""
        try:
            if self.is_permanent:
                return "Permanent"
            
            if self.banned_until:
                remaining = self.banned_until - timezone.now()
                if remaining.total_seconds() > 0:
                    days = remaining.days
                    hours = remaining.seconds // 3600
                    minutes = (remaining.seconds % 3600) // 60
                    return f"{days}d {hours}h {minutes}m"
            
            return "Expired"
        except Exception as e:
            logger.error(f"Error calculating ban time: {str(e)}")
            return "Unknown"


class GracefulDegradation:
    """Decorator for implementing graceful degradation pattern"""
    
    def __init__(self, default_return=None, log_error=True):
        self.default_return = default_return
        self.log_error = log_error
    
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if self.log_error:
                    logger.error(f"Error in {func.__name__}: {str(e)}")
                return self.default_return
        return wrapper
    
    @classmethod
    def with_default(cls, default_value):
        """Factory method to create decorator with specific default value"""
        return cls(default_return=default_value)


class ClickTracker(models.Model):
    """
    Base ClickTracker model with comprehensive defensive coding
    Type checking, validation, and null object pattern enriched model
    """
    
    # Null Object Pattern: All fields have default values
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='click_trackers',
        verbose_name="User",
        help_text="User who performed the click",
        null=True,  # Allow anonymous clicks
        blank=True)
    
    action_type = models.CharField(
        max_length=100,
        verbose_name="Action Type",
        help_text="Type of click (e.g., button_click, link_click, null=True, blank=True)",
        default="unknown",  # Default value
        db_index=True
    )
    
    ip_address = models.GenericIPAddressField(
        verbose_name="IP Address",
        help_text="User's IP address",
        default="0.0.0.0",  # Default value
        null=True,
        blank=True
    )
    
    user_agent = models.TextField(
        verbose_name="User Agent",
        help_text="Browser/device user agent",
        default="",  # Default value
    )
    
    device_info = models.JSONField(
        verbose_name="Device Information",
        help_text="Device/browser details",
        default=dict,  # Default empty dict
        blank=True,
        null=True
    )
    
    metadata = models.JSONField(
        verbose_name="Additional Metadata",
        help_text="Any additional click data",
        default=dict,  # Default empty dict
    )
    
    referer = models.URLField(
        verbose_name="Referer URL",
        max_length=500,
        blank=True,
        null=True,
        default="")
    
    page_url = models.URLField(
        verbose_name="Page URL",
        max_length=500,
        default="")
    
    element_id = models.CharField(
        max_length=200,
        verbose_name="Element ID",
        help_text="HTML element ID that was clicked",
        blank=True,
        null=True,
        default="")
    
    session_id = models.CharField(
        max_length=100,
        verbose_name="Session ID",
        help_text="User session identifier",
        blank=True,
        null=True,
        default="")
    
    is_suspicious = models.BooleanField(
        verbose_name="Is Suspicious",
        help_text="Flag for suspicious click patterns",
        default=False
    )
    
    risk_score = models.FloatField(
        verbose_name="Risk Score",
        help_text="Calculated risk score (0-100)",
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    clicked_at = models.DateTimeField(
        verbose_name="Clicked At",
        auto_now_add=True,
        db_index=True
    )
    
    # Model-Level Constraints
    class Meta:
        db_table = 'security_clicktracker'
        verbose_name = 'Click Tracker'
        verbose_name_plural = 'Click Trackers'
        
        # Database indexes for performance
        indexes = [
            Index(fields=['user', 'clicked_at']),
            Index(fields=['action_type', 'clicked_at']),
            Index(fields=['ip_address', 'clicked_at']),
            Index(fields=['is_suspicious']),
            Index(fields=['session_id']),
        ]
        
        # Order by most recent first
        ordering = ['-clicked_at']
    
    # Type Hinting: All methods have proper type hints
    def clean(self) -> None:
        """Validate model data before saving"""
        errors = {}
        
        # Type validation
        try:
            # Validate risk score range
            if not 0 <= self.risk_score <= 100:
                errors['risk_score'] = "Risk score must be between 0 and 100"
            
            # Validate action_type length
            if len(self.action_type) > 100:
                errors['action_type'] = "Action type cannot exceed 100 characters"
            
            # Validate JSON fields
            if self.device_info and not isinstance(self.device_info, dict):
                errors['device_info'] = "Device info must be a valid JSON object"
            
            if self.metadata and not isinstance(self.metadata, dict):
                errors['metadata'] = "Metadata must be a valid JSON object"
            
            # Validate URLs
            if self.referer and len(self.referer) > 500:
                errors['referer'] = "Referer URL is too long"
            
            if self.page_url and len(self.page_url) > 500:
                errors['page_url'] = "Page URL is too long"
        
        except Exception as e:
            # Graceful Degradation: Log error but don't crash
            logger.error(f"ClickTracker validation error: {e}")
            errors['non_field_errors'] = "An unexpected validation error occurred"
        
        if errors:
            raise ValidationError(errors)
    
    @GracefulDegradation.with_default(None)
    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save with defensive programming"""
        try:
            # Auto-clean before saving
            self.full_clean()
            
            # Set defaults if not provided
            if not self.device_info:
                self.device_info = {}
            
            if not self.metadata:
                self.metadata = {}
            
            # Auto-calculate risk score if not set
            if self.risk_score == 0:
                self.risk_score = self._calculate_risk_score()
            
            super().save(*args, **kwargs)
            
        except ValidationError:
            raise
        except Exception as e:
            # Graceful Degradation: Log but don't crash
            logger.error(f"Failed to save ClickTracker: {e}")
            raise
    
    def _calculate_risk_score(self) -> float:
        """Calculate risk score based on various factors"""
        score = 0.0
        
        try:
            # No user (anonymous) adds risk
            if not self.user:
                score += 20
            
            # Empty user agent adds risk
            if not self.user_agent or len(self.user_agent) < 10:
                score += 10
            
            # Check for suspicious IP patterns
            if self.ip_address:
                if self.ip_address.startswith('192.168.'):
                    score -= 5  # Local IP, lower risk
                elif self.ip_address == '0.0.0.0':
                    score += 30  # Invalid IP, high risk
            
            # Check action type
            suspicious_actions = ['login', 'signup', 'password_reset', 'purchase']
            if self.action_type in suspicious_actions:
                score += 15
            
            # Normalize score to 0-100 range
            score = max(0, min(100, score))
            
        except Exception as e:
            # Graceful Degradation: Return default score on error
            logger.error(f"Error calculating risk score: {e}")
            score = 50.0  # Medium risk as default
        
        return score
    
    # Business logic methods with type hints
    def get_click_details(self) -> Dict[str, Any]:
        """Safely get click details"""
        try:
            return {
                'id': self.id,
                'user_id': self.user.id if self.user else None,
                'action_type': self.action_type,
                'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None,
                'ip_address': self.ip_address,
                'page_url': self.page_url,
                'risk_score': self.risk_score,
                'is_suspicious': self.is_suspicious,
                'device_info': self.device_info or {},
                'metadata': self.metadata or {}
            }
        except Exception as e:
            # Graceful Degradation: Return safe default
            logger.error(f"Error getting click details for ID {self.id}: {e}")
            return {
                'error': 'Could not retrieve click details',
                'id': self.id
            }
    
    def mark_as_suspicious(self, reason: str = "Manual flag") -> Tuple[bool, str]:
        """Mark click as suspicious with error handling"""
        try:
            self.is_suspicious = True
            self.risk_score = min(100, self.risk_score + 30)  # Increase risk score
            
            # Add reason to metadata
            if not self.metadata:
                self.metadata = {}
            
            self.metadata['suspicion_reason'] = reason
            self.metadata['marked_suspicious_at'] = timezone.now().isoformat()
            
            self.save()
            
            logger.info(f"Marked click {self.id} as suspicious: {reason}")
            return True, "Click marked as suspicious"
            
        except Exception as e:
            logger.error(f"Failed to mark click {self.id} as suspicious: {e}")
            return False, f"Error: {str(e)}"
    
    @classmethod
    @GracefulDegradation.with_default([])
    def get_recent_clicks(cls, 
                         user_id: Optional[int] = None,
                         hours: int = 24,
                         limit: int = 100) -> List['ClickTracker']:
        """Get recent clicks with defensive parameters"""
        try:
            queryset = cls.objects.all()
            
            # Add filters if provided
            if user_id:
                queryset = queryset.filter(user_id=user_id)
            
            # Time filter
            time_threshold = timezone.now() - timedelta(hours=hours)
            queryset = queryset.filter(clicked_at__gte=time_threshold)
            
            # Apply limit safely
            limit = max(1, min(1000, limit))  # Constrain limit
            
            return list(queryset[:limit])
            
        except Exception as e:
            logger.error(f"Error getting recent clicks: {e}")
            return []
    
    @classmethod
    @GracefulDegradation.with_default(0)
    def get_click_count(cls,
                       user_id: Optional[int] = None,
                       action_type: Optional[str] = None,
                       time_window: Optional[timedelta] = None) -> int:
        """Get click count with various filters"""
        try:
            queryset = cls.objects.all()
            
            if user_id:
                queryset = queryset.filter(user_id=user_id)
            
            if action_type:
                queryset = queryset.filter(action_type=action_type)
            
            if time_window:
                time_threshold = timezone.now() - time_window
                queryset = queryset.filter(clicked_at__gte=time_threshold)
            
            return queryset.count()
            
        except Exception as e:
            logger.error(f"Error getting click count: {e}")
            return 0
    
    # Factory methods
    @classmethod
    def create_click(cls,
                    user=None,
                    action_type: str = "click",
                    ip_address: Optional[str] = None,
                    user_agent: Optional[str] = None,
                    page_url: Optional[str] = None,
                    **kwargs) -> 'ClickTracker':
        """Factory method for creating click records"""
        try:
            # Validate required parameters
            if not action_type:
                action_type = "unknown"
            
            # Create click record
            click = cls(
                user=user,
                action_type=action_type,
                ip_address=ip_address or "0.0.0.0",
                user_agent=user_agent or "",
                page_url=page_url or "",
                **kwargs
            )
            
            # Add additional metadata
            if kwargs.get('metadata'):
                click.metadata = {**click.metadata, **kwargs['metadata']}
            
            click.save()
            return click
            
        except Exception as e:
            logger.error(f"Error creating click record: {e}")
            # Graceful Degradation: Return a minimal valid object
            return cls.objects.create(
                action_type="error_fallback",
                metadata={'error': str(e), 'original_action': action_type}
            )
    
    def __str__(self) -> str:
        """String representation with null safety"""
        user_info = self.user.username if self.user else "Anonymous"
        return f"{user_info} - {self.action_type} at {self.clicked_at}"
    
    @property
    def time_since_click(self) -> str:
        """Human-readable time since click"""
        try:
            if not self.clicked_at:
                return "Unknown"
            
            delta = timezone.now() - self.clicked_at
            
            if delta.days > 0:
                return f"{delta.days} days ago"
            elif delta.seconds > 3600:
                hours = delta.seconds // 3600
                return f"{hours} hours ago"
            elif delta.seconds > 60:
                minutes = delta.seconds // 60
                return f"{minutes} minutes ago"
            else:
                return "Just now"
                
        except Exception:
            return "Time unknown"


# # Enhanced ClickTracker Proxy Model
# class EnhancedClickTracker(ClickTracker):
#     """
#     Proxy model extending ClickTracker with enhanced security features
#     and defensive coding patterns
#     """
    
#     class Meta:
#         proxy = True
#         verbose_name = 'Enhanced Click Tracker'
#         verbose_name_plural = 'Enhanced Click Trackers'
    
#     @classmethod
#     @GracefulDegradation.with_default(False)
#     def check_fast_clicking(cls, 
#                            user, 
#                            action_type: str, 
#                            time_window: int = 60, 
#                            max_clicks: int = 5) -> bool:
#         """
#         Check if user is clicking too fast with defensive coding
#         Returns True if suspicious, False otherwise
#         """
#         try:
#             # Parameter validation
#             if not user or not action_type:
#                 return False
            
#             if time_window <= 0 or max_clicks <= 0:
#                 logger.warning(f"Invalid parameters: time_window={time_window}, max_clicks={max_clicks}")
#                 return False
            
#             # Generate cache key
#             cache_key = f'click_rate:{user.id}:{action_type}:{time_window}'
            
#             # Try cache first (Graceful Degradation)
#             try:
#                 cached_result = cache.get(cache_key)
#                 if cached_result is not None:
#                     return cached_result >= max_clicks
#             except Exception as e:
#                 logger.warning(f"Cache check failed: {e}")
#                 # Continue with database query if cache fails
            
#             # Calculate time threshold
#             time_threshold = timezone.now() - timedelta(seconds=time_window)
            
#             # Count recent clicks
#             recent_count = cls.objects.filter(
#                 user=user,
#                 action_type=action_type,
#                 clicked_at__gte=time_threshold,
#                 is_suspicious=False  # Don't count already suspicious clicks
#             ).count()
            
#             # Update cache
#             try:
#                 cache.set(cache_key, recent_count, time_window)
#             except Exception as e:
#                 logger.warning(f"Cache set failed: {e}")
            
#             # Return result
#             is_suspicious = recent_count >= max_clicks
            
#             # Auto-mark as suspicious if threshold exceeded
#             if is_suspicious:
#                 logger.warning(
#                     f"Fast clicking detected: User {user.id}, "
#                     f"Action: {action_type}, "
#                     f"Clicks: {recent_count}/{max_clicks} in {time_window}s"
#                 )
                
#                 # Mark recent clicks as suspicious
#                 recent_clicks = cls.objects.filter(
#                     user=user,
#                     action_type=action_type,
#                     clicked_at__gte=time_threshold,
#                     is_suspicious=False
#                 )[:5]  # Limit to 5 clicks
                
#                 for click in recent_clicks:
#                     click.mark_as_suspicious(
#                         reason=f"Fast clicking detected ({recent_count} clicks in {time_window}s)"
#                     )
            
#             return is_suspicious
            
#         except Exception as e:
#             logger.error(f"Error in check_fast_clicking: {e}")
#             return False  # Graceful degradation: Assume not suspicious on error
    
#     @classmethod
#     @GracefulDegradation.with_default(None)
#     def log_action(cls,
#                   user=None,
#                   action_type: str = "click",
#                   ip_address: Optional[str] = None,
#                   device_info: Optional[Dict] = None,
#                   metadata: Optional[Dict] = None,
#                   **kwargs) -> Optional[ClickTracker]:
#         """
#         Log user action with comprehensive defensive coding
#         """
#         try:
#             # Input validation and sanitization
#             if not action_type or not isinstance(action_type, str):
#                 action_type = "unknown"
            
#             # Clean action_type
#             action_type = action_type.strip().lower()[:100]
            
#             # Get request information if available
#             request = kwargs.get('request')
#             if request:
#                 if not ip_address:
#                     ip_address = cls._get_client_ip(request)
                
#                 if not device_info:
#                     device_info = cls._extract_device_info(request)
            
#             # Create the click record
#             click = cls.create_click(
#                 user=user,
#                 action_type=action_type,
#                 ip_address=ip_address or "0.0.0.0",
#                 user_agent=device_info.get('user_agent') if device_info else "",
#                 page_url=metadata.get('page_url') if metadata else "",
#                 device_info=device_info or {},
#                 metadata=metadata or {},
#                 **{k: v for k, v in kwargs.items() if k not in ['request']}
#             )
            
#             # Check for suspicious patterns
#             if user and action_type:
#                 # Check fast clicking
#                 is_fast_clicking = cls.check_fast_clicking(
#                     user=user,
#                     action_type=action_type,
#                     time_window=60,  # 1 minute
#                     max_clicks=10    # 10 clicks per minute max
#                 )
                
#                 if is_fast_clicking:
#                     click.mark_as_suspicious(reason="Fast clicking pattern detected")
                
#                 # Check for repetitive actions
#                 is_repetitive = cls._check_repetitive_patterns(user, action_type)
#                 if is_repetitive:
#                     click.mark_as_suspicious(reason="Repetitive pattern detected")
            
#             return click
            
#         except Exception as e:
#             logger.error(f"Error logging action: {e}")
            
#             # Try to create a minimal error record
#             try:
#                 return cls.create_click(
#                     action_type="error_logging_failed",
#                     metadata={
#                         'error': str(e),
#                         'original_action': action_type,
#                         'user_id': user.id if user else None
#                     }
#                 )
#             except:
#                 return None
    
#     @staticmethod
#     @GracefulDegradation.with_default("0.0.0.0")
#     def _get_client_ip(request) -> str:
#         """Safely extract client IP from request"""
#         try:
#             x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
#             if x_forwarded_for:
#                 ip = x_forwarded_for.split(',')[0].strip()
#             else:
#                 ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
            
#             # Validate IP format
#             if ip and len(ip) <= 45:  # Max length for IPv6
#                 return ip
            
#             return "0.0.0.0"
#         except Exception:
#             return "0.0.0.0"
    
#     @staticmethod
#     @GracefulDegradation.with_default({})
#     def _extract_device_info(request) -> Dict[str, Any]:
#         """Safely extract device information from request"""
#         try:
#             user_agent = request.META.get('HTTP_USER_AGENT', '')
            
#             device_info = {
#                 'user_agent': user_agent[:500],  # Limit length
#                 'browser': cls._parse_browser(user_agent),
#                 'platform': cls._parse_platform(user_agent),
#                 'is_mobile': any(mobile in user_agent.lower() for mobile in [
#                     'mobile', 'android', 'iphone', 'ipad'
#                 ]),
#                 'accept_language': request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
#                 'referer': request.META.get('HTTP_REFERER', '')[:500],
#             }
            
#             return device_info
            
#         except Exception:
#             return {}
    
#     @staticmethod
#     @GracefulDegradation.with_default("Unknown")
#     def _parse_browser(user_agent: str) -> str:
#         """Parse browser from user agent string"""
#         try:
#             user_agent = user_agent.lower()
            
#             browsers = {
#                 'chrome': 'Chrome',
#                 'firefox': 'Firefox',
#                 'safari': 'Safari',
#                 'edge': 'Edge',
#                 'opera': 'Opera',
#                 'ie': 'Internet Explorer',
#                 'brave': 'Brave'
#             }
            
#             for key, name in browsers.items():
#                 if key in user_agent:
#                     return name
            
#             return 'Unknown'
#         except Exception:
#             return 'Unknown'
    
#     @staticmethod
#     @GracefulDegradation.with_default("Unknown")
#     def _parse_platform(user_agent: str) -> str:
#         """Parse platform from user agent string"""
#         try:
#             user_agent = user_agent.lower()
            
#             platforms = {
#                 'windows': 'Windows',
#                 'macintosh': 'macOS',
#                 'linux': 'Linux',
#                 'android': 'Android',
#                 'iphone': 'iOS',
#                 'ipad': 'iOS'
#             }
            
#             for key, name in platforms.items():
#                 if key in user_agent:
#                     return name
            
#             return 'Unknown'
#         except Exception:
#             return 'Unknown'
    
#     @classmethod
#     @GracefulDegradation.with_default(False)
#     def _check_repetitive_patterns(cls, user, action_type: str) -> bool:
#         """Check for repetitive click patterns"""
#         try:
#             # Check last hour
#             one_hour_ago = timezone.now() - timedelta(hours=1)
            
#             similar_actions = cls.objects.filter(
#                 user=user,
#                 action_type=action_type,
#                 clicked_at__gte=one_hour_ago
#             ).count()
            
#             # Threshold: more than 50 similar actions in an hour
#             return similar_actions > 50
            
#         except Exception as e:
#             logger.error(f"Error checking repetitive patterns: {e}")
#             return False
    
#     @classmethod
#     @GracefulDegradation.with_default([])
#     def get_suspicious_activity(cls,
#                                hours: int = 24,
#                                min_risk_score: float = 70.0,
#                                limit: int = 50) -> List['EnhancedClickTracker']:
#         """Get suspicious activity with defensive parameters"""
#         try:
#             # Parameter validation
#             hours = max(1, min(720, hours))  # Limit 1-720 hours (1 month)
#             min_risk_score = max(0, min(100, min_risk_score))
#             limit = max(1, min(500, limit))
            
#             time_threshold = timezone.now() - timedelta(hours=hours)
            
#             suspicious_clicks = cls.objects.filter(
#                 clicked_at__gte=time_threshold,
#                 risk_score__gte=min_risk_score
#             ).order_by('-risk_score', '-clicked_at')[:limit]
            
#             return list(suspicious_clicks)
            
#         except Exception as e:
#             logger.error(f"Error getting suspicious activity: {e}")
#             return []
    
#     @classmethod
#     @GracefulDegradation.with_default({})
#     def get_user_click_stats(cls, user_id: int, days: int = 7) -> Dict[str, Any]:
#         """Get comprehensive click statistics for a user"""
#         try:
#             time_threshold = timezone.now() - timedelta(days=days)
            
#             # Get total clicks
#             total_clicks = cls.objects.filter(
#                 user_id=user_id,
#                 clicked_at__gte=time_threshold
#             ).count()
            
#             # Get clicks by action type
#             clicks_by_type = cls.objects.filter(
#                 user_id=user_id,
#                 clicked_at__gte=time_threshold
#             ).values('action_type').annotate(count=models.Count('id'))
            
#             # Get suspicious clicks
#             suspicious_clicks = cls.objects.filter(
#                 user_id=user_id,
#                 clicked_at__gte=time_threshold,
#                 is_suspicious=True
#             ).count()
            
#             # Calculate average risk score
#             avg_risk = cls.objects.filter(
#                 user_id=user_id,
#                 clicked_at__gte=time_threshold
#             ).aggregate(avg_risk=models.Avg('risk_score'))['avg_risk'] or 0.0
            
#             return {
#                 'user_id': user_id,
#                 'time_period_days': days,
#                 'total_clicks': total_clicks,
#                 'suspicious_clicks': suspicious_clicks,
#                 'average_risk_score': round(avg_risk, 2),
#                 'clicks_by_type': list(clicks_by_type),
#                 'analysis_timestamp': timezone.now().isoformat()
#             }
            
#         except Exception as e:
#             logger.error(f"Error getting user click stats for user {user_id}: {e}")
#             return {
#                 'user_id': user_id,
#                 'error': 'Could not retrieve statistics',
#                 'time_period_days': days
#             }
        
        
        
        
        # models.py - শুধুমাত্র সংশোধিত অংশ
class EnhancedClickTracker(ClickTracker):
    """
    Proxy model extending ClickTracker with enhanced security features
    and defensive coding patterns
    """
    
    class Meta:
        proxy = True
        verbose_name = 'Enhanced Click Tracker'
        verbose_name_plural = 'Enhanced Click Trackers'
    
    @classmethod
    @GracefulDegradation.with_default(False)
    def check_fast_clicking(cls, 
                           user, 
                           action_type: str, 
                           time_window: int = 60, 
                           max_clicks: int = 5) -> bool:
        """
        Check if user is clicking too fast with defensive coding
        Returns True if suspicious, False otherwise
        """
        try:
            # Parameter validation
            if not user or not action_type:
                return False
            
            if time_window <= 0 or max_clicks <= 0:
                logger.warning(f"Invalid parameters: time_window={time_window}, max_clicks={max_clicks}")
                return False
            
            # Generate cache key
            cache_key = f'click_rate:{user.id}:{action_type}:{time_window}'
            
            # Try cache first (Graceful Degradation)
            try:
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    return cached_result >= max_clicks
            except Exception as e:
                logger.warning(f"Cache check failed: {e}")
                # Continue with database query if cache fails
            
            # Calculate time threshold
            time_threshold = timezone.now() - timedelta(seconds=time_window)
            
            # Count recent clicks
            recent_count = cls.objects.filter(
                user=user,
                action_type=action_type,
                clicked_at__gte=time_threshold,
                is_suspicious=False  # Don't count already suspicious clicks
            ).count()
            
            # Update cache
            try:
                cache.set(cache_key, recent_count, time_window)
            except Exception as e:
                logger.warning(f"Cache set failed: {e}")
            
            # Return result
            is_suspicious = recent_count >= max_clicks
            
            # Auto-mark as suspicious if threshold exceeded
            if is_suspicious:
                logger.warning(
                    f"Fast clicking detected: User {user.id}, "
                    f"Action: {action_type}, "
                    f"Clicks: {recent_count}/{max_clicks} in {time_window}s"
                )
                
                # Mark recent clicks as suspicious
                recent_clicks = cls.objects.filter(
                    user=user,
                    action_type=action_type,
                    clicked_at__gte=time_threshold,
                    is_suspicious=False
                )[:5]  # Limit to 5 clicks
                
                for click in recent_clicks:
                    click.mark_as_suspicious(
                        reason=f"Fast clicking detected ({recent_count} clicks in {time_window}s)"
                    )
            
            return is_suspicious
            
        except Exception as e:
            logger.error(f"Error in check_fast_clicking: {e}")
            return False  # Graceful degradation: Assume not suspicious on error
    
    @classmethod
    @GracefulDegradation.with_default(None)
    def log_action(cls,
                  user=None,
                  action_type: str = "click",
                  ip_address: Optional[str] = None,
                  device_info: Optional[Dict] = None,
                  metadata: Optional[Dict] = None,
                  **kwargs) -> Optional[ClickTracker]:
        """
        Log user action with comprehensive defensive coding
        """
        try:
            # Input validation and sanitization
            if not action_type or not isinstance(action_type, str):
                action_type = "unknown"
            
            # Clean action_type
            action_type = action_type.strip().lower()[:100]
            
            # Get request information if available
            request = kwargs.get('request')
            if request:
                if not ip_address:
                    ip_address = cls._get_client_ip(request)
                
                if not device_info:
                    device_info = cls._extract_device_info(request)
            
            # Create the click record
            click = cls.create_click(
                user=user,
                action_type=action_type,
                ip_address=ip_address or "0.0.0.0",
                user_agent=device_info.get('user_agent') if device_info else "",
                page_url=metadata.get('page_url') if metadata else "",
                device_info=device_info or {},
                metadata=metadata or {},
                **{k: v for k, v in kwargs.items() if k not in ['request']}
            )
            
            # Check for suspicious patterns
            if user and action_type:
                # Check fast clicking
                is_fast_clicking = cls.check_fast_clicking(
                    user=user,
                    action_type=action_type,
                    time_window=60,  # 1 minute
                    max_clicks=10    # 10 clicks per minute max
                )
                
                if is_fast_clicking:
                    click.mark_as_suspicious(reason="Fast clicking pattern detected")
                
                # Check for repetitive actions
                is_repetitive = cls._check_repetitive_patterns(user, action_type)
                if is_repetitive:
                    click.mark_as_suspicious(reason="Repetitive pattern detected")
            
            return click
            
        except Exception as e:
            logger.error(f"Error logging action: {e}")
            
            # Try to create a minimal error record
            try:
                return cls.create_click(
                    action_type="error_logging_failed",
                    metadata={
                        'error': str(e),
                        'original_action': action_type,
                        'user_id': user.id if user else None
                    }
                )
            except:
                return None
    
    # এই মেথডগুলো EnhancedClickTracker ক্লাসের ভিতরে থাকবে
    @staticmethod
    @GracefulDegradation.with_default("0.0.0.0")
    def _get_client_ip(request) -> str:
        """Safely extract client IP from request"""
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
            
            # Validate IP format
            if ip and len(ip) <= 45:  # Max length for IPv6
                return ip
            
            return "0.0.0.0"
        except Exception:
            return "0.0.0.0"
    
    @staticmethod
    @GracefulDegradation.with_default({})
    def _extract_device_info(request) -> Dict[str, Any]:
        """Safely extract device information from request"""
        try:
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            
            device_info = {
                'user_agent': user_agent[:500],  # Limit length
                'browser': EnhancedClickTracker._parse_browser(user_agent),  # Static method call
                'platform': EnhancedClickTracker._parse_platform(user_agent),  # Static method call
                'is_mobile': any(mobile in user_agent.lower() for mobile in [
                    'mobile', 'android', 'iphone', 'ipad'
                ]),
                'accept_language': request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
                'referer': request.META.get('HTTP_REFERER', '')[:500],
            }
            
            return device_info
            
        except Exception:
            return {}
    
    @staticmethod
    @GracefulDegradation.with_default("Unknown")
    def _parse_browser(user_agent: str) -> str:
        """Parse browser from user agent string"""
        try:
            user_agent = user_agent.lower()
            
            browsers = {
                'chrome': 'Chrome',
                'firefox': 'Firefox',
                'safari': 'Safari',
                'edge': 'Edge',
                'opera': 'Opera',
                'ie': 'Internet Explorer',
                'brave': 'Brave'
            }
            
            for key, name in browsers.items():
                if key in user_agent:
                    return name
            
            return 'Unknown'
        except Exception:
            return 'Unknown'
    
    @staticmethod
    @GracefulDegradation.with_default("Unknown")
    def _parse_platform(user_agent: str) -> str:
        """Parse platform from user agent string"""
        try:
            user_agent = user_agent.lower()
            
            platforms = {
                'windows': 'Windows',
                'macintosh': 'macOS',
                'linux': 'Linux',
                'android': 'Android',
                'iphone': 'iOS',
                'ipad': 'iOS'
            }
            
            for key, name in platforms.items():
                if key in user_agent:
                    return name
            
            return 'Unknown'
        except Exception:
            return 'Unknown'
    
    @classmethod
    @GracefulDegradation.with_default(False)
    def _check_repetitive_patterns(cls, user, action_type: str) -> bool:
        """Check for repetitive click patterns"""
        try:
            # Check last hour
            one_hour_ago = timezone.now() - timedelta(hours=1)
            
            similar_actions = cls.objects.filter(
                user=user,
                action_type=action_type,
                clicked_at__gte=one_hour_ago
            ).count()
            
            # Threshold: more than 50 similar actions in an hour
            return similar_actions > 50
            
        except Exception as e:
            logger.error(f"Error checking repetitive patterns: {e}")
            return False
    
    @classmethod
    @GracefulDegradation.with_default([])
    def get_suspicious_activity(cls,
                               hours: int = 24,
                               min_risk_score: float = 70.0,
                               limit: int = 50) -> List['EnhancedClickTracker']:
        """Get suspicious activity with defensive parameters"""
        try:
            # Parameter validation
            hours = max(1, min(720, hours))  # Limit 1-720 hours (1 month)
            min_risk_score = max(0, min(100, min_risk_score))
            limit = max(1, min(500, limit))
            
            time_threshold = timezone.now() - timedelta(hours=hours)
            
            suspicious_clicks = cls.objects.filter(
                clicked_at__gte=time_threshold,
                risk_score__gte=min_risk_score
            ).order_by('-risk_score', '-clicked_at')[:limit]
            
            return list(suspicious_clicks)
            
        except Exception as e:
            logger.error(f"Error getting suspicious activity: {e}")
            return []
    
    @classmethod
    @GracefulDegradation.with_default({})
    def get_user_click_stats(cls, user_id: int, days: int = 7) -> Dict[str, Any]:
        """Get comprehensive click statistics for a user"""
        try:
            time_threshold = timezone.now() - timedelta(days=days)
            
            # Get total clicks
            total_clicks = cls.objects.filter(
                user_id=user_id,
                clicked_at__gte=time_threshold
            ).count()
            
            # Get clicks by action type
            clicks_by_type = cls.objects.filter(
                user_id=user_id,
                clicked_at__gte=time_threshold
            ).values('action_type').annotate(count=models.Count('id'))
            
            # Get suspicious clicks
            suspicious_clicks = cls.objects.filter(
                user_id=user_id,
                clicked_at__gte=time_threshold,
                is_suspicious=True
            ).count()
            
            # Calculate average risk score
            avg_risk = cls.objects.filter(
                user_id=user_id,
                clicked_at__gte=time_threshold
            ).aggregate(avg_risk=models.Avg('risk_score'))['avg_risk'] or 0.0
            
            return {
                'user_id': user_id,
                'time_period_days': days,
                'total_clicks': total_clicks,
                'suspicious_clicks': suspicious_clicks,
                'average_risk_score': round(avg_risk, 2),
                'clicks_by_type': list(clicks_by_type),
                'analysis_timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting user click stats for user {user_id}: {e}")
            return {
                'user_id': user_id,
                'error': 'Could not retrieve statistics',
                'time_period_days': days
            }
        


# ==================== UTILITY FUNCTIONS ====================

def validate_ip_address(ip_address: str) -> bool:
    """Validate IP address format"""
    try:
        ipaddress.ip_address(ip_address)
        return True
    except ValueError:
        return False


def sanitize_user_input(input_string: str, max_length: int = 500) -> str:
    """Sanitize user input"""
    if not isinstance(input_string, str):
        return ''
    
    # Trim whitespace
    sanitized = input_string.strip()
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized


def calculate_risk_level(score: int) -> str:
    """Calculate risk level from score"""
    if score >= 80:
        return 'critical'
    elif score >= 60:
        return 'high'
    elif score >= 40:
        return 'medium'
    elif score >= 20:
        return 'low'
    else:
        return 'very_low'


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    return ip


# ==================== SECURITY MIDDLEWARE INTEGRATION ====================

class SecurityMiddleware:
    """Security middleware for request validation"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Process request
        self.process_request(request)
        
        response = self.get_response(request)
        
        # Process response
        self.process_response(request, response)
        
        return response
    
    def process_request(self, request):
        """Process incoming request"""
        try:
            # Get client IP
            ip_address = get_client_ip(request)
            
            # Check IP blacklist
            if IPBlacklist.is_blocked(ip_address):
                raise PermissionDenied("IP address blocked")
            
            # Check geolocation
            geolocation = GeolocationLog.get_geolocation(ip_address)
            risk_assessment = geolocation.assess_risk()
            
            if risk_assessment['threat_level'] == 'high':
                # Log high-risk access
                SecurityLog.objects.create(
                    security_type='suspicious_activity',
                    severity='high',
                    ip_address=ip_address,
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    description=f"High-risk geolocation access: {risk_assessment}",
                )
            
        except Exception as e:
            logger.error(f"Error in security middleware: {str(e)}")
            # Don't block request on middleware error
    
    def process_response(self, request, response):
        """Process outgoing response"""
        try:
            # Add security headers
            response['X-Content-Type-Options'] = 'nosniff'
            response['X-Frame-Options'] = 'DENY'
            response['X-XSS-Protection'] = '1; mode=block'
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
            # Add rate limit headers if applicable
            if hasattr(request, 'rate_limit_info'):
                response['X-RateLimit-Limit'] = str(request.rate_limit_info['limit'])
                response['X-RateLimit-Remaining'] = str(request.rate_limit_info['remaining'])
                response['X-RateLimit-Reset'] = request.rate_limit_info['reset_time'].isoformat()
            
        except Exception as e:
            logger.error(f"Error adding security headers: {str(e)}")
        
        return response


# ==================== ADMIN PANEL ENHANCEMENTS ====================

class SecurityAdminMixin:
    """Mixin for security-related admin panels"""
    
    def get_queryset(self, request):
        """Get queryset with defensive coding"""
        try:
            qs = super().get_queryset(request)
            
            # Apply filters based on user permissions
            if not request.user.is_superuser:
                # Filter to show only relevant data
                qs = qs.filter(
                    Q(user=request.user) | 
                    Q(created_by=request.user)
                )
            
            return qs
            
        except Exception as e:
            logger.error(f"Error getting admin queryset: {str(e)}")
            return self.model.objects.none()
    
    def get_readonly_fields(self, request, obj=None):
        """Get readonly fields with defensive coding"""
        try:
            readonly_fields = list(super().get_readonly_fields(request, obj))
            
            # Make certain fields readonly based on object state
            if obj and hasattr(obj, 'status'):
                if obj.status in ['completed', 'cancelled']:
                    readonly_fields.extend(['status', 'processed_at'])
            
            return readonly_fields
            
        except Exception as e:
            logger.error(f"Error getting readonly fields: {str(e)}")
            return []
    
    def save_model(self, request, obj, form, change):
        """Save model with audit trail"""
        try:
            # Track who made the change
            if not change:
                obj.created_by = request.user
            else:
                obj.updated_by = request.user
            
            # Create audit trail
            AuditTrail.log_action(
                user=request.user,
                action_type='create' if not change else 'update',
                model_name=obj._meta.model_name,
                object_id=obj.pk,
                old_values=form.initial if change else {},
                new_values=form.cleaned_data,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            super().save_model(request, obj, form, change)
            
        except Exception as e:
            logger.error(f"Error saving model in admin: {str(e)}")
            raise


# ==================== API SECURITY UTILITIES ====================

def validate_api_request(request, required_params=None):
    """Validate API request with defensive coding"""
    try:
        # Check required parameters
        if required_params:
            for param in required_params:
                if param not in request.GET and param not in request.POST:
                    return False, f"Missing required parameter: {param}"
        
        # Validate content type for POST/PUT requests
        if request.method in ['POST', 'PUT', 'PATCH']:
            content_type = request.content_type
            if content_type not in ['application/json', 'application/x-www-form-urlencoded']:
                return False, f"Unsupported content type: {content_type}"
        
        # Validate request size
        if hasattr(request, 'content_length') and request.content_length:
            max_size = 10 * 1024 * 1024  # 10MB
            if request.content_length > max_size:
                return False, "Request too large"
        
        return True, "Valid"
        
    except Exception as e:
        logger.error(f"Error validating API request: {str(e)}")
        return False, f"Validation error: {str(e)}"


def sanitize_api_response(data):
    """Sanitize API response data"""
    try:
        if isinstance(data, dict):
            return {k: sanitize_api_response(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [sanitize_api_response(item) for item in data]
        elif isinstance(data, str):
            # Remove control characters except newline and tab
            import re
            data = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', data)
            return data
        else:
            return data
            
    except Exception as e:
        logger.error(f"Error sanitizing API response: {str(e)}")
        return {}


# ==================== DATABASE CONSTRAINTS ====================

class ModelConstraints:
    """Database constraint definitions"""
    
    @staticmethod
    def create_security_constraints():
        """Create additional database constraints"""
        constraints = []
        
        # Example constraint: Ensure risk_score is between 0-100
        constraints.append(
            models.CheckConstraint(
                check=models.Q(risk_score__gte=0) & models.Q(risk_score__lte=100),
                name='valid_risk_score'
            )
        )
        
        return constraints


# ==================== FINAL SETUP ====================
# NOTE: Security system initialization has been moved to api/security/apps.py ready() method
# This ensures models are loaded and database is ready before initialization
# Module-level initialization has been removed to prevent "Models aren't loaded yet" errors



class MaintenanceMode(models.Model):
    """
    MaintenanceMode model with comprehensive defensive coding
    For server maintenance mode management
    """
    
    # Null Object Pattern: Default values for all fields
    is_active = models.BooleanField(
        verbose_name="Is Active",
        help_text="Check if maintenance mode is active",
        default=False,
        db_index=True
    )
    
    title = models.CharField(
        max_length=200,
        verbose_name="Title",
        help_text="Maintenance mode title",
        default="Site Under Maintenance",
        blank=True)
    
    message = models.TextField(
        verbose_name="Message",
        help_text="Message for users",
        default="We are currently performing maintenance. Please check back shortly.",
    )
    
    start_time = models.DateTimeField(
        verbose_name="Start Time",
        help_text="Maintenance start time",
        default=timezone.now
    )
    
    estimated_end_time = models.DateTimeField(
        verbose_name="Estimated End Time",
        help_text="Estimated maintenance completion time",
        null=True,
        blank=True
    )
    
    actual_end_time = models.DateTimeField(
        verbose_name="Actual End Time",
        help_text="When maintenance actually ended",
    )
    
    # Maintenance scope and settings
    maintenance_type = models.CharField(
        max_length=50,
        verbose_name="Maintenance Type",
        help_text="Type of maintenance",
        choices=[
            ('full', 'Full Site Maintenance'),
            ('partial', 'Partial Maintenance'),
            ('emergency', 'Emergency Maintenance'),
            ('scheduled', 'Scheduled Maintenance'),
            ('database', 'Database Maintenance'),
            ('security', 'Security Update'),
        ],
        default='scheduled'
    )
    
    affected_services = models.JSONField(
        verbose_name="Affected Services",
        help_text="Services affected by maintenance (JSON array)",
        default=list,
        blank=True,
        null=True
    )
    
    # Access control
    allowed_ips = models.JSONField(
        verbose_name="Allowed IPs",
        help_text="IP addresses allowed during maintenance (JSON array)",
        default=list,
        blank=True,
        null=True
    )
    
    allowed_users = models.JSONField(
        verbose_name="Allowed Users",
        help_text="User IDs allowed during maintenance (JSON array)",
        default=list,
    )
    
    bypass_token = models.CharField(
        max_length=100,
        verbose_name="Bypass Token",
        help_text="Token to bypass maintenance mode",
        blank=True,
        null=True,
        unique=True)
    
    # Status tracking
    progress_percentage = models.IntegerField(
        verbose_name="Progress Percentage",
        help_text="Maintenance progress (0-100)",
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    status = models.CharField(
        max_length=50,
        verbose_name="Status",
        help_text="Current maintenance status",
        choices=[
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
            ('paused', 'Paused'),
        ],
        default='pending',
        db_index=True
    )
    
    # Metadata
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        verbose_name="Initiated By",
        help_text="User who initiated maintenance",
        null=True,
        blank=True)
    
    notes = models.TextField(
        verbose_name="Notes",
        help_text="Additional notes/comments",
    )
    
    created_at = models.DateTimeField(
        verbose_name="Created At",
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        verbose_name="Updated At",
        auto_now=True
    )
    
    # Model-Level Constraints
    class Meta:
        db_table = 'security_maintenancemode'
        verbose_name = 'Maintenance Mode'
        verbose_name_plural = 'Maintenance Modes'
        
        indexes = [
            models.Index(fields=['is_active', 'status']),
            models.Index(fields=['start_time', 'estimated_end_time']),
            models.Index(fields=['maintenance_type']),
        ]
        
        ordering = ['-start_time']
    
    # Type Hinting: All methods have proper type hints
    def clean(self) -> None:
        """Validate model data before saving"""
        errors = {}
        
        try:
            # Type validation
            if self.start_time and self.estimated_end_time:
                if self.estimated_end_time <= self.start_time:
                    errors['estimated_end_time'] = "End time must be after start time"
            
            # Progress validation
            if not 0 <= self.progress_percentage <= 100:
                errors['progress_percentage'] = "Progress must be between 0 and 100"
            
            # Validate JSON fields
            if self.affected_services and not isinstance(self.affected_services, list):
                errors['affected_services'] = "Affected services must be a list"
            
            if self.allowed_ips and not isinstance(self.allowed_ips, list):
                errors['allowed_ips'] = "Allowed IPs must be a list"
            
            if self.allowed_users and not isinstance(self.allowed_users, list):
                errors['allowed_users'] = "Allowed users must be a list"
            
            # Status consistency
            if self.status == 'completed' and self.is_active:
                errors['status'] = "Cannot be active when status is completed"
            
            if self.status in ['completed', 'cancelled'] and not self.actual_end_time:
                errors['actual_end_time'] = f"Actual end time required for {self.status} status"
            
        except Exception as e:
            # Graceful Degradation: Log error but don't crash
            logger.error(f"MaintenanceMode validation error: {e}")
            errors['non_field_errors'] = "An unexpected validation error occurred"
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save with defensive programming"""
        try:
            # Auto-clean before saving
            self.full_clean()
            
            # Set defaults if not provided
            if not self.affected_services:
                self.affected_services = []
            
            if not self.allowed_ips:
                self.allowed_ips = []
            
            if not self.allowed_users:
                self.allowed_users = []
            
            # Generate bypass token if not provided and maintenance is active
            if self.is_active and not self.bypass_token:
                import secrets
                self.bypass_token = secrets.token_urlsafe(32)
            
            # Update cache when maintenance mode changes
            cache_key = 'maintenance_mode_status'
            
            super().save(*args, **kwargs)
            
            # Update cache with defensive error handling
            try:
                cache.set(cache_key, {
                    'is_active': self.is_active,
                    'title': self.title,
                    'message': self.message,
                    'estimated_end_time': self.estimated_end_time.isoformat() if self.estimated_end_time else None,
                }, timeout=300)  # Cache for 5 minutes
            except Exception as e:
                logger.warning(f"Failed to update maintenance mode cache: {e}")
            
        except Exception as e:
            logger.error(f"Failed to save MaintenanceMode: {e}")
            raise
    
    # Business logic methods with defensive coding
    def is_currently_active(self) -> bool:
        """Check if maintenance is currently active with defensive checks"""
        try:
            if not self.is_active:
                return False
            
            # Check if past estimated end time
            if self.estimated_end_time and timezone.now() > self.estimated_end_time:
                # Auto-deactivate if past estimated time
                if self.status != 'completed':
                    self.status = 'completed'
                    self.is_active = False
                    self.actual_end_time = timezone.now()
                    self.save()
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking maintenance status: {e}")
            return False  # Graceful degradation: Assume not active on error
    
    def can_bypass(self, user=None, ip_address: str = None, token: str = None) -> Tuple[bool, str]:
        """Check if user can bypass maintenance with detailed response"""
        try:
            # If maintenance is not active, everyone can "bypass"
            if not self.is_currently_active():
                return True, "Maintenance mode is not active"
            
            # Check bypass token
            if token and self.bypass_token and token == self.bypass_token:
                return True, "Valid bypass token"
            
            # Check allowed IPs
            if ip_address and ip_address in self.allowed_ips:
                return True, "IP address is allowed"
            
            # Check allowed users
            if user and user.id in self.allowed_users:
                return True, "User is allowed"
            
            # Check if user is staff/admin
            if user and (user.is_staff or user.is_superuser):
                return True, "Staff/Admin user"
            
            # Default: cannot bypass
            return False, "Access denied during maintenance"
            
        except Exception as e:
            logger.error(f"Error checking bypass permission: {e}")
            return False, f"Error checking permissions: {str(e)}"
    
    def start_maintenance(self, user=None) -> Tuple[bool, str]:
        """Start maintenance mode with error handling"""
        try:
            if self.is_active:
                return False, "Maintenance is already active"
            
            self.is_active = True
            self.status = 'in_progress'
            self.start_time = timezone.now()
            self.progress_percentage = 0
            self.initiated_by = user
            
            # Generate new bypass token
            import secrets
            self.bypass_token = secrets.token_urlsafe(32)
            
            self.save()
            
            # Clear relevant caches
            self._clear_related_caches()
            
            logger.info(f"Maintenance started by user {user.id if user else 'system'}")
            return True, "Maintenance mode started successfully"
            
        except Exception as e:
            logger.error(f"Failed to start maintenance: {e}")
            return False, f"Failed to start maintenance: {str(e)}"
    
    def end_maintenance(self, user=None) -> Tuple[bool, str]:
        """End maintenance mode with error handling"""
        try:
            if not self.is_active:
                return False, "Maintenance is not active"
            
            self.is_active = False
            self.status = 'completed'
            self.actual_end_time = timezone.now()
            self.progress_percentage = 100
            
            if user:
                self.notes = f"{self.notes}\n\nEnded by: {user.username} at {timezone.now()}"
            
            self.save()
            
            # Clear relevant caches
            self._clear_related_caches()
            
            logger.info(f"Maintenance ended by user {user.id if user else 'system'}")
            return True, "Maintenance mode ended successfully"
            
        except Exception as e:
            logger.error(f"Failed to end maintenance: {e}")
            return False, f"Failed to end maintenance: {str(e)}"
    
    def pause_maintenance(self, user=None) -> Tuple[bool, str]:
        """Pause maintenance mode"""
        try:
            if not self.is_active:
                return False, "Maintenance is not active"
            
            if self.status != 'in_progress':
                return False, f"Cannot pause maintenance with status: {self.status}"
            
            self.status = 'paused'
            self.save()
            
            logger.info(f"Maintenance paused by user {user.id if user else 'system'}")
            return True, "Maintenance paused"
            
        except Exception as e:
            logger.error(f"Failed to pause maintenance: {e}")
            return False, f"Failed to pause maintenance: {str(e)}"
    
    def resume_maintenance(self, user=None) -> Tuple[bool, str]:
        """Resume paused maintenance"""
        try:
            if not self.is_active:
                return False, "Maintenance is not active"
            
            if self.status != 'paused':
                return False, f"Cannot resume maintenance with status: {self.status}"
            
            self.status = 'in_progress'
            self.save()
            
            logger.info(f"Maintenance resumed by user {user.id if user else 'system'}")
            return True, "Maintenance resumed"
            
        except Exception as e:
            logger.error(f"Failed to resume maintenance: {e}")
            return False, f"Failed to resume maintenance: {str(e)}"
    
    def update_progress(self, percentage: int, notes: str = None) -> Tuple[bool, str]:
        """Update maintenance progress with validation"""
        try:
            # Validate percentage
            if not 0 <= percentage <= 100:
                return False, "Progress percentage must be between 0 and 100"
            
            self.progress_percentage = percentage
            
            if notes:
                current_notes = self.notes or ""
                self.notes = f"{current_notes}\n\nProgress update ({timezone.now()}): {notes}"
            
            self.save()
            
            return True, "Progress updated successfully"
            
        except Exception as e:
            logger.error(f"Failed to update progress: {e}")
            return False, f"Failed to update progress: {str(e)}"
    
    def get_maintenance_info(self) -> Dict[str, Any]:
        """Get maintenance information with defensive coding"""
        try:
            is_active = self.is_currently_active()
            
            info = {
                'id': self.id,
                'is_active': is_active,
                'title': self.title,
                'message': self.message,
                'maintenance_type': self.maintenance_type,
                'status': self.status,
                'progress_percentage': self.progress_percentage,
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'estimated_end_time': self.estimated_end_time.isoformat() if self.estimated_end_time else None,
                'actual_end_time': self.actual_end_time.isoformat() if self.actual_end_time else None,
                'affected_services': self.affected_services or [],
                'initiated_by': self.initiated_by.username if self.initiated_by else None,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            }
            
            # Calculate estimated time remaining
            if is_active and self.estimated_end_time:
                now = timezone.now()
                if self.estimated_end_time > now:
                    remaining = self.estimated_end_time - now
                    info['estimated_time_remaining'] = {
                        'total_seconds': int(remaining.total_seconds()),
                        'hours': remaining.days * 24 + remaining.seconds // 3600,
                        'minutes': (remaining.seconds % 3600) // 60,
                        'seconds': remaining.seconds % 60,
                    }
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting maintenance info for ID {self.id}: {e}")
            return {
                'id': self.id,
                'is_active': False,
                'error': 'Could not retrieve maintenance information',
                'title': 'Error',
                'message': 'Unable to retrieve maintenance details'
            }
    
    @classmethod
    def get_active_maintenance(cls) -> Optional['MaintenanceMode']:
        """Get currently active maintenance with defensive coding"""
        try:
            # Try cache first
            cache_key = 'active_maintenance'
            cached = cache.get(cache_key)
            
            if cached is not None:
                if cached == 'none':
                    return None
                try:
                    return cls.objects.get(id=cached)
                except cls.DoesNotExist:
                    pass
            
            # Query database
            active_maintenance = cls.objects.filter(
                is_active=True
            ).order_by('-start_time').first()
            
            # Update cache
            try:
                if active_maintenance:
                    cache.set(cache_key, active_maintenance.id, timeout=60)
                else:
                    cache.set(cache_key, 'none', timeout=60)
            except Exception as e:
                logger.warning(f"Failed to update maintenance cache: {e}")
            
            return active_maintenance
            
        except Exception as e:
            logger.error(f"Error getting active maintenance: {e}")
            return None
    
    @classmethod
    def check_maintenance_status(cls, user=None, ip_address: str = None, token: str = None) -> Tuple[bool, Dict[str, Any]]:
        """Check maintenance status and bypass permissions"""
        try:
            maintenance = cls.get_active_maintenance()
            
            if not maintenance:
                return False, {'is_active': False}
            
            # Check if user can bypass
            can_bypass, reason = maintenance.can_bypass(user, ip_address, token)
            
            if can_bypass:
                return False, {
                    'is_active': True,
                    'can_bypass': True,
                    'reason': reason,
                    'maintenance_id': maintenance.id
                }
            
            # Return maintenance info for blocked users
            info = maintenance.get_maintenance_info()
            info.update({
                'can_bypass': False,
                'reason': reason,
                'bypass_token_required': bool(token is None and maintenance.bypass_token)
            })
            
            return True, info
            
        except Exception as e:
            logger.error(f"Error checking maintenance status: {e}")
            # Graceful degradation: Assume no maintenance on error
            return False, {'is_active': False, 'error': 'Unable to check maintenance status'}
    
    def _clear_related_caches(self) -> None:
        """Clear related caches with error handling"""
        try:
            cache_keys = [
                'maintenance_mode_status',
                'active_maintenance',
                f'maintenance_{self.id}_info'
            ]
            
            for key in cache_keys:
                try:
                    cache.delete(key)
                except Exception as e:
                    logger.warning(f"Failed to delete cache key {key}: {e}")
                    
        except Exception as e:
            logger.error(f"Error clearing maintenance caches: {e}")
    
    def __str__(self) -> str:
        """String representation with null safety"""
        status_display = "Active" if self.is_active else "Inactive"
        return f"{self.title} ({status_display})"
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Calculate maintenance duration with defensive coding"""
        try:
            if not self.start_time:
                return None
            
            end_time = self.actual_end_time or timezone.now()
            return end_time - self.start_time
            
        except Exception:
            return None
        
        
class SecurityConfig(models.Model):
    """
    SecurityConfig model with comprehensive defensive coding
    Centralized security configuration management
    """
    
    # Null Object Pattern: Default values for all fields
    name = models.CharField(
        null=True, blank=True,
        max_length=100,
        verbose_name="Configuration Name",
        help_text="Unique name for this security configuration",
        unique=True,
        db_index=True)
    
    description = models.TextField(
        null=True, blank=True,
        verbose_name="Description",
        help_text="Description of this security configuration",
    )
    
    config_type = models.CharField(
        max_length=50,
        verbose_name="Configuration Type",
        help_text="Type of security configuration",
        choices=[
            ('rate_limit', 'Rate Limiting'),
            ('password_policy', 'Password Policy'),
            ('login_security', 'Login Security'),
            ('api_security', 'API Security'),
            ('content_security', 'Content Security'),
            ('general', 'General Security'),
        ],
        default='general'
    )
    
    # Configuration values stored as JSON for flexibility
    config_data = models.JSONField(
        verbose_name="Configuration Data",
        help_text="Security configuration in JSON format",
        default=dict,
        blank=True
    )
    
    # Activation and scheduling
    is_active = models.BooleanField(
        verbose_name="Is Active",
        help_text="Whether this configuration is active",
        default=True,
        db_index=True
    )
    
    is_default = models.BooleanField(
        verbose_name="Is Default",
        help_text="Whether this is the default configuration",
        default=False
    )
    
    effective_from = models.DateTimeField(
        verbose_name="Effective From",
        help_text="When this configuration becomes effective",
        default=timezone.now
    )
    
    effective_until = models.DateTimeField(
        verbose_name="Effective Until",
        help_text="When this configuration expires",
        null=True,
        blank=True
    )
    
    # Versioning and auditing
    version = models.PositiveIntegerField(
        verbose_name="Version",
        help_text="Configuration version number",
        default=1
    )
    
    parent_config = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        verbose_name="Parent Configuration",
        help_text="Parent configuration this was based on",
        null=True,
        blank=True,
        related_name='child_configs')
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        verbose_name="Created By",
        help_text="User who created this configuration",
        null=True,
        blank=True,
        related_name='created_security_configs')
    
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        verbose_name="Updated By",
        help_text="User who last updated this configuration",
        null=True,
        blank=True,
        related_name='updated_security_configs')
    
    created_at = models.DateTimeField(
        verbose_name="Created At",
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        verbose_name="Updated At",
        auto_now=True
    )
    
    # Model-Level Constraints
    class Meta:
        db_table = 'security_securityconfig'
        verbose_name = 'Security Configuration'
        verbose_name_plural = 'Security Configurations'
        
        indexes = [
            models.Index(fields=['name', 'is_active']),
            models.Index(fields=['config_type', 'is_active']),
            models.Index(fields=['effective_from', 'effective_until']),
            models.Index(fields=['is_default']),
        ]
        
        ordering = ['-effective_from', 'name']
        
        # Ensure only one default config per type
        constraints = [
            models.UniqueConstraint(
                fields=['config_type', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_per_type'
            )
        ]
    
    # Type Hinting: All methods have proper type hints
    def clean(self) -> None:
        """Validate model data before saving"""
        errors = {}
        
        try:
            # Name validation
            if not self.name or len(self.name.strip()) == 0:
                errors['name'] = "Name is required"
            
            # Type validation
            valid_types = [choice[0] for choice in self._meta.get_field('config_type').choices]
            if self.config_type not in valid_types:
                errors['config_type'] = f"Invalid configuration type. Must be one of: {', '.join(valid_types)}"
            
            # Date validation
            if self.effective_from and self.effective_until:
                if self.effective_until <= self.effective_from:
                    errors['effective_until'] = "Effective until must be after effective from"
            
            # Config data validation
            if not isinstance(self.config_data, dict):
                errors['config_data'] = "Configuration data must be a valid JSON object"
            
            # Validate based on config type
            self._validate_config_data(errors)
            
        except Exception as e:
            # Graceful Degradation: Log error but don't crash
            logger.error(f"SecurityConfig validation error for {self.name}: {e}")
            errors['non_field_errors'] = "An unexpected validation error occurred"
        
        if errors:
            raise ValidationError(errors)
    
    def _validate_config_data(self, errors: Dict[str, str]) -> None:
        """Validate configuration data based on type"""
        try:
            config_type_validators = {
                'rate_limit': self._validate_rate_limit_config,
                'password_policy': self._validate_password_policy_config,
                'login_security': self._validate_login_security_config,
                'api_security': self._validate_api_security_config,
                'content_security': self._validate_content_security_config,
                'general': self._validate_general_config,
            }
            
            validator = config_type_validators.get(self.config_type)
            if validator:
                validator(errors)
                
        except Exception as e:
            logger.error(f"Error in config data validation: {e}")
            errors['config_data'] = f"Configuration validation error: {str(e)}"
    
    def _validate_rate_limit_config(self, errors: Dict[str, str]) -> None:
        """Validate rate limiting configuration"""
        config = self.config_data
        
        required_fields = ['max_requests', 'time_window']
        for field in required_fields:
            if field not in config:
                errors['config_data'] = f"Rate limit config missing '{field}' field"
                return
        
        if not isinstance(config['max_requests'], int) or config['max_requests'] <= 0:
            errors['config_data'] = "max_requests must be a positive integer"
        
        if not isinstance(config['time_window'], int) or config['time_window'] <= 0:
            errors['config_data'] = "time_window must be a positive integer (seconds)"
    
    def _validate_password_policy_config(self, errors: Dict[str, str]) -> None:
        """Validate password policy configuration"""
        config = self.config_data
        
        # Validate min_length
        if 'min_length' in config and (not isinstance(config['min_length'], int) or config['min_length'] < 6):
            errors['config_data'] = "min_length must be an integer >= 6"
        
        # Validate require_* flags
        boolean_fields = ['require_uppercase', 'require_lowercase', 'require_numbers', 'require_symbols']
        for field in boolean_fields:
            if field in config and not isinstance(config[field], bool):
                errors['config_data'] = f"{field} must be a boolean"
    
    def _validate_login_security_config(self, errors: Dict[str, str]) -> None:
        """Validate login security configuration"""
        config = self.config_data
        
        # Validate max_attempts
        if 'max_attempts' in config and (not isinstance(config['max_attempts'], int) or config['max_attempts'] <= 0):
            errors['config_data'] = "max_attempts must be a positive integer"
        
        # Validate lockout_duration
        if 'lockout_duration' in config and (not isinstance(config['lockout_duration'], int) or config['lockout_duration'] < 0):
            errors['config_data'] = "lockout_duration must be a non-negative integer"
    
    def _validate_api_security_config(self, errors: Dict[str, str]) -> None:
        """Validate API security configuration"""
        config = self.config_data
        
        # Validate require_https
        if 'require_https' in config and not isinstance(config['require_https'], bool):
            errors['config_data'] = "require_https must be a boolean"
        
        # Validate allowed_origins
        if 'allowed_origins' in config and not isinstance(config['allowed_origins'], list):
            errors['config_data'] = "allowed_origins must be a list"
    
    def _validate_content_security_config(self, errors: Dict[str, str]) -> None:
        """Validate content security configuration"""
        config = self.config_data
        
        # Validate allowed_file_types
        if 'allowed_file_types' in config and not isinstance(config['allowed_file_types'], list):
            errors['config_data'] = "allowed_file_types must be a list"
        
        # Validate max_file_size
        if 'max_file_size' in config and (not isinstance(config['max_file_size'], int) or config['max_file_size'] <= 0):
            errors['config_data'] = "max_file_size must be a positive integer"
    
    def _validate_general_config(self, errors: Dict[str, str]) -> None:
        """Validate general security configuration"""
        # General config is more flexible
        pass
    
    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save with defensive programming"""
        try:
            # Auto-clean before saving
            self.full_clean()
            
            # Set defaults for config_data if empty
            if not self.config_data:
                self.config_data = self.get_default_config()
            
            # Ensure only one default per type
            if self.is_default:
                # Remove default flag from other configs of same type
                SecurityConfig.objects.filter(
                    config_type=self.config_type,
                    is_default=True
                ).exclude(pk=self.pk if self.pk else None).update(is_default=False)
            
            # Update version if this is an update
            if self.pk:
                original = SecurityConfig.objects.get(pk=self.pk)
                if original.config_data != self.config_data:
                    self.version += 1
            
            super().save(*args, **kwargs)
            
            # Clear configuration cache
            self._clear_config_cache()
            
        except Exception as e:
            logger.error(f"Failed to save SecurityConfig {self.name}: {e}")
            raise
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration based on type"""
        default_configs = {
            'rate_limit': {
                'max_requests': 100,
                'time_window': 60,  # seconds
                'burst_limit': 10,
                'scope': 'ip',
                'enabled': True
            },
            'password_policy': {
                'min_length': 8,
                'require_uppercase': True,
                'require_lowercase': True,
                'require_numbers': True,
                'require_symbols': True,
                'max_age_days': 90,
                'prevent_reuse': 5
            },
            'login_security': {
                'max_attempts': 5,
                'lockout_duration': 900,  # 15 minutes
                'require_2fa': False,
                'session_timeout': 3600,  # 1 hour
                'prevent_concurrent_logins': True
            },
            'api_security': {
                'require_https': True,
                'allowed_origins': [],
                'cors_enabled': False,
                'rate_limit_enabled': True,
                'api_key_required': True
            },
            'content_security': {
                'allowed_file_types': ['.jpg', '.jpeg', '.png', '.pdf', '.doc', '.docx'],
                'max_file_size': 5242880,  # 5MB
                'scan_for_malware': True,
                'sanitize_html': True,
                'prevent_xss': True
            },
            'general': {
                'enable_audit_logging': True,
                'log_retention_days': 90,
                'enable_security_headers': True,
                'enable_csrf_protection': True,
                'enable_clickjacking_protection': True
            }
        }
        
        return default_configs.get(self.config_type, {})
    
    # Business logic methods with defensive coding
    def is_currently_effective(self) -> bool:
        """Check if configuration is currently effective"""
        try:
            if not self.is_active:
                return False
            
            now = timezone.now()
            
            # Check effective_from
            if self.effective_from and now < self.effective_from:
                return False
            
            # Check effective_until
            if self.effective_until and now > self.effective_until:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking config effectiveness for {self.name}: {e}")
            return False  # Graceful degradation: Assume not effective on error
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Safely get configuration value with defensive coding"""
        try:
            if not isinstance(self.config_data, dict):
                return default
            
            return self.config_data.get(key, default)
            
        except Exception as e:
            logger.error(f"Error getting config value {key} from {self.name}: {e}")
            return default
    
    def update_config_value(self, key: str, value: Any, updated_by=None) -> Tuple[bool, str]:
        """Update configuration value with validation"""
        try:
            if not isinstance(self.config_data, dict):
                self.config_data = {}
            
            # Validate based on key if needed
            if not self._validate_config_key_value(key, value):
                return False, f"Invalid value for key '{key}'"
            
            # Update value
            old_value = self.config_data.get(key)
            self.config_data[key] = value
            
            # Update metadata
            self.updated_by = updated_by
            self.version += 1
            
            self.save()
            
            logger.info(f"Updated config {self.name}.{key}: {old_value} -> {value}")
            return True, "Configuration updated successfully"
            
        except Exception as e:
            logger.error(f"Failed to update config value {key}: {e}")
            return False, f"Failed to update configuration: {str(e)}"
    
    def _validate_config_key_value(self, key: str, value: Any) -> bool:
        """Validate key-value pair for configuration"""
        try:
            # Add validation logic based on config type and key
            validation_rules = {
                'rate_limit': {
                    'max_requests': lambda v: isinstance(v, int) and v > 0,
                    'time_window': lambda v: isinstance(v, int) and v > 0,
                    'burst_limit': lambda v: isinstance(v, int) and v > 0,
                },
                'password_policy': {
                    'min_length': lambda v: isinstance(v, int) and v >= 6,
                    'require_uppercase': lambda v: isinstance(v, bool),
                    'require_lowercase': lambda v: isinstance(v, bool),
                },
                # Add more validation rules as needed
            }
            
            type_rules = validation_rules.get(self.config_type, {})
            if key in type_rules:
                return type_rules[key](value)
            
            return True  # Default: accept any value
            
        except Exception:
            return False
    
    def clone_config(self, new_name: str, created_by=None) -> Optional['SecurityConfig']:
        """Create a clone of this configuration"""
        try:
            # Ensure unique name
            if SecurityConfig.objects.filter(name=new_name).exists():
                raise ValidationError(f"Configuration with name '{new_name}' already exists")
            
            cloned_config = SecurityConfig(
                name=new_name,
                description=f"Cloned from {self.name}",
                config_type=self.config_type,
                config_data=self.config_data.copy() if self.config_data else {},
                is_active=False,  # Clones are inactive by default
                is_default=False,
                effective_from=timezone.now(),
                parent_config=self,
                created_by=created_by,
                version=1
            )
            
            cloned_config.save()
            
            logger.info(f"Cloned config {self.name} to {new_name}")
            return cloned_config
            
        except Exception as e:
            logger.error(f"Failed to clone config {self.name}: {e}")
            return None
    
    @classmethod
    def get_active_config(cls, config_type: str, name: str = None) -> Optional['SecurityConfig']:
        """Get active configuration by type and optional name"""
        try:
            cache_key = f'security_config:{config_type}:{name or "default"}'
            
            # Try cache first
            cached_id = cache.get(cache_key)
            if cached_id:
                try:
                    return cls.objects.get(id=cached_id, is_active=True)
                except cls.DoesNotExist:
                    pass
            
            # Build query
            query = cls.objects.filter(
                config_type=config_type,
                is_active=True
            )
            
            if name:
                query = query.filter(name=name)
            else:
                # Get default config for type
                query = query.filter(is_default=True)
            
            # Get currently effective config
            now = timezone.now()
            config = query.filter(
                models.Q(effective_until__isnull=True) | models.Q(effective_until__gt=now),
                effective_from__lte=now
            ).order_by('-is_default', '-effective_from').first()
            
            # Update cache
            if config:
                try:
                    cache.set(cache_key, config.id, timeout=300)  # Cache for 5 minutes
                except Exception as e:
                    logger.warning(f"Failed to cache security config: {e}")
            
            return config
            
        except Exception as e:
            logger.error(f"Error getting active config for type {config_type}: {e}")
            return None
    
    @classmethod
    def get_config_value_by_type(cls, config_type: str, key: str, default: Any = None) -> Any:
        """Get configuration value by type with defensive coding"""
        try:
            config = cls.get_active_config(config_type)
            if config:
                return config.get_config_value(key, default)
            return default
            
        except Exception as e:
            logger.error(f"Error getting config value for type {config_type}.{key}: {e}")
            return default
    
    def _clear_config_cache(self) -> None:
        """Clear configuration cache with error handling"""
        try:
            cache_keys = [
                f'security_config:{self.config_type}:{self.name}',
                f'security_config:{self.config_type}:default',
                'all_security_configs'
            ]
            
            for key in cache_keys:
                try:
                    cache.delete(key)
                except Exception as e:
                    logger.warning(f"Failed to delete cache key {key}: {e}")
                    
        except Exception as e:
            logger.error(f"Error clearing config cache for {self.name}: {e}")
    
    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Get audit log for this configuration"""
        try:
            from django.contrib.admin.models import LogEntry
            from django.contrib.contenttypes.models import ContentType
            
            content_type = ContentType.objects.get_for_model(self)
            
            log_entries = LogEntry.objects.filter(
                content_type=content_type,
                object_id=self.id
            ).order_by('-action_time')[:100]  # Limit to 100 entries
            
            return [
                {
                    'action_time': entry.action_time,
                    'user': entry.user.username if entry.user else 'System',
                    'action_flag': entry.get_action_flag_display(),
                    'change_message': entry.change_message,
                }
                for entry in log_entries
            ]
            
        except Exception as e:
            logger.error(f"Error getting audit log for config {self.name}: {e}")
            return []
    
    def __str__(self) -> str:
        """String representation with null safety"""
        status = "Active" if self.is_active else "Inactive"
        default = " (Default)" if self.is_default else ""
        return f"{self.name} - {self.config_type}{default} [{status}]"
    
    
    
    # models.py - AppVersion মডেল যোগ করুন
class AppVersion(models.Model):
    """
    AppVersion model for version management with defensive coding
    অ্যাপ্লিকেশন ভার্সন ম্যানেজমেন্টের জন্য
    """
    
    # Null Object Pattern: Default values
    version_name = models.CharField(
        max_length=50,
        verbose_name="Version Name",
        help_text="Version name (e.g., 1.0.0, null=True, blank=True)",
        default="1.0.0",
        unique=True
    )
    
    version_code = models.CharField(
        max_length=20,
        verbose_name="Version Code",
        help_text="Version code for comparison",
        default="1",
        unique=True,
        db_index=True)
    
    release_type = models.CharField(
        max_length=20,
        verbose_name="Release Type",
        help_text="Type of release",
        choices=[
            ('stable', 'Stable Release'),
            ('beta', 'Beta Release'),
            ('alpha', 'Alpha Release'),
            ('development', 'Development Build'),
            ('emergency', 'Emergency Fix'),
        ],
        default='stable'
    )
    
    release_notes = models.TextField(
        verbose_name="Release Notes",
        help_text="Release notes and changelog",
        default="",
        blank=True
    )
    
    is_mandatory = models.BooleanField(
        verbose_name="Is Mandatory",
        help_text="Whether this update is mandatory",
        default=False
    )
    
    min_os_version = models.CharField(
        max_length=20,
        verbose_name="Minimum OS Version",
        help_text="Minimum operating system version required",
        default="",
        blank=True)
    
    max_os_version = models.CharField(
        max_length=20,
        verbose_name="Maximum OS Version",
        help_text="Maximum operating system version supported",
        default="",)
    
    download_url = models.URLField(
        verbose_name="Download URL",
        help_text="URL to download the update",
        default="",
        blank=True)
    
    checksum = models.CharField(
        max_length=128,
        verbose_name="Checksum",
        help_text="SHA256 checksum for verification",
        default="",)
    
    file_size = models.BigIntegerField(
        verbose_name="File Size",
        help_text="Size of the update file in bytes",
        default=0
    )
    
    # Release management
    release_date = models.DateTimeField(
        verbose_name="Release Date",
        help_text="When the version was released",
        default=timezone.now
    )
    
    effective_from = models.DateTimeField(
        verbose_name="Effective From",
        help_text="When this version becomes effective",
        default=timezone.now
    )
    
    deprecated_at = models.DateTimeField(
        verbose_name="Deprecated At",
        help_text="When this version was deprecated",
        null=True,
        blank=True
    )
    
    is_active = models.BooleanField(
        verbose_name="Is Active",
        help_text="Whether this version is active",
        default=True,
        db_index=True
    )
    
    # Platform support
    supported_platforms = models.JSONField(
        verbose_name="Supported Platforms",
        help_text="Platforms supported by this version",
        default=list,
        blank=True,
        null=True
    )
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        verbose_name="Created By",
        help_text="User who created this version",
        null=True,
        blank=True)
    
    notes = models.TextField(
        verbose_name="Notes",
        help_text="Additional notes/comments",
    )
    
    created_at = models.DateTimeField(
        verbose_name="Created At",
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        verbose_name="Updated At",
        auto_now=True
    )
    
    # Model-Level Constraints
    class Meta:
        db_table = 'security_appversion'
        verbose_name = 'App Version'
        verbose_name_plural = 'App Versions'
        
        indexes = [
            models.Index(fields=['version_code', 'is_active']),
            models.Index(fields=['release_type', 'release_date']),
            models.Index(fields=['is_mandatory']),
        ]
        
        ordering = ['-version_code', '-release_date']
    
    # Type Hinting: All methods have proper type hints
    def clean(self) -> None:
        """Validate model data before saving"""
        errors = {}
        
        try:
            # Version validation
            if not self.version_name or len(self.version_name.strip()) == 0:
                errors['version_name'] = "Version name is required"
            
            if not self.version_code or len(self.version_code.strip()) == 0:
                errors['version_code'] = "Version code is required"
            
            # Date validation
            if self.effective_from and self.deprecated_at:
                if self.deprecated_at <= self.effective_from:
                    errors['deprecated_at'] = "Deprecated date must be after effective date"
            
            # File size validation
            if self.file_size < 0:
                errors['file_size'] = "File size cannot be negative"
            
            # Platform validation
            if self.supported_platforms and not isinstance(self.supported_platforms, list):
                errors['supported_platforms'] = "Supported platforms must be a list"
            
        except Exception as e:
            logger.error(f"AppVersion validation error for {self.version_name}: {e}")
            errors['non_field_errors'] = "An unexpected validation error occurred"
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save with defensive programming"""
        try:
            # Auto-clean before saving
            self.full_clean()
            
            # Set defaults if not provided
            if not self.supported_platforms:
                self.supported_platforms = ['web', 'android', 'ios']
            
            # Auto-generate version code if not provided
            if not self.version_code and self.version_name:
                # Convert version name to code (e.g., "1.2.3" -> "10203")
                try:
                    parts = self.version_name.split('.')
                    code = int(''.join([part.zfill(2) for part in parts]))
                    self.version_code = str(code)
                except:
                    # Fallback to timestamp
                    self.version_code = str(int(timezone.now().timestamp()))
            
            super().save(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"Failed to save AppVersion {self.version_name}: {e}")
            raise
    
    # Business logic methods with defensive coding
    def is_currently_active(self) -> bool:
        """Check if version is currently active"""
        try:
            if not self.is_active:
                return False
            
            now = timezone.now()
            
            # Check effective_from
            if self.effective_from and now < self.effective_from:
                return False
            
            # Check deprecated_at
            if self.deprecated_at and now > self.deprecated_at:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking version status for {self.version_name}: {e}")
            return False
    
    def get_latest_version_info(self, platform: str = 'web') -> Dict[str, Any]:
        """Get latest version information for a platform"""
        try:
            # Check if platform is supported
            if platform not in (self.supported_platforms or []):
                return {
                    'error': f"Platform {platform} not supported",
                    'version_name': self.version_name,
                    'supported_platforms': self.supported_platforms or []
                }
            
            info = {
                'version_name': self.version_name,
                'version_code': self.version_code,
                'release_type': self.release_type,
                'release_notes': self.release_notes,
                'is_mandatory': self.is_mandatory,
                'download_url': self.download_url,
                'file_size': self.file_size,
                'checksum': self.checksum,
                'release_date': self.release_date.isoformat() if self.release_date else None,
                'min_os_version': self.min_os_version,
                'max_os_version': self.max_os_version,
                'is_update_available': False,  # Will be set by caller
                'update_type': 'none',  # none, optional, mandatory
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting version info for {self.version_name}: {e}")
            return {
                'error': 'Could not retrieve version information',
                'version_name': self.version_name
            }
    
    def mark_as_deprecated(self, reason: str = "New version available") -> Tuple[bool, str]:
        """Mark version as deprecated"""
        try:
            self.is_active = False
            self.deprecated_at = timezone.now()
            self.notes = f"{self.notes}\n\nDeprecated: {reason} ({timezone.now()})"
            
            self.save()
            
            logger.info(f"Version {self.version_name} marked as deprecated: {reason}")
            return True, "Version deprecated successfully"
            
        except Exception as e:
            logger.error(f"Failed to deprecate version {self.version_name}: {e}")
            return False, f"Failed to deprecate version: {str(e)}"
    
    @classmethod
    def get_latest_version(cls, platform: str = 'web') -> Optional['AppVersion']:
        """Get latest version for a platform"""
        try:
            cache_key = f'app_version:latest:{platform}'
            
            # Try cache first
            cached_id = cache.get(cache_key)
            if cached_id:
                try:
                    return cls.objects.get(id=cached_id)
                except cls.DoesNotExist:
                    pass
            
            # Query database
            latest_version = cls.objects.filter(
                is_active=True,
                supported_platforms__contains=[platform]
            ).filter(
                models.Q(deprecated_at__isnull=True) | models.Q(deprecated_at__gt=timezone.now())
            ).order_by('-version_code', '-release_date').first()
            
            # Update cache
            if latest_version:
                try:
                    cache.set(cache_key, latest_version.id, timeout=300)  # 5 minutes
                except Exception as e:
                    logger.warning(f"Failed to cache latest version: {e}")
            
            return latest_version
            
        except Exception as e:
            logger.error(f"Error getting latest version for platform {platform}: {e}")
            return None
    
    @classmethod
    def check_for_updates(cls, current_version_code: str, platform: str = 'web') -> Dict[str, Any]:
        """Check for updates with defensive coding"""
        try:
            latest_version = cls.get_latest_version(platform)
            
            if not latest_version:
                return {
                    'is_update_available': False,
                    'message': 'No versions available',
                    'current_version': current_version_code
                }
            
            # Compare version codes
            try:
                current_code = int(current_version_code)
                latest_code = int(latest_version.version_code)
                
                if latest_code > current_code:
                    info = latest_version.get_latest_version_info(platform)
                    info['is_update_available'] = True
                    info['current_version'] = current_version_code
                    
                    # Determine update type
                    if latest_version.is_mandatory:
                        info['update_type'] = 'mandatory'
                    else:
                        info['update_type'] = 'optional'
                    
                    return info
                else:
                    return {
                        'is_update_available': False,
                        'message': 'You have the latest version',
                        'current_version': current_version_code,
                        'latest_version': latest_version.version_name
                    }
                    
            except ValueError:
                # If version codes aren't integers, do string comparison
                if latest_version.version_code != current_version_code:
                    info = latest_version.get_latest_version_info(platform)
                    info['is_update_available'] = True
                    info['current_version'] = current_version_code
                    info['update_type'] = 'optional'
                    return info
                else:
                    return {
                        'is_update_available': False,
                        'message': 'You have the latest version',
                        'current_version': current_version_code
                    }
            
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return {
                'is_update_available': False,
                'error': 'Could not check for updates',
                'current_version': current_version_code
            }
    
    def __str__(self) -> str:
        """String representation"""
        mandatory = " (Mandatory)" if self.is_mandatory else ""
        deprecated = " [Deprecated]" if self.deprecated_at else ""
        return f"{self.version_name}{mandatory}{deprecated}"
    
    
    
    # models.py - Add this after other models
class IPBlacklist(models.Model):
    """
    IPBlacklist model with comprehensive defensive coding
    IP address blacklisting with threat intelligence and rate limiting
    """
    
    # Null Object Pattern: Default values for all fields
    ip_address = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name="IP Address",
        help_text="IP address to blacklist",
        unique=True,
        db_index=True
    )
    
    subnet_mask = models.PositiveSmallIntegerField(
        verbose_name="Subnet Mask",
        help_text="Subnet mask for IP range blocking (e.g., 24 for /24)",
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(32)]
    )
    
    # Blocking details
    reason = models.TextField(
        verbose_name="Reason",
        help_text="Reason for blacklisting",
        default="Suspicious activity detected",
        blank=False
    )
    
    threat_level = models.CharField(
        max_length=20,
        verbose_name="Threat Level",
        help_text="Threat level assessment",
        choices=[
            ('low', 'Low Threat'),
            ('medium', 'Medium Threat'),
            ('high', 'High Threat'),
            ('critical', 'Critical Threat'),
            ('confirmed_attacker', 'Confirmed Attacker'),
        ],
        default='medium',
        db_index=True
    )
    
    threat_type = models.CharField(
        max_length=50,
        verbose_name="Threat Type",
        help_text="Type of threat detected",
        choices=[
            ('brute_force', 'Brute Force Attack'),
            ('ddos', 'DDoS Attack'),
            ('scanning', 'Port Scanning'),
            ('spam', 'Spam/Bot Activity'),
            ('malware', 'Malware Distribution'),
            ('phishing', 'Phishing Attempt'),
            ('credential_stuffing', 'Credential Stuffing'),
            ('api_abuse', 'API Abuse'),
            ('web_scraping', 'Web Scraping'),
            ('suspicious_pattern', 'Suspicious Pattern'),
            ('manual_block', 'Manual Block'),
            ('other', 'Other'),
        ],
        default='suspicious_pattern'
    )
    
    # Blocking configuration
    is_active = models.BooleanField(
        verbose_name="Is Active",
        help_text="Whether this blacklist entry is active",
        default=True,
        db_index=True
    )
    
    is_permanent = models.BooleanField(
        verbose_name="Is Permanent",
        help_text="Permanent blacklist (no automatic expiration)",
        default=False
    )
    
    blocked_until = models.DateTimeField(
        verbose_name="Blocked Until",
        help_text="Temporary block expiration time",
        null=True,
        blank=True
    )
    
    # Rate limiting within the block
    max_requests_per_minute = models.IntegerField(
        verbose_name="Max Requests/Minute",
        help_text="Maximum allowed requests per minute (0=complete block)",
        default=0,
        validators=[MinValueValidator(0)]
    )
    
    # Detection and analytics
    detection_method = models.CharField(
        max_length=50,
        verbose_name="Detection Method",
        help_text="How this IP was detected",
        choices=[
            ('automated', 'Automated Detection'),
            ('manual', 'Manual Entry'),
            ('threat_intel', 'Threat Intelligence Feed'),
            ('honeypot', 'Honeypot Detection'),
            ('ids_ips', 'IDS/IPS System'),
            ('waf', 'Web Application Firewall'),
            ('rate_limit', 'Rate Limit Violation'),
            ('geo_block', 'Geographic Blocking'),
            ('asn_block', 'ASN Blocking'),
        ],
        default='automated'
    )
    
    confidence_score = models.FloatField(
        verbose_name="Confidence Score",
        help_text="Confidence in the threat assessment (0-100)",
        default=80.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    attack_count = models.PositiveIntegerField(
        verbose_name="Attack Count",
        help_text="Number of attacks detected from this IP",
        default=1
    )
    
    last_attempt = models.DateTimeField(
        verbose_name="Last Attempt",
        help_text="Last attack attempt from this IP",
        auto_now=True
    )
    
    first_seen = models.DateTimeField(
        verbose_name="First Seen",
        help_text="When this IP was first detected",
        auto_now_add=True
    )
    
    # Geographic and network information
    country_code = models.CharField(
        max_length=2,
        verbose_name="Country Code",
        help_text="ISO country code",
        blank=True,
        null=True)
    
    country_name = models.CharField(
        max_length=100,
        verbose_name="Country Name",
        help_text="Country name",)
    
    city = models.CharField(
        max_length=100,
        verbose_name="City",
        help_text="City name",
        blank=True,
        null=True)
    
    isp = models.CharField(
        max_length=200,
        verbose_name="ISP",
        help_text="Internet Service Provider",)
    
    asn = models.CharField(
        max_length=50,
        verbose_name="ASN",
        help_text="Autonomous System Number",
        blank=True,
        null=True)
    
    organization = models.CharField(
        max_length=200,
        verbose_name="Organization",
        help_text="Organization name",)
    
    # Threat intelligence
    threat_intel_data = models.JSONField(
        verbose_name="Threat Intelligence Data",
        help_text="Additional threat intelligence data",
        default=dict,
        blank=True,
        null=True
    )
    
    # Metadata
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        verbose_name="Reported By",
        help_text="User who reported this IP",
        null=True,
        blank=True,
        related_name='reported_ips')
    
    auto_blocked_by = models.CharField(
        max_length=100,
        verbose_name="Auto-blocked By",
        help_text="System/rule that auto-blocked this IP",
        null=True)
    
    notes = models.TextField(
        verbose_name="Notes",
        help_text="Additional notes/comments",
        blank=True,
    )
    
    # Model-Level Constraints
    class Meta:
        db_table = 'security_ipblacklist'
        verbose_name = 'IP Blacklist'
        verbose_name_plural = 'IP Blacklist'
        
        indexes = [
            models.Index(fields=['ip_address', 'is_active']),
            models.Index(fields=['threat_level', 'is_active']),
            models.Index(fields=['threat_type', 'is_active']),
            models.Index(fields=['country_code', 'is_active']),
            models.Index(fields=['first_seen']),
            models.Index(fields=['last_attempt']),
            models.Index(fields=['is_permanent', 'blocked_until']),
        ]
        
        ordering = ['-threat_level', '-last_attempt']
    
    # Type Hinting: All methods have proper type hints
    def clean(self) -> None:
        """Validate model data before saving"""
        errors = {}
        
        try:
            # IP address validation
            if not self.ip_address:
                errors['ip_address'] = "IP address is required"
            
            # Subnet mask validation
            if self.subnet_mask is not None:
                if not 0 <= self.subnet_mask <= 32:
                    errors['subnet_mask'] = "Subnet mask must be between 0 and 32"
            
            # Date validation
            if not self.is_permanent and not self.blocked_until:
                errors['blocked_until'] = "Temporary blocks must have an expiration time"
            
            if self.blocked_until and self.blocked_until <= timezone.now():
                errors['blocked_until'] = "Block expiration must be in the future"
            
            # Confidence score validation
            if not 0 <= self.confidence_score <= 100:
                errors['confidence_score'] = "Confidence score must be between 0 and 100"
            
            # Attack count validation
            if self.attack_count < 0:
                errors['attack_count'] = "Attack count cannot be negative"
            
            # Max requests validation
            if self.max_requests_per_minute < 0:
                errors['max_requests_per_minute'] = "Max requests per minute cannot be negative"
            
            # Validate threat intel data
            if self.threat_intel_data and not isinstance(self.threat_intel_data, dict):
                errors['threat_intel_data'] = "Threat intelligence data must be a valid JSON object"
            
        except Exception as e:
            # Graceful Degradation: Log error but don't crash
            logger.error(f"IPBlacklist validation error for {self.ip_address}: {e}")
            errors['non_field_errors'] = "An unexpected validation error occurred"
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save with defensive programming"""
        try:
            # Auto-clean before saving
            self.full_clean()
            
            # Set defaults if not provided
            if not self.threat_intel_data:
                self.threat_intel_data = {}
            
            # Auto-detect geographic info if not provided
            if not self.country_code:
                self._detect_geographic_info()
            
            # Update last_attempt timestamp
            self.last_attempt = timezone.now()
            
            # Auto-expire if blocked_until is past
            if not self.is_permanent and self.blocked_until and self.blocked_until <= timezone.now():
                self.is_active = False
            
            super().save(*args, **kwargs)
            
            # Update cache
            self._update_cache()
            
        except Exception as e:
            logger.error(f"Failed to save IPBlacklist for {self.ip_address}: {e}")
            raise
    
    def _detect_geographic_info(self) -> None:
        """Detect geographic information for IP address"""
        try:
            # This is a placeholder - in production, you would use:
            # 1. GeoIP2 database
            # 2. External API service
            # 3. Local database lookup
            
            # Example: Use django.contrib.gis.geoip2 (requires geoip2 package)
            # from django.contrib.gis.geoip2 import GeoIP2
            # g = GeoIP2()
            # info = g.city(self.ip_address)
            # self.country_code = info.get('country_code')
            # self.country_name = info.get('country_name')
            # self.city = info.get('city')
            
            # For now, set placeholder values
            self.country_code = "XX"
            self.country_name = "Unknown"
            
        except Exception as e:
            # Graceful degradation: Don't fail if geo lookup fails
            logger.warning(f"Could not detect geographic info for {self.ip_address}: {e}")
            self.country_code = "XX"
            self.country_name = "Unknown"
    
    def _update_cache(self) -> None:
        """Update cache with defensive error handling"""
        try:
            cache_key = f'ip_blacklist:{self.ip_address}'
            
            # Only cache active entries
            if self.is_active and self.is_currently_blocked():
                cache_data = {
                    'id': self.id,
                    'ip_address': self.ip_address,
                    'subnet_mask': self.subnet_mask,
                    'is_permanent': self.is_permanent,
                    'blocked_until': self.blocked_until.isoformat() if self.blocked_until else None,
                    'max_requests_per_minute': self.max_requests_per_minute,
                    'threat_level': self.threat_level,
                }
                
                # Set cache with appropriate timeout
                if self.is_permanent:
                    timeout = 24 * 60 * 60  # 24 hours for permanent blocks
                elif self.blocked_until:
                    timeout = max(60, int((self.blocked_until - timezone.now()).total_seconds()))
                else:
                    timeout = 3600  # 1 hour default
                
                cache.set(cache_key, cache_data, timeout)
            else:
                # Remove from cache if not active
                cache.delete(cache_key)
            
            # Also update the global blacklist cache
            cache.delete('ip_blacklist_all_active')
            
        except Exception as e:
            logger.warning(f"Failed to update IP blacklist cache: {e}")
    
    # Business logic methods with defensive coding
    def is_currently_blocked(self) -> bool:
        """Check if IP is currently blocked"""
        try:
            if not self.is_active:
                return False
            
            if self.is_permanent:
                return True
            
            if self.blocked_until:
                return timezone.now() < self.blocked_until
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking block status for {self.ip_address}: {e}")
            return False  # Graceful degradation: Assume not blocked on error
    
    def increment_attack_count(self, attack_type: str = None) -> Tuple[bool, str]:
        """Increment attack count and update threat level"""
        try:
            self.attack_count += 1
            self.last_attempt = timezone.now()
            
            # Update threat level based on attack count
            if self.attack_count >= 100:
                self.threat_level = 'confirmed_attacker'
            elif self.attack_count >= 50:
                self.threat_level = 'critical'
            elif self.attack_count >= 20:
                self.threat_level = 'high'
            elif self.attack_count >= 10:
                self.threat_level = 'medium'
            
            # Update threat intel data
            if attack_type:
                if 'attack_types' not in self.threat_intel_data:
                    self.threat_intel_data['attack_types'] = []
                
                if attack_type not in self.threat_intel_data['attack_types']:
                    self.threat_intel_data['attack_types'].append(attack_type)
            
            self.save()
            
            logger.info(f"Incremented attack count for {self.ip_address}: {self.attack_count}")
            return True, f"Attack count incremented to {self.attack_count}"
            
        except Exception as e:
            logger.error(f"Failed to increment attack count for {self.ip_address}: {e}")
            return False, f"Error: {str(e)}"
    
    def extend_block(self, hours: int = 24, reason: str = None) -> Tuple[bool, str]:
        """Extend block duration"""
        try:
            if not self.is_active:
                return False, "IP is not currently blocked"
            
            if self.is_permanent:
                return False, "Cannot extend permanent block"
            
            # Calculate new expiration time
            new_expiration = max(
                self.blocked_until or timezone.now(),
                timezone.now() + timedelta(hours=hours)
            )
            
            self.blocked_until = new_expiration
            self.is_active = True
            
            if reason:
                self.notes = f"{self.notes}\n\nExtended by {hours}h: {reason}"
            
            self.save()
            
            logger.info(f"Extended block for {self.ip_address} by {hours} hours")
            return True, f"Block extended until {self.blocked_until}"
            
        except Exception as e:
            logger.error(f"Failed to extend block for {self.ip_address}: {e}")
            return False, f"Failed to extend block: {str(e)}"
    
    def unblock(self, reason: str = "Manually unblocked") -> Tuple[bool, str]:
        """Unblock IP address"""
        try:
            if not self.is_active:
                return False, "IP is not currently blocked"
            
            self.is_active = False
            self.blocked_until = None
            self.notes = f"{self.notes}\n\nUnblocked: {reason} ({timezone.now()})"
            
            self.save()
            
            logger.info(f"Unblocked IP {self.ip_address}: {reason}")
            return True, "IP unblocked successfully"
            
        except Exception as e:
            logger.error(f"Failed to unblock {self.ip_address}: {e}")
            return False, f"Failed to unblock: {str(e)}"
    
    def matches_ip(self, ip_address: str) -> bool:
        """Check if given IP matches this blacklist entry (including subnet)"""
        try:
            if not ip_address:
                return False
            
            # Direct match
            if self.ip_address == ip_address:
                return True
            
            # Subnet match (if subnet_mask is set)
            if self.subnet_mask is not None:
                try:
                    import ipaddress
                    network = ipaddress.ip_network(f"{self.ip_address}/{self.subnet_mask}", strict=False)
                    ip = ipaddress.ip_address(ip_address)
                    return ip in network
                except Exception:
                    # If IP parsing fails, fall back to string comparison
                    pass
            
            return False
            
        except Exception as e:
            logger.error(f"Error matching IP {ip_address} against {self.ip_address}: {e}")
            return False
    
    def get_block_details(self) -> Dict[str, Any]:
        """Get detailed block information"""
        try:
            is_blocked = self.is_currently_blocked()
            
            details = {
                'id': self.id,
                'ip_address': self.ip_address,
                'subnet_mask': self.subnet_mask,
                'is_blocked': is_blocked,
                'is_permanent': self.is_permanent,
                'is_active': self.is_active,
                'threat_level': self.threat_level,
                'threat_type': self.threat_type,
                'reason': self.reason,
                'confidence_score': self.confidence_score,
                'attack_count': self.attack_count,
                'first_seen': self.first_seen.isoformat() if self.first_seen else None,
                'last_attempt': self.last_attempt.isoformat() if self.last_attempt else None,
                'blocked_until': self.blocked_until.isoformat() if self.blocked_until else None,
                'max_requests_per_minute': self.max_requests_per_minute,
                'country_code': self.country_code,
                'country_name': self.country_name,
                'city': self.city,
                'isp': self.isp,
                'asn': self.asn,
                'organization': self.organization,
            }
            
            # Calculate time remaining for temporary blocks
            if is_blocked and self.blocked_until and not self.is_permanent:
                remaining = self.blocked_until - timezone.now()
                details['time_remaining'] = {
                    'total_seconds': int(remaining.total_seconds()),
                    'hours': remaining.days * 24 + remaining.seconds // 3600,
                    'minutes': (remaining.seconds % 3600) // 60,
                    'seconds': remaining.seconds % 60,
                }
            
            return details
            
        except Exception as e:
            logger.error(f"Error getting block details for {self.ip_address}: {e}")
            return {
                'ip_address': self.ip_address,
                'is_blocked': False,
                'error': 'Could not retrieve block details'
            }
    
    @classmethod
    def is_ip_blocked(cls, ip_address: str, check_subnet: bool = True) -> Tuple[bool, Optional['IPBlacklist']]:
        """Check if IP is blacklisted with defensive coding"""
        try:
            if not ip_address:
                return False, None
            
            # Try cache first
            cache_key = f'ip_blacklist:{ip_address}'
            cached = cache.get(cache_key)
            
            if cached:
                try:
                    blacklist_entry = cls.objects.get(id=cached['id'])
                    if blacklist_entry.is_currently_blocked():
                        return True, blacklist_entry
                except Exception:
                    pass
            
            # Build query
            query = cls.objects.filter(is_active=True)
            
            if check_subnet:
                # Complex query for subnet matching - we'll handle in Python
                potential_matches = query.all()
                for entry in potential_matches:
                    if entry.matches_ip(ip_address) and entry.is_currently_blocked():
                        # Update cache
                        entry._update_cache()
                        return True, entry
            else:
                # Simple IP match
                blacklist_entry = query.filter(ip_address=ip_address).first()
                if blacklist_entry and blacklist_entry.is_currently_blocked():
                    blacklist_entry._update_cache()
                    return True, blacklist_entry
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error checking if IP {ip_address} is blocked: {e}")
            return False, None  # Graceful degradation: Assume not blocked
    
    @classmethod
    def block_ip(cls,
                ip_address: str,
                reason: str = "Suspicious activity",
                threat_level: str = "medium",
                duration_hours: int = 24,
                reported_by=None,
                **kwargs) -> Tuple[bool, str, Optional['IPBlacklist']]:
        """Block an IP address with defensive coding"""
        try:
            # Validate IP address
            import ipaddress
            try:
                ipaddress.ip_address(ip_address)
            except ValueError:
                return False, f"Invalid IP address: {ip_address}", None
            
            # Check if already blocked
            is_blocked, existing_entry = cls.is_ip_blocked(ip_address)
            if is_blocked and existing_entry:
                return False, f"IP {ip_address} is already blocked", existing_entry
            
            # Calculate expiration time
            blocked_until = None
            is_permanent = kwargs.get('is_permanent', False)
            
            if not is_permanent:
                blocked_until = timezone.now() + timedelta(hours=duration_hours)
            
            # Create blacklist entry
            blacklist_entry = cls(
                ip_address=ip_address,
                subnet_mask=kwargs.get('subnet_mask'),
                reason=reason,
                threat_level=threat_level,
                threat_type=kwargs.get('threat_type', 'suspicious_pattern'),
                is_active=True,
                is_permanent=is_permanent,
                blocked_until=blocked_until,
                max_requests_per_minute=kwargs.get('max_requests_per_minute', 0),
                detection_method=kwargs.get('detection_method', 'manual'),
                confidence_score=kwargs.get('confidence_score', 80.0),
                reported_by=reported_by,
                auto_blocked_by=kwargs.get('auto_blocked_by'),
                notes=kwargs.get('notes'),
                threat_intel_data=kwargs.get('threat_intel_data', {})
            )
            
            # Set geographic info if provided
            if kwargs.get('country_code'):
                blacklist_entry.country_code = kwargs['country_code']
                blacklist_entry.country_name = kwargs.get('country_name')
                blacklist_entry.city = kwargs.get('city')
                blacklist_entry.isp = kwargs.get('isp')
                blacklist_entry.asn = kwargs.get('asn')
                blacklist_entry.organization = kwargs.get('organization')
            
            blacklist_entry.save()
            
            logger.warning(f"IP {ip_address} blocked: {reason}")
            return True, f"IP {ip_address} blocked successfully", blacklist_entry
            
        except ValidationError as e:
            logger.error(f"Validation error blocking IP {ip_address}: {e}")
            return False, f"Validation error: {e}", None
        except Exception as e:
            logger.error(f"Error blocking IP {ip_address}: {e}")
            return False, f"Error blocking IP: {str(e)}", None
    
    @classmethod
    def unblock_ip(cls, ip_address: str, reason: str = "Manual unblock") -> Tuple[bool, str]:
        """Unblock an IP address"""
        try:
            # Find active blacklist entries for this IP
            entries = cls.objects.filter(ip_address=ip_address, is_active=True)
            
            if not entries.exists():
                return False, f"No active block found for IP {ip_address}"
            
            # Unblock all matching entries
            unblocked_count = 0
            for entry in entries:
                success, message = entry.unblock(reason)
                if success:
                    unblocked_count += 1
            
            if unblocked_count > 0:
                logger.info(f"Unblocked IP {ip_address}: {reason}")
                return True, f"Unblocked {unblocked_count} entries for IP {ip_address}"
            else:
                return False, f"Failed to unblock IP {ip_address}"
            
        except Exception as e:
            logger.error(f"Error unblocking IP {ip_address}: {e}")
            return False, f"Error unblocking IP: {str(e)}"
    
    @classmethod
    def cleanup_expired_blocks(cls) -> int:
        """Clean up expired temporary blocks"""
        try:
            now = timezone.now()
            
            expired_blocks = cls.objects.filter(
                is_active=True,
                is_permanent=False,
                blocked_until__lte=now
            )
            
            count = expired_blocks.count()
            
            # Deactivate expired blocks
            expired_blocks.update(
                is_active=False,
                notes=models.functions.Concat(
                    models.F('notes'),
                    models.Value(f"\n\nAuto-expired: {now}"),
                    output_field=models.TextField()
                )
            )
            
            # Clear cache for expired blocks
            for block in expired_blocks:
                try:
                    cache.delete(f'ip_blacklist:{block.ip_address}')
                except Exception:
                    pass
            
            if count > 0:
                logger.info(f"Cleaned up {count} expired IP blocks")
            
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired IP blocks: {e}")
            return 0
    
    @classmethod
    def get_block_statistics(cls) -> Dict[str, Any]:
        """Get blacklist statistics"""
        try:
            total_blocks = cls.objects.count()
            active_blocks = cls.objects.filter(is_active=True).count()
            permanent_blocks = cls.objects.filter(is_permanent=True, is_active=True).count()
            temporary_blocks = cls.objects.filter(is_permanent=False, is_active=True).count()
            
            # Count by threat level
            threat_level_stats = cls.objects.filter(is_active=True).values(
                'threat_level'
            ).annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Count by threat type
            threat_type_stats = cls.objects.filter(is_active=True).values(
                'threat_type'
            ).annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Count by country
            country_stats = cls.objects.filter(
                is_active=True,
                country_code__isnull=False
            ).values(
                'country_code',
                'country_name'
            ).annotate(
                count=Count('id')
            ).order_by('-count')[:10]  # Top 10 countries
            
            # Recent blocks (last 7 days)
            week_ago = timezone.now() - timedelta(days=7)
            recent_blocks = cls.objects.filter(
                first_seen__gte=week_ago
            ).count()
            
            return {
                'total_blocks': total_blocks,
                'active_blocks': active_blocks,
                'permanent_blocks': permanent_blocks,
                'temporary_blocks': temporary_blocks,
                'recent_blocks_7d': recent_blocks,
                'threat_level_distribution': list(threat_level_stats),
                'threat_type_distribution': list(threat_type_stats),
                'top_countries': list(country_stats),
                'generated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting blacklist statistics: {e}")
            return {
                'error': 'Could not retrieve statistics',
                'generated_at': timezone.now().isoformat()
            }
    
    def __str__(self) -> str:
        """String representation"""
        status = "Active" if self.is_active else "Inactive"
        permanent = " (Permanent)" if self.is_permanent else ""
        threat = f" [{self.threat_level}]"
        return f"{self.ip_address}{permanent} - {status}{threat}"
    
    @property
    def block_duration(self) -> Optional[timedelta]:
        """Calculate block duration"""
        try:
            if not self.first_seen:
                return None
            
            end_time = self.blocked_until or timezone.now()
            return end_time - self.first_seen
            
        except Exception:
            return None
        
        
        
        # models.py - Add this after other models
class WithdrawalProtection(models.Model):
    """
    WithdrawalProtection model with comprehensive defensive coding
    Financial transaction security and fraud prevention for withdrawals
    """
    
    # Null Object Pattern: Default values for all fields
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="User",
        help_text="User associated with withdrawal protection",
        related_name='withdrawal_protections',
        db_index=True)
    
    # Protection status
    is_active = models.BooleanField(
        verbose_name="Is Active",
        help_text="Whether withdrawal protection is active",
        default=True,
        db_index=True
    )
    
    protection_level = models.CharField(
        max_length=20,
        verbose_name="Protection Level",
        help_text="Level of withdrawal protection",
        choices=[
            ('disabled', 'Disabled'),
            ('basic', 'Basic Protection'),
            ('standard', 'Standard Protection'),
            ('enhanced', 'Enhanced Protection'),
            ('maximum', 'Maximum Protection'),
        ],
        default='standard',
        db_index=True
    )
    
    # Withdrawal limits
    daily_limit = models.DecimalField(
        verbose_name="Daily Withdrawal Limit",
        help_text="Maximum withdrawal amount per day",
        max_digits=15,
        decimal_places=2,
        default=1000.00)
    
    weekly_limit = models.DecimalField(
        verbose_name="Weekly Withdrawal Limit",
        help_text="Maximum withdrawal amount per week",
        max_digits=15,
        decimal_places=2,
        default=5000.00)
    
    monthly_limit = models.DecimalField(
        verbose_name="Monthly Withdrawal Limit",
        help_text="Maximum withdrawal amount per month",
        max_digits=15,
        decimal_places=2,
        default=20000.00)
    
    single_transaction_limit = models.DecimalField(
        verbose_name="Single Transaction Limit",
        help_text="Maximum amount per single withdrawal",
        max_digits=15,
        decimal_places=2,
        default=2000.00)
    
    min_withdrawal_amount = models.DecimalField(
        verbose_name="Minimum Withdrawal Amount",
        help_text="Minimum amount per withdrawal",
        max_digits=15,
        decimal_places=2,
        default=10.00)
    
    # Frequency limits
    daily_count_limit = models.PositiveIntegerField(
        verbose_name="Daily Count Limit",
        help_text="Maximum number of withdrawals per day",
        default=5
    )
    
    weekly_count_limit = models.PositiveIntegerField(
        verbose_name="Weekly Count Limit",
        help_text="Maximum number of withdrawals per week",
        default=20
    )
    
    monthly_count_limit = models.PositiveIntegerField(
        verbose_name="Monthly Count Limit",
        help_text="Maximum number of withdrawals per month",
        default=50
    )
    
    # Security features
    require_2fa = models.BooleanField(
        verbose_name="Require 2FA",
        help_text="Require two-factor authentication for withdrawals",
        default=False
    )
    
    require_email_confirmation = models.BooleanField(
        verbose_name="Require Email Confirmation",
        help_text="Require email confirmation for withdrawals",
        default=True
    )
    
    require_sms_confirmation = models.BooleanField(
        verbose_name="Require SMS Confirmation",
        help_text="Require SMS confirmation for withdrawals",
        default=False
    )
    
    delay_hours = models.PositiveIntegerField(
        verbose_name="Withdrawal Delay (Hours)",
        help_text="Delay before processing withdrawal (in hours)",
        default=0
    )
    
    # Risk assessment
    risk_score = models.FloatField(
        verbose_name="Risk Score",
        help_text="Current risk score (0-100)",
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    risk_level = models.CharField(
        max_length=20,
        verbose_name="Risk Level",
        help_text="Current risk level",
        choices=[
            ('low', 'Low Risk'),
            ('medium', 'Medium Risk'),
            ('high', 'High Risk'),
            ('very_high', 'Very High Risk'),
        ],
        default='low',
        db_index=True
    )
    
    auto_hold_threshold = models.DecimalField(
        verbose_name="Auto-Hold Threshold",
        help_text="Amount threshold for automatic hold review",
        max_digits=15,
        decimal_places=2,
        default=5000.00)
    
    # Whitelist/Blacklist
    whitelisted_ips = models.JSONField(
        verbose_name="Whitelisted IPs",
        help_text="IP addresses allowed for withdrawals",
        default=list,
        blank=True,
        null=True
    )
    
    whitelisted_devices = models.JSONField(
        verbose_name="Whitelisted Devices",
        help_text="Device IDs allowed for withdrawals",
        default=list,
    )
    
    blacklisted_destinations = models.JSONField(
        verbose_name="Blacklisted Destinations",
        help_text="Blocked withdrawal destinations (wallets/banks)",
        default=list,
        blank=True,
        null=True
    )
    
    # Time-based restrictions
    allowed_withdrawal_hours = models.JSONField(
        verbose_name="Allowed Withdrawal Hours",
        help_text="Hours when withdrawals are allowed (0-23)",
        default=get_hours_default, # All hours by default
        blank=True,
        null=True
    )
    
    allowed_withdrawal_days = models.JSONField(
        verbose_name="Allowed Withdrawal Days",
        help_text="Days when withdrawals are allowed (0=Monday, 6=Sunday)",
        default=get_hours_default,
    )
    
    # Verification requirements
    require_id_verification = models.BooleanField(
        verbose_name="Require ID Verification",
        help_text="Require identity verification for withdrawals",
        default=True
    )
    
    require_address_verification = models.BooleanField(
        verbose_name="Require Address Verification",
        help_text="Require address verification for withdrawals",
        default=False
    )
    
    min_account_age_days = models.PositiveIntegerField(
        verbose_name="Minimum Account Age (Days)",
        help_text="Minimum account age required for withdrawals",
        default=7
    )
    
    # Monitoring and alerts
    notify_on_large_withdrawal = models.BooleanField(
        verbose_name="Notify on Large Withdrawal",
        help_text="Send notification for large withdrawals",
        default=True
    )
    
    large_withdrawal_threshold = models.DecimalField(
        verbose_name="Large Withdrawal Threshold",
        help_text="Amount considered as large withdrawal",
        max_digits=15,
        decimal_places=2,
        default=1000.00)
    
    notify_on_suspicious_activity = models.BooleanField(
        verbose_name="Notify on Suspicious Activity",
        help_text="Send notification for suspicious withdrawals",
        default=True
    )
    
    # Protection history
    total_withdrawals = models.PositiveIntegerField(
        verbose_name="Total Withdrawals",
        help_text="Total number of withdrawals made",
        default=0
    )
    
    total_withdrawal_amount = models.DecimalField(
        verbose_name="Total Withdrawal Amount",
        help_text="Total amount withdrawn",
        max_digits=20,
        decimal_places=2,
        default=0.00)
    
    last_withdrawal_at = models.DateTimeField(
        verbose_name="Last Withdrawal At",
        help_text="Time of last withdrawal",
        null=True,
        blank=True
    )
    
    # Custom rules and exceptions
    custom_rules = models.JSONField(
        verbose_name="Custom Rules",
        help_text="Custom withdrawal protection rules",
        default=dict,
        null=True
    )
    
    exceptions = models.JSONField(
        verbose_name="Exceptions",
        help_text="Exceptions to protection rules",
        default=dict,
        blank=True,
    )
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        verbose_name="Created By",
        help_text="User who created this protection",
        null=True,
        blank=True,
        related_name='created_withdrawal_protections')
    
    notes = models.TextField(
        verbose_name="Notes",
        help_text="Additional notes/comments",
    )
    
    created_at = models.DateTimeField(
        verbose_name="Created At",
        auto_now_add=True
    )
    
    updated_at = models.DateTimeField(
        verbose_name="Updated At",
        auto_now=True
    )
    
    # Model-Level Constraints
    class Meta:
        db_table = 'security_withdrawalprotection'
        verbose_name = 'Withdrawal Protection'
        verbose_name_plural = 'Withdrawal Protections'
        
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['protection_level', 'is_active']),
            models.Index(fields=['risk_level']),
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
        ]
        
        constraints = [
            # Ensure one active protection per user
            models.UniqueConstraint(
                fields=['user'],
                name='unique_active_protection_per_user'
            ),
        ]
        
        ordering = ['-updated_at']
    
    # Type Hinting: All methods have proper type hints
    def clean(self) -> None:
        """Validate model data before saving"""
        errors = {}
        
        try:
            # Limit validation
            if self.daily_limit <= 0:
                errors['daily_limit'] = "Daily limit must be positive"
            
            if self.weekly_limit <= 0:
                errors['weekly_limit'] = "Weekly limit must be positive"
            
            if self.monthly_limit <= 0:
                errors['monthly_limit'] = "Monthly limit must be positive"
            
            if self.single_transaction_limit <= 0:
                errors['single_transaction_limit'] = "Single transaction limit must be positive"
            
            if self.min_withdrawal_amount <= 0:
                errors['min_withdrawal_amount'] = "Minimum withdrawal amount must be positive"
            
            # Logical validation
            if self.daily_limit > self.weekly_limit:
                errors['daily_limit'] = "Daily limit cannot exceed weekly limit"
            
            if self.weekly_limit > self.monthly_limit:
                errors['weekly_limit'] = "Weekly limit cannot exceed monthly limit"
            
            if self.single_transaction_limit > self.daily_limit:
                errors['single_transaction_limit'] = "Single transaction limit cannot exceed daily limit"
            
            if self.min_withdrawal_amount > self.single_transaction_limit:
                errors['min_withdrawal_amount'] = "Minimum withdrawal amount cannot exceed single transaction limit"
            
            # Count limit validation
            if self.daily_count_limit <= 0:
                errors['daily_count_limit'] = "Daily count limit must be positive"
            
            if self.weekly_count_limit <= 0:
                errors['weekly_count_limit'] = "Weekly count limit must be positive"
            
            if self.monthly_count_limit <= 0:
                errors['monthly_count_limit'] = "Monthly count limit must be positive"
            
            # Risk score validation
            if not 0 <= self.risk_score <= 100:
                errors['risk_score'] = "Risk score must be between 0 and 100"
            
            # JSON field validation
            if self.whitelisted_ips and not isinstance(self.whitelisted_ips, list):
                errors['whitelisted_ips'] = "Whitelisted IPs must be a list"
            
            if self.whitelisted_devices and not isinstance(self.whitelisted_devices, list):
                errors['whitelisted_devices'] = "Whitelisted devices must be a list"
            
            if self.blacklisted_destinations and not isinstance(self.blacklisted_destinations, list):
                errors['blacklisted_destinations'] = "Blacklisted destinations must be a list"
            
            if self.allowed_withdrawal_hours:
                if not isinstance(self.allowed_withdrawal_hours, list):
                    errors['allowed_withdrawal_hours'] = "Allowed withdrawal hours must be a list"
                else:
                    for hour in self.allowed_withdrawal_hours:
                        if not isinstance(hour, int) or not 0 <= hour <= 23:
                            errors['allowed_withdrawal_hours'] = "Allowed hours must be integers between 0 and 23"
            
            if self.allowed_withdrawal_days:
                if not isinstance(self.allowed_withdrawal_days, list):
                    errors['allowed_withdrawal_days'] = "Allowed withdrawal days must be a list"
                else:
                    for day in self.allowed_withdrawal_days:
                        if not isinstance(day, int) or not 0 <= day <= 6:
                            errors['allowed_withdrawal_days'] = "Allowed days must be integers between 0 and 6"
            
            # Account age validation
            if self.min_account_age_days < 0:
                errors['min_account_age_days'] = "Minimum account age cannot be negative"
            
            # Auto-hold threshold validation
            if self.auto_hold_threshold < 0:
                errors['auto_hold_threshold'] = "Auto-hold threshold cannot be negative"
            
            # Large withdrawal threshold validation
            if self.large_withdrawal_threshold < 0:
                errors['large_withdrawal_threshold'] = "Large withdrawal threshold cannot be negative"
            
        except Exception as e:
            # Graceful Degradation: Log error but don't crash
            logger.error(f"WithdrawalProtection validation error for user {self.user_id}: {e}")
            errors['non_field_errors'] = "An unexpected validation error occurred"
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args: Any, **kwargs: Any) -> None:
        """Override save with defensive programming"""
        try:
            # Auto-clean before saving
            self.full_clean()
            
            # Set defaults for JSON fields if empty
            if not self.whitelisted_ips:
                self.whitelisted_ips = []
            
            if not self.whitelisted_devices:
                self.whitelisted_devices = []
            
            if not self.blacklisted_destinations:
                self.blacklisted_destinations = []
            
            if not self.allowed_withdrawal_hours:
                self.allowed_withdrawal_hours = list(range(0, 24))
            
            if not self.allowed_withdrawal_days:
                self.allowed_withdrawal_days = list(range(0, 7))
            
            if not self.custom_rules:
                self.custom_rules = {}
            
            if not self.exceptions:
                self.exceptions = {}
            
            # Update risk level based on risk score
            self._update_risk_level()
            
            # Update protection level based on settings
            self._update_protection_level()
            
            # Ensure only one active protection per user
            if self.is_active and self.pk:
                WithdrawalProtection.objects.filter(
                    user=self.user,
                    is_active=True
                ).exclude(pk=self.pk).update(is_active=False)
            
            super().save(*args, **kwargs)
            
            # Update cache
            self._update_cache()
            
        except Exception as e:
            logger.error(f"Failed to save WithdrawalProtection for user {self.user_id}: {e}")
            raise
    
    def _update_risk_level(self) -> None:
        """Update risk level based on risk score"""
        try:
            if self.risk_score >= 80:
                self.risk_level = 'very_high'
            elif self.risk_score >= 60:
                self.risk_level = 'high'
            elif self.risk_score >= 30:
                self.risk_level = 'medium'
            else:
                self.risk_level = 'low'
        except Exception as e:
            logger.warning(f"Error updating risk level for user {self.user_id}: {e}")
            self.risk_level = 'low'
    
    def _update_protection_level(self) -> None:
        """Update protection level based on settings"""
        try:
            # Calculate protection score based on security features
            score = 0
            
            if self.require_2fa:
                score += 20
            if self.require_email_confirmation:
                score += 10
            if self.require_sms_confirmation:
                score += 15
            if self.delay_hours > 0:
                score += min(self.delay_hours * 2, 20)
            if self.require_id_verification:
                score += 15
            if self.require_address_verification:
                score += 10
            
            # Set protection level based on score
            if score >= 70:
                self.protection_level = 'maximum'
            elif score >= 50:
                self.protection_level = 'enhanced'
            elif score >= 30:
                self.protection_level = 'standard'
            elif score >= 10:
                self.protection_level = 'basic'
            else:
                self.protection_level = 'disabled'
                
        except Exception as e:
            logger.warning(f"Error updating protection level for user {self.user_id}: {e}")
            self.protection_level = 'standard'
    
    def _update_cache(self) -> None:
        """Update cache with defensive error handling"""
        try:
            if self.is_active:
                cache_key = f'withdrawal_protection:{self.user_id}'
                cache_data = {
                    'id': self.id,
                    'protection_level': self.protection_level,
                    'risk_level': self.risk_level,
                    'daily_limit': float(self.daily_limit),
                    'weekly_limit': float(self.weekly_limit),
                    'monthly_limit': float(self.monthly_limit),
                    'single_transaction_limit': float(self.single_transaction_limit),
                    'min_withdrawal_amount': float(self.min_withdrawal_amount),
                    'require_2fa': self.require_2fa,
                    'delay_hours': self.delay_hours,
                }
                cache.set(cache_key, cache_data, timeout=300)  # 5 minutes
        except Exception as e:
            logger.warning(f"Failed to update withdrawal protection cache for user {self.user_id}: {e}")
    
    # Business logic methods with defensive coding
    def can_withdraw(self, 
                    amount: Decimal, 
                    destination: str = None,
                    ip_address: str = None,
                    device_id: str = None,
                    check_time: bool = True) -> Tuple[bool, List[str]]:
        """
        Check if withdrawal is allowed with detailed reasons
        
        Returns:
            Tuple[bool, List[str]]: (is_allowed, list_of_reasons)
        """
        reasons = []
        
        try:
            # Basic checks
            if not self.is_active:
                reasons.append("Withdrawal protection is not active")
                return False, reasons
            
            if self.protection_level == 'disabled':
                reasons.append("Withdrawal protection is disabled")
                return True, reasons  # Allowed when disabled
            
            # Amount validation
            if amount <= 0:
                reasons.append("Withdrawal amount must be positive")
                return False, reasons
            
            # Check minimum amount
            if amount < self.min_withdrawal_amount:
                reasons.append(f"Amount below minimum ({self.min_withdrawal_amount})")
                return False, reasons
            
            # Check single transaction limit
            if amount > self.single_transaction_limit:
                reasons.append(f"Amount exceeds single transaction limit ({self.single_transaction_limit})")
                return False, reasons
            
            # Check daily limit (simplified - would need actual usage tracking)
            # This is a placeholder for actual usage checking logic
            
            # Check blacklisted destinations
            if destination and destination in (self.blacklisted_destinations or []):
                reasons.append(f"Destination is blacklisted: {destination}")
                return False, reasons
            
            # Check IP whitelist
            if ip_address and self.whitelisted_ips and ip_address not in self.whitelisted_ips:
                reasons.append(f"IP address not whitelisted: {ip_address}")
                return False, reasons
            
            # Check device whitelist
            if device_id and self.whitelisted_devices and device_id not in self.whitelisted_devices:
                reasons.append(f"Device not whitelisted: {device_id}")
                return False, reasons
            
            # Check time restrictions
            if check_time:
                now = timezone.now()
                current_hour = now.hour
                current_day = now.weekday()  # Monday=0, Sunday=6
                
                if current_hour not in (self.allowed_withdrawal_hours or list(range(0, 24))):
                    reasons.append(f"Withdrawals not allowed at hour {current_hour}")
                    return False, reasons
                
                if current_day not in (self.allowed_withdrawal_days or list(range(0, 7))):
                    reasons.append(f"Withdrawals not allowed on day {current_day}")
                    return False, reasons
            
            # Check risk level restrictions
            if self.risk_level in ['high', 'very_high'] and amount > self.auto_hold_threshold:
                reasons.append(f"Large withdrawal requires manual review (risk level: {self.risk_level})")
                return False, reasons
            
            # All checks passed
            return True, ["Withdrawal allowed"]
            
        except Exception as e:
            logger.error(f"Error checking withdrawal permission for user {self.user_id}: {e}")
            reasons.append(f"Error checking withdrawal permission: {str(e)}")
            return False, reasons
    
    def record_withdrawal(self, amount: Decimal) -> Tuple[bool, str]:
        """Record a successful withdrawal"""
        try:
            # Update statistics
            self.total_withdrawals += 1
            self.total_withdrawal_amount += amount
            self.last_withdrawal_at = timezone.now()
            
            # Recalculate risk score based on withdrawal patterns
            self._recalculate_risk_score()
            
            self.save()
            
            logger.info(f"Recorded withdrawal for user {self.user_id}: {amount}")
            return True, "Withdrawal recorded successfully"
            
        except Exception as e:
            logger.error(f"Failed to record withdrawal for user {self.user_id}: {e}")
            return False, f"Failed to record withdrawal: {str(e)}"
    
    def _recalculate_risk_score(self) -> None:
        """Recalculate risk score based on withdrawal patterns"""
        try:
            base_score = 0.0
            
            # Increase risk for frequent withdrawals
            if self.total_withdrawals > 100:
                base_score += 30
            elif self.total_withdrawals > 50:
                base_score += 20
            elif self.total_withdrawals > 20:
                base_score += 10
            
            # Increase risk for large total amount
            total_amount = float(self.total_withdrawal_amount)
            if total_amount > 100000:
                base_score += 40
            elif total_amount > 50000:
                base_score += 30
            elif total_amount > 10000:
                base_score += 20
            elif total_amount > 1000:
                base_score += 10
            
            # Decrease risk for established patterns (if last withdrawal was long ago)
            if self.last_withdrawal_at:
                days_since_last = (timezone.now() - self.last_withdrawal_at).days
                if days_since_last > 30:
                    base_score -= 20
                elif days_since_last > 7:
                    base_score -= 10
            
            # Normalize score
            base_score = max(0, min(100, base_score))
            
            # Apply custom rules if any
            if self.custom_rules and 'risk_adjustment' in self.custom_rules:
                try:
                    adjustment = float(self.custom_rules['risk_adjustment'])
                    base_score += adjustment
                except (ValueError, TypeError):
                    pass
            
            self.risk_score = base_score
            
        except Exception as e:
            logger.warning(f"Error recalculating risk score for user {self.user_id}: {e}")
            # Don't fail if risk calculation fails
    
    def add_ip_to_whitelist(self, ip_address: str) -> Tuple[bool, str]:
        """Add IP address to whitelist"""
        try:
            # Validate IP address
            import ipaddress
            ipaddress.ip_address(ip_address)
            
            if ip_address in (self.whitelisted_ips or []):
                return False, f"IP address already whitelisted: {ip_address}"
            
            self.whitelisted_ips.append(ip_address)
            self.save()
            
            return True, f"IP address added to whitelist: {ip_address}"
            
        except ValueError:
            return False, f"Invalid IP address: {ip_address}"
        except Exception as e:
            logger.error(f"Failed to add IP to whitelist for user {self.user_id}: {e}")
            return False, f"Failed to add IP to whitelist: {str(e)}"
    
    def remove_ip_from_whitelist(self, ip_address: str) -> Tuple[bool, str]:
        """Remove IP address from whitelist"""
        try:
            if ip_address not in (self.whitelisted_ips or []):
                return False, f"IP address not in whitelist: {ip_address}"
            
            self.whitelisted_ips.remove(ip_address)
            self.save()
            
            return True, f"IP address removed from whitelist: {ip_address}"
            
        except Exception as e:
            logger.error(f"Failed to remove IP from whitelist for user {self.user_id}: {e}")
            return False, f"Failed to remove IP from whitelist: {str(e)}"
    
    def add_to_blacklist(self, destination: str, reason: str = None) -> Tuple[bool, str]:
        """Add destination to blacklist"""
        try:
            if destination in (self.blacklisted_destinations or []):
                return False, f"Destination already blacklisted: {destination}"
            
            self.blacklisted_destinations.append(destination)
            
            # Add to exceptions with reason
            if reason:
                if 'blacklist_reasons' not in self.exceptions:
                    self.exceptions['blacklist_reasons'] = {}
                self.exceptions['blacklist_reasons'][destination] = reason
            
            self.save()
            
            return True, f"Destination added to blacklist: {destination}"
            
        except Exception as e:
            logger.error(f"Failed to add destination to blacklist for user {self.user_id}: {e}")
            return False, f"Failed to add to blacklist: {str(e)}"
    
    def remove_from_blacklist(self, destination: str) -> Tuple[bool, str]:
        """Remove destination from blacklist"""
        try:
            if destination not in (self.blacklisted_destinations or []):
                return False, f"Destination not in blacklist: {destination}"
            
            self.blacklisted_destinations.remove(destination)
            
            # Remove from exceptions
            if self.exceptions and 'blacklist_reasons' in self.exceptions:
                self.exceptions['blacklist_reasons'].pop(destination, None)
            
            self.save()
            
            return True, f"Destination removed from blacklist: {destination}"
            
        except Exception as e:
            logger.error(f"Failed to remove destination from blacklist for user {self.user_id}: {e}")
            return False, f"Failed to remove from blacklist: {str(e)}"
    
    def get_withdrawal_summary(self, period_days: int = 30) -> Dict[str, Any]:
        """Get withdrawal summary for specified period"""
        try:
            # This would typically query actual withdrawal transactions
            # For now, return mock/summary data
            from django.db.models import Sum, Count
            from datetime import datetime, timedelta
            
            # Placeholder for actual transaction query
            # In real implementation, you would query the withdrawal transaction model
            # transactions = WithdrawalTransaction.objects.filter(
            #     user=self.user,
            #     created_at__gte=timezone.now() - timedelta(days=period_days)
            # ).aggregate(
            #     total_count=Count('id'),
            #     total_amount=Sum('amount'),
            #     average_amount=Avg('amount')
            # )
            
            # Mock data for example
            summary = {
                'period_days': period_days,
                'total_withdrawals': self.total_withdrawals,
                'total_amount': float(self.total_withdrawal_amount),
                'last_withdrawal': self.last_withdrawal_at.isoformat() if self.last_withdrawal_at else None,
                'current_limits': {
                    'daily': float(self.daily_limit),
                    'weekly': float(self.weekly_limit),
                    'monthly': float(self.monthly_limit),
                    'single_transaction': float(self.single_transaction_limit),
                },
                'protection_status': {
                    'is_active': self.is_active,
                    'protection_level': self.protection_level,
                    'risk_level': self.risk_level,
                    'risk_score': self.risk_score,
                },
                'security_features': {
                    'require_2fa': self.require_2fa,
                    'require_email_confirmation': self.require_email_confirmation,
                    'require_sms_confirmation': self.require_sms_confirmation,
                    'delay_hours': self.delay_hours,
                },
                'generated_at': timezone.now().isoformat()
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting withdrawal summary for user {self.user_id}: {e}")
            return {
                'error': 'Could not retrieve withdrawal summary',
                'period_days': period_days,
                'user_id': self.user_id
            }
    
    def update_limits(self, 
                     daily_limit: Decimal = None,
                     weekly_limit: Decimal = None,
                     monthly_limit: Decimal = None,
                     single_transaction_limit: Decimal = None,
                     updated_by=None) -> Tuple[bool, str]:
        """Update withdrawal limits"""
        try:
            changes = []
            
            if daily_limit is not None and daily_limit != self.daily_limit:
                self.daily_limit = daily_limit
                changes.append(f"Daily limit: {daily_limit}")
            
            if weekly_limit is not None and weekly_limit != self.weekly_limit:
                self.weekly_limit = weekly_limit
                changes.append(f"Weekly limit: {weekly_limit}")
            
            if monthly_limit is not None and monthly_limit != self.monthly_limit:
                self.monthly_limit = monthly_limit
                changes.append(f"Monthly limit: {monthly_limit}")
            
            if single_transaction_limit is not None and single_transaction_limit != self.single_transaction_limit:
                self.single_transaction_limit = single_transaction_limit
                changes.append(f"Single transaction limit: {single_transaction_limit}")
            
            if changes:
                self.updated_by = updated_by
                self.save()
                
                log_message = f"Updated limits: {', '.join(changes)}"
                logger.info(f"Updated withdrawal limits for user {self.user_id}: {log_message}")
                
                return True, log_message
            
            return False, "No changes made"
            
        except Exception as e:
            logger.error(f"Failed to update limits for user {self.user_id}: {e}")
            return False, f"Failed to update limits: {str(e)}"
    
    @classmethod
    def get_user_protection(cls, user_id: int) -> Optional['WithdrawalProtection']:
        """Get active withdrawal protection for user"""
        try:
            cache_key = f'withdrawal_protection:{user_id}'
            
            # Try cache first
            cached = cache.get(cache_key)
            if cached:
                try:
                    protection = cls.objects.get(id=cached['id'], is_active=True)
                    return protection
                except cls.DoesNotExist:
                    pass
            
            # Query database
            protection = cls.objects.filter(user_id=user_id, is_active=True).first()
            
            # Create default protection if none exists
            if not protection:
                protection = cls.create_default_protection(user_id)
            
            # Update cache
            if protection:
                protection._update_cache()
            
            return protection
            
        except Exception as e:
            logger.error(f"Error getting withdrawal protection for user {user_id}: {e}")
            return None
    
    @classmethod
    def create_default_protection(cls, user_id: int) -> 'WithdrawalProtection':
        """Create default withdrawal protection for user"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            user = User.objects.get(id=user_id)
            
            protection = cls(
                user=user,
                is_active=True,
                protection_level='standard',
                # Limits already have defaults
                notes="Auto-created default protection"
            )
            
            protection.save()
            
            logger.info(f"Created default withdrawal protection for user {user_id}")
            return protection
            
        except Exception as e:
            logger.error(f"Failed to create default protection for user {user_id}: {e}")
            # Return a minimal protection object
            return cls(
                user_id=user_id,
                is_active=True,
                protection_level='standard'
            )
    
    def __str__(self) -> str:
        """String representation"""
        status = "Active" if self.is_active else "Inactive"
        level = self.protection_level.title()
        risk = self.risk_level.title()
        return f"{self.user} - {level} Protection ({risk} Risk) [{status}]"
    
    @property
    def daily_remaining(self) -> Decimal:
        """Calculate daily remaining limit (placeholder)"""
        # In real implementation, you would calculate based on actual withdrawals today
        return self.daily_limit
    
    @property
    def weekly_remaining(self) -> Decimal:
        """Calculate weekly remaining limit (placeholder)"""
        # In real implementation, you would calculate based on actual withdrawals this week
        return self.weekly_limit
    
    @property
    def monthly_remaining(self) -> Decimal:
        """Calculate monthly remaining limit (placeholder)"""
        # In real implementation, you would calculate based on actual withdrawals this month
        return self.monthly_limit
    