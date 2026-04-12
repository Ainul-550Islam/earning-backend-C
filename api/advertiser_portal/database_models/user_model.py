"""
User Database Model

This module contains User model and related models
for managing user accounts and authentication.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg, F
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.hashers import make_password

from ..models import *
from ..enums import *
from ..utils import *
from ..validators import *


class AdvertiserUser(AbstractUser, AdvertiserPortalBaseModel):
    """
    Extended user model for advertiser portal users.

    This model extends Django's AbstractUser with additional
    fields specific to the advertiser portal.
    """

    # Fix reverse accessor clashes with the main User model
    groups = models.ManyToManyField(
        'auth.Group',
        blank=True,
        related_name='advertiser_portal_users',
        related_query_name='advertiser_portal_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        blank=True,
        related_name='advertiser_portal_users',
        related_query_name='advertiser_portal_user',
    )
    
    # Basic Information
    user_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text="Unique user identifier"
    )
    
    # Profile Information
    first_name = models.CharField(
        max_length=100,
        help_text="First name"
    )
    last_name = models.CharField(
        max_length=100,
        help_text="Last name"
    )
    display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Display name"
    )
    
    # Contact Information
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Phone number"
    )
    mobile_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Mobile number"
    )
    
    # Company Information
    job_title = models.CharField(
        max_length=100,
        blank=True,
        help_text="Job title"
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        help_text="Department"
    )
    
    # Account Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='users',
        help_text="Associated advertiser"
    )
    role = models.CharField(
        max_length=50,
        choices=[
            ('owner', 'Owner'),
            ('admin', 'Admin'),
            ('manager', 'Manager'),
            ('analyst', 'Analyst'),
            ('viewer', 'Viewer'),
            ('custom', 'Custom Role')
        ],
        default='viewer',
        help_text="User role"
    )
    
    # Permissions and Access
    permissions = models.JSONField(
        default=list,
        blank=True,
        help_text="Custom permissions list"
    )
    can_create_campaigns = models.BooleanField(
        default=False,
        help_text="Can create campaigns"
    )
    can_edit_campaigns = models.BooleanField(
        default=False,
        help_text="Can edit campaigns"
    )
    can_view_billing = models.BooleanField(
        default=False,
        help_text="Can view billing information"
    )
    can_manage_billing = models.BooleanField(
        default=False,
        help_text="Can manage billing"
    )
    can_manage_users = models.BooleanField(
        default=False,
        help_text="Can manage other users"
    )
    can_view_reports = models.BooleanField(
        default=True,
        help_text="Can view reports"
    )
    can_export_data = models.BooleanField(
        default=False,
        help_text="Can export data"
    )
    
    # Status and Verification
    is_active = models.BooleanField(
        default=True,
        help_text="Whether user account is active"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether user email is verified"
    )
    verification_token = models.CharField(
        max_length=255,
        blank=True,
        help_text="Email verification token"
    )
    verification_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When verification email was sent"
    )
    
    # Password Management
    password_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When password was last changed"
    )
    password_reset_token = models.CharField(
        max_length=255,
        blank=True,
        help_text="Password reset token"
    )
    password_reset_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When password reset email was sent"
    )
    must_change_password = models.BooleanField(
        default=False,
        help_text="Whether user must change password on next login"
    )
    
    # Two-Factor Authentication
    two_factor_enabled = models.BooleanField(
        default=False,
        help_text="Whether 2FA is enabled"
    )
    two_factor_secret = models.CharField(
        max_length=255,
        blank=True,
        help_text="2FA secret key"
    )
    backup_codes = models.JSONField(
        default=list,
        blank=True,
        help_text="2FA backup codes"
    )
    
    # Session Management
    last_login_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of last login"
    )
    last_login_device = models.CharField(
        max_length=255,
        blank=True,
        help_text="Device used for last login"
    )
    last_login_location = models.CharField(
        max_length=255,
        blank=True,
        help_text="Location of last login"
    )
    
    # Preferences
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        help_text="User timezone"
    )
    language = models.CharField(
        max_length=10,
        default='en',
        help_text="Preferred language"
    )
    date_format = models.CharField(
        max_length=20,
        choices=[
            ('mm/dd/yyyy', 'MM/DD/YYYY'),
            ('dd/mm/yyyy', 'DD/MM/YYYY'),
            ('yyyy-mm-dd', 'YYYY-MM-DD')
        ],
        default='mm/dd/yyyy',
        help_text="Date format preference"
    )
    time_format = models.CharField(
        max_length=10,
        choices=[
            ('12h', '12-hour'),
            ('24h', '24-hour')
        ],
        default='12h',
        help_text="Time format preference"
    )
    
    # Notification Preferences
    email_notifications = models.BooleanField(
        default=True,
        help_text="Receive email notifications"
    )
    sms_notifications = models.BooleanField(
        default=False,
        help_text="Receive SMS notifications"
    )
    push_notifications = models.BooleanField(
        default=True,
        help_text="Receive push notifications"
    )
    
    # API Access
    api_key = models.CharField(
        max_length=255,
        blank=True,
        unique=True,
        help_text="API key for programmatic access"
    )
    api_key_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="API key expiration"
    )
    api_last_used = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last API usage"
    )
    
    # Activity Tracking
    login_count = models.IntegerField(
        default=0,
        help_text="Number of logins"
    )
    failed_login_attempts = models.IntegerField(
        default=0,
        help_text="Number of failed login attempts"
    )
    last_failed_login = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last failed login attempt"
    )
    locked_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Account locked until this time"
    )
    
    class Meta:
        db_table = 'advertiser_users'
        verbose_name = 'Advertiser User'
        verbose_name_plural = 'Advertiser Users'
        indexes = [
            models.Index(fields=['advertiser', 'role']),
            models.Index(fields=['email']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_verified']),
            models.Index(fields=['last_login']),
            models.Index(fields=['api_key']),
        ]
    
    def __str__(self) -> str:
        return f"{self.display_name or self.get_full_name()} ({self.advertiser.company_name})"
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate email format
        if self.email:
            from django.core.validators import EmailValidator
            validator = EmailValidator()
            validator(self.email)
        
        # Validate phone format
        if self.phone_number:
            if not re.match(r'^\+?1?\d{9,15}$', self.phone_number.replace('-', '').replace(' ', '')):
                raise ValidationError("Invalid phone number format")
        
        # Validate role permissions
        if self.role == 'owner':
            # Owners should have all permissions
            self.can_create_campaigns = True
            self.can_edit_campaigns = True
            self.can_view_billing = True
            self.can_manage_billing = True
            self.can_manage_users = True
            self.can_view_reports = True
            self.can_export_data = True
        elif self.role == 'viewer':
            # Viewers should have minimal permissions
            self.can_create_campaigns = False
            self.can_edit_campaigns = False
            self.can_view_billing = False
            self.can_manage_billing = False
            self.can_manage_users = False
            self.can_view_reports = True
            self.can_export_data = False
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Generate display name if not set
        if not self.display_name:
            self.display_name = self.get_full_name() or self.username
        
        # Generate API key if not set
        if not self.api_key and self.can_export_data:
            self.api_key = self.generate_api_key()
        
        # Set verification token if email changed and not verified
        if self.email and not self.is_verified and not self.verification_token:
            self.verification_token = self.generate_verification_token()
        
        super().save(*args, **kwargs)
    
    def generate_api_key(self) -> str:
        """Generate unique API key."""
        import secrets
        prefix = "adv_api_"
        unique_id = secrets.token_urlsafe(32)
        return f"{prefix}{unique_id}"
    
    def generate_verification_token(self) -> str:
        """Generate email verification token."""
        import secrets
        return secrets.token_urlsafe(32)
    
    def generate_password_reset_token(self) -> str:
        """Generate password reset token."""
        import secrets
        return secrets.token_urlsafe(32)
    
    def is_locked(self) -> bool:
        """Check if account is locked."""
        if not self.locked_until:
            return False
        
        return timezone.now() < self.locked_until
    
    def lock_account(self, duration_hours: int = 24) -> None:
        """Lock account for specified duration."""
        self.locked_until = timezone.now() + timezone.timedelta(hours=duration_hours)
        self.save(update_fields=['locked_until'])
    
    def unlock_account(self) -> None:
        """Unlock account."""
        self.locked_until = None
        self.failed_login_attempts = 0
        self.save(update_fields=['locked_until', 'failed_login_attempts'])
    
    def record_login(self, ip_address: str, device: str = '', location: str = '') -> None:
        """Record successful login."""
        self.last_login = timezone.now()
        self.last_login_ip = ip_address
        self.last_login_device = device
        self.last_login_location = location
        self.login_count += 1
        self.failed_login_attempts = 0
        self.save(update_fields=[
            'last_login', 'last_login_ip', 'last_login_device',
            'last_login_location', 'login_count', 'failed_login_attempts'
        ])
    
    def record_failed_login(self) -> None:
        """Record failed login attempt."""
        self.failed_login_attempts += 1
        self.last_failed_login = timezone.now()
        
        # Lock account after too many failed attempts
        max_attempts = 5
        if self.failed_login_attempts >= max_attempts:
            self.lock_account()
        
        self.save(update_fields=['failed_login_attempts', 'last_failed_login', 'locked_until'])
    
    def verify_email(self) -> None:
        """Verify user email."""
        self.is_verified = True
        self.verification_token = ''
        self.save(update_fields=['is_verified', 'verification_token'])
    
    def send_verification_email(self) -> bool:
        """Send email verification."""
        try:
            # This would implement actual email sending
            self.verification_sent_at = timezone.now()
            self.save(update_fields=['verification_sent_at'])
            return True
        except Exception:
            return False
    
    def send_password_reset_email(self) -> bool:
        """Send password reset email."""
        try:
            self.password_reset_token = self.generate_password_reset_token()
            self.password_reset_sent_at = timezone.now()
            self.save(update_fields=['password_reset_token', 'password_reset_sent_at'])
            
            # This would implement actual email sending
            return True
        except Exception:
            return False
    
    def reset_password(self, new_password: str) -> bool:
        """Reset user password."""
        try:
            self.password = make_password(new_password)
            self.password_changed_at = timezone.now()
            self.password_reset_token = ''
            self.must_change_password = False
            self.save(update_fields=['password', 'password_changed_at', 'password_reset_token', 'must_change_password'])
            return True
        except Exception:
            return False
    
    def enable_two_factor(self) -> str:
        """Enable two-factor authentication."""
        import pyotp
        
        secret = pyotp.random_base32()
        self.two_factor_secret = secret
        self.backup_codes = [secrets.token_urlsafe(8) for _ in range(10)]
        self.save(update_fields=['two_factor_secret', 'backup_codes'])
        
        return secret
    
    def disable_two_factor(self) -> None:
        """Disable two-factor authentication."""
        self.two_factor_enabled = False
        self.two_factor_secret = ''
        self.backup_codes = []
        self.save(update_fields=['two_factor_enabled', 'two_factor_secret', 'backup_codes'])
    
    def verify_two_factor_token(self, token: str) -> bool:
        """Verify two-factor authentication token."""
        import pyotp
        
        if not self.two_factor_secret:
            return False
        
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.verify(token)
    
    def verify_backup_code(self, code: str) -> bool:
        """Verify backup code."""
        if not self.backup_codes:
            return False
        
        if code in self.backup_codes:
            self.backup_codes.remove(code)
            self.save(update_fields=['backup_codes'])
            return True
        
        return False
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission."""
        # Check role-based permissions
        role_permissions = {
            'owner': ['*'],
            'admin': ['campaign.create', 'campaign.edit', 'billing.view', 'billing.manage', 'users.manage', 'reports.view', 'data.export'],
            'manager': ['campaign.create', 'campaign.edit', 'billing.view', 'reports.view', 'data.export'],
            'analyst': ['campaign.view', 'reports.view', 'data.export'],
            'viewer': ['campaign.view', 'reports.view']
        }
        
        if self.role in role_permissions:
            permissions = role_permissions[self.role]
            if '*' in permissions:
                return True
            if permission in permissions:
                return True
        
        # Check custom permissions
        if permission in self.permissions:
            return True
        
        # Check explicit permission fields
        permission_map = {
            'campaign.create': self.can_create_campaigns,
            'campaign.edit': self.can_edit_campaigns,
            'billing.view': self.can_view_billing,
            'billing.manage': self.can_manage_billing,
            'users.manage': self.can_manage_users,
            'reports.view': self.can_view_reports,
            'data.export': self.can_export_data
        }
        
        return permission_map.get(permission, False)
    
    def get_accessible_campaigns(self) -> QuerySet:
        """Get campaigns user can access."""
        from .campaign_model import Campaign
        
        if self.has_permission('campaign.view'):
            return Campaign.objects.filter(advertiser=self.advertiser, is_deleted=False)
        
        return Campaign.objects.none()
    
    def get_user_summary(self) -> Dict[str, Any]:
        """Get user summary."""
        return {
            'basic_info': {
                'user_id': str(self.user_id),
                'username': self.username,
                'display_name': self.display_name,
                'email': self.email,
                'role': self.role,
                'job_title': self.job_title
            },
            'advertiser': {
                'id': str(self.advertiser.id),
                'company_name': self.advertiser.company_name
            },
            'permissions': {
                'custom_permissions': self.permissions,
                'can_create_campaigns': self.can_create_campaigns,
                'can_edit_campaigns': self.can_edit_campaigns,
                'can_view_billing': self.can_view_billing,
                'can_manage_billing': self.can_manage_billing,
                'can_manage_users': self.can_manage_users,
                'can_view_reports': self.can_view_reports,
                'can_export_data': self.can_export_data
            },
            'status': {
                'is_active': self.is_active,
                'is_verified': self.is_verified,
                'is_locked': self.is_locked(),
                'two_factor_enabled': self.two_factor_enabled
            },
            'activity': {
                'login_count': self.login_count,
                'failed_login_attempts': self.failed_login_attempts,
                'last_login': self.last_login.isoformat() if self.last_login else None,
                'last_login_ip': self.last_login_ip,
                'last_login_device': self.last_login_device,
                'last_login_location': self.last_login_location
            },
            'preferences': {
                'timezone': self.timezone,
                'language': self.language,
                'date_format': self.date_format,
                'time_format': self.time_format,
                'email_notifications': self.email_notifications,
                'sms_notifications': self.sms_notifications,
                'push_notifications': self.push_notifications
            },
            'api': {
                'api_key': self.api_key,
                'api_key_expires_at': self.api_key_expires_at.isoformat() if self.api_key_expires_at else None,
                'api_last_used': self.api_last_used.isoformat() if self.api_last_used else None
            }
        }


