"""
tasks/models/tenant_model.py
Enhanced tenant model for SaaS multi-tenancy
"""
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import json

class Tenant(models.Model):
    """
    Enhanced tenant model for SaaS multi-tenancy
    """
    
    class SubscriptionPlan(models.TextChoices):
        BASIC = 'basic', 'Basic Plan'
        PRO = 'pro', 'Professional Plan'
        ENTERPRISE = 'enterprise', 'Enterprise Plan'
    
    class TenantStatus(models.TextChoices):
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'
        TRIAL = 'trial', 'Trial'
        CANCELLED = 'cancelled', 'Cancelled'
    
    # Basic Information
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    domain = models.CharField(max_length=255, unique=True)
    
    # Subscription & Billing
    subscription_plan = models.CharField(
        max_length=20,
        choices=SubscriptionPlan.choices,
        default=SubscriptionPlan.BASIC
    )
    subscription_expires_at = models.DateTimeField(null=True, blank=True)
    is_trial = models.BooleanField(default=False)
    
    # Resource Limits
    max_users = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(1), MaxValueValidator(100000)]
    )
    max_storage_gb = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(10000)]
    )
    max_api_requests_per_hour = models.PositiveIntegerField(
        default=1000,
        validators=[MinValueValidator(10), MaxValueValidator(100000)]
    )
    max_concurrent_tasks = models.PositiveIntegerField(
        default=50,
        validators=[MinValueValidator(1), MaxValueValidator(10000)]
    )
    
    # Features & Configuration
    features = models.JSONField(default=dict)
    settings = models.JSONField(default=dict)
    ui_config = models.JSONField(default=dict)
    
    # Status & Metadata
    status = models.CharField(
        max_length=20,
        choices=TenantStatus.choices,
        default=TenantStatus.ACTIVE
    )
    is_active = models.BooleanField(default=True)
    is_suspended = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'tenants'
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['domain']),
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['subscription_expires_at']),
        ]
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def is_expired(self) -> bool:
        """Check if tenant subscription has expired."""
        if not self.subscription_expires_at:
            return False
        return timezone.now() > self.subscription_expires_at
    
    @property
    def user_count(self) -> int:
        """Get current user count for this tenant."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.filter(tenant_id=self.id).count()
    
    @property
    def storage_usage_percent(self) -> float:
        """Calculate storage usage percentage."""
        if self.max_storage_gb == 0:
            return 0.0
        return (self.current_storage_gb / self.max_storage_gb) * 100
    
    @property
    def current_storage_gb(self) -> float:
        """Get current storage usage (placeholder - implement actual calculation)."""
        # This would be calculated from actual usage data
        return 0.0
    
    def get_resource_usage(self) -> dict:
        """Get comprehensive resource usage for tenant."""
        return {
            'users': {
                'current': self.user_count,
                'max': self.max_users,
                'percentage': (self.user_count / self.max_users) * 100 if self.max_users > 0 else 0
            },
            'storage': {
                'current_gb': self.current_storage_gb,
                'max_gb': self.max_storage_gb,
                'percentage': self.storage_usage_percent
            },
            'api': {
                'current_requests_per_hour': self.current_api_requests_per_hour,
                'max_requests_per_hour': self.max_api_requests_per_hour,
                'percentage': (self.current_api_requests_per_hour / self.max_api_requests_per_hour) * 100 if self.max_api_requests_per_hour > 0 else 0
            },
            'tasks': {
                'current_concurrent': self.current_concurrent_tasks,
                'max_concurrent': self.max_concurrent_tasks,
                'percentage': (self.current_concurrent_tasks / self.max_concurrent_tasks) * 100 if self.max_concurrent_tasks > 0 else 0
            }
        }
    
    @property
    def current_api_requests_per_hour(self) -> int:
        """Get current API requests per hour (placeholder - implement actual tracking)."""
        # This would be calculated from actual usage data
        return 0
    
    @property
    def current_concurrent_tasks(self) -> int:
        """Get current concurrent tasks (placeholder - implement actual tracking)."""
        # This would be calculated from actual task data
        return 0
    
    def can_add_user(self) -> bool:
        """Check if tenant can add more users."""
        return self.user_count < self.max_users and self.is_active and not self.is_expired
    
    def can_create_task(self) -> bool:
        """Check if tenant can create more tasks."""
        return self.current_concurrent_tasks < self.max_concurrent_tasks and self.is_active and not self.is_expired
    
    def get_feature_flags(self) -> dict:
        """Get feature flags for this tenant."""
        default_features = {
            'custom_branding': False,
            'custom_domain': False,
            'white_labeling': False,
            'advanced_analytics': False,
            'api_access': True,
            'task_management': True,
            'user_management': True,
        }
        
        # Override with tenant-specific features
        tenant_features = self.features or {}
        
        return {
            **default_features,
            **tenant_features
        }
    
    def enforce_resource_limits(self) -> dict:
        """Get resource limits for enforcement."""
        return {
            'max_users': self.max_users,
            'max_storage_gb': self.max_storage_gb,
            'max_api_requests_per_hour': self.max_api_requests_per_hour,
            'max_concurrent_tasks': self.max_concurrent_tasks,
            'subscription_plan': self.subscription_plan,
            'is_trial': self.is_trial,
            'expires_at': self.subscription_expires_at,
        }
