"""
tenants/models.py
Tenant models for multi-tenant SaaS architecture
"""
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
import json

User = get_user_model()


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
        return User.objects.filter(tenant_id=self.id).count()
    
    def get_resource_usage(self) -> dict:
        """Get comprehensive resource usage for tenant."""
        return {
            'users': {
                'current': self.user_count,
                'max': self.max_users,
                'percentage': (self.user_count / self.max_users) * 100 if self.max_users > 0 else 0
            },
            'storage': {
                'current_gb': 0.0,  # Placeholder
                'max_gb': self.max_storage_gb,
                'percentage': 0.0
            },
            'api': {
                'current_requests_per_hour': 0,  # Placeholder
                'max_requests_per_hour': self.max_api_requests_per_hour,
                'percentage': 0.0
            },
            'tasks': {
                'current_concurrent': 0,  # Placeholder
                'max_concurrent': self.max_concurrent_tasks,
                'percentage': 0.0
            }
        }
    
    def can_add_user(self) -> bool:
        """Check if tenant can add more users."""
        return self.user_count < self.max_users and self.is_active and not self.is_expired
    
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
        
        tenant_features = self.features or {}
        return {**default_features, **tenant_features}