class UserSession(AdvertiserPortalBaseModel):
    """
    Model for tracking user sessions.
    """
    
    # Basic Information
    user = models.ForeignKey(
        AdvertiserUser,
        on_delete=models.CASCADE,
        related_name='sessions',
        help_text="Associated user"
    )
    session_key = models.CharField(
        max_length=255,
        unique=True,
        help_text="Session key"
    )
    
    # Session Information
    ip_address = models.GenericIPAddressField(
        help_text="IP address"
    )
    user_agent = models.TextField(
        help_text="User agent string"
    )
    device_type = models.CharField(
        max_length=50,
        choices=[
            ('desktop', 'Desktop'),
            ('mobile', 'Mobile'),
            ('tablet', 'Tablet'),
            ('unknown', 'Unknown')
        ],
        default='unknown',
        help_text="Device type"
    )
    browser = models.CharField(
        max_length=100,
        blank=True,
        help_text="Browser name"
    )
    operating_system = models.CharField(
        max_length=100,
        blank=True,
        help_text="Operating system"
    )
    
    # Location Information
    country = models.CharField(
        max_length=2,
        blank=True,
        help_text="Country code"
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City"
    )
    
    # Session Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether session is active"
    )
    expires_at = models.DateTimeField(
        help_text="Session expiration time"
    )
    
    # Activity Tracking
    last_activity = models.DateTimeField(
        help_text="Last activity timestamp"
    )
    page_views = models.IntegerField(
        default=0,
        help_text="Number of page views in session"
    )
    
    class Meta:
        db_table = 'user_sessions'
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['ip_address']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self) -> str:
        return f"Session for {self.user.username}"
    
    def is_expired(self) -> bool:
        """Check if session is expired."""
        return timezone.now() > self.expires_at
    
    def extend_session(self, duration_hours: int = 24) -> None:
        """Extend session expiration."""
        self.expires_at = timezone.now() + timezone.timedelta(hours=duration_hours)
        self.last_activity = timezone.now()
        self.save(update_fields=['expires_at', 'last_activity'])
    
    def end_session(self) -> None:
        """End session."""
        self.is_active = False
        self.save(update_fields=['is_active'])


class UserActivityLog(AdvertiserPortalBaseModel):
    """
    Model for logging user activities.
    """
    
    # Basic Information
    user = models.ForeignKey(
        AdvertiserUser,
        on_delete=models.CASCADE,
        related_name='activity_logs',
        help_text="Associated user"
    )
    
    # Activity Details
    activity_type = models.CharField(
        max_length=50,
        choices=[
            ('login', 'Login'),
            ('logout', 'Logout'),
            ('create', 'Create'),
            ('update', 'Update'),
            ('delete', 'Delete'),
            ('view', 'View'),
            ('export', 'Export'),
            ('import', 'Import'),
            ('api_call', 'API Call'),
            ('password_change', 'Password Change'),
            ('permission_change', 'Permission Change')
        ],
        db_index=True,
        help_text="Type of activity"
    )
    
    # Object Information
    object_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Type of object acted upon"
    )
    object_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="ID of object acted upon"
    )
    object_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Name of object acted upon"
    )
    
    # Activity Details
    description = models.TextField(
        help_text="Activity description"
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional activity details"
    )
    
    # Context Information
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string"
    )
    session_key = models.CharField(
        max_length=255,
        blank=True,
        help_text="Session key"
    )
    
    # Result Information
    success = models.BooleanField(
        default=True,
        help_text="Whether activity was successful"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if activity failed"
    )
    
    class Meta:
        db_table = 'user_activity_logs'
        verbose_name = 'User Activity Log'
        verbose_name_plural = 'User Activity Logs'
        indexes = [
            models.Index(fields=['user', 'activity_type']),
            models.Index(fields=['object_type', 'object_id']),
            models.Index(fields=['created_at']),
            models.Index(fields=['success']),
        ]
    
    def __str__(self) -> str:
        return f"{self.activity_type} - {self.user.username}"
