"""
Base Models for Advertiser Portal

This module contains base model classes and mixins that are used
across the advertiser portal application.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from typing import Optional, Dict, Any, List
import uuid


class TimeStampedModel(models.Model):
    """
    Abstract base model with created_at and updated_at fields.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """
    Abstract base model with soft delete functionality.
    """
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_deleted'
    )

    class Meta:
        abstract = True

    def soft_delete(self, user: Optional[get_user_model()] = None) -> None:
        """Soft delete the instance."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save()

    def restore(self) -> None:
        """Restore the soft deleted instance."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save()


class UUIDModel(models.Model):
    """
    Abstract base model with UUID primary key.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class AdvertiserPortalBaseModel(TimeStampedModel, SoftDeleteModel, UUIDModel):
    """
    Base model for all Advertiser Portal models.
    Combines timestamp tracking, soft delete, and UUID primary key.
    """
    class Meta:
        abstract = True


class StatusModel(models.Model):
    """
    Abstract model with status field and common status choices.
    """
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('suspended', 'Suspended'),
        ('archived', 'Archived'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True)

    class Meta:
        abstract = True


class AuditModel(models.Model):
    """
    Abstract model for tracking creation and modification.
    """
    created_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created'
    )
    modified_by = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_modified'
    )

    class Meta:
        abstract = True


class ConfigurationModel(models.Model):
    """
    Abstract model for configuration data with JSON field.
    """
    configuration = models.JSONField(
        default=dict,
        blank=True,
        help_text="Configuration data in JSON format"
    )

    class Meta:
        abstract = True

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key."""
        return self.configuration.get(key, default)

    def set_config_value(self, key: str, value: Any) -> None:
        """Set configuration value by key."""
        if self.configuration is None:
            self.configuration = {}
        self.configuration[key] = value
        self.save(update_fields=['configuration'])

    def update_config(self, config_dict: Dict[str, Any]) -> None:
        """Update multiple configuration values."""
        if self.configuration is None:
            self.configuration = {}
        self.configuration.update(config_dict)
        self.save(update_fields=['configuration'])


class APIKeyModel(models.Model):
    """
    Abstract model for API key management.
    """
    api_key = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="API key for authentication")
    api_key_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="API key expiration date"
    )
    last_api_access = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last API access timestamp"
    )

    class Meta:
        abstract = True

    def is_api_key_valid(self) -> bool:
        """Check if API key is valid and not expired."""
        if not self.api_key:
            return False
        if self.api_key_expires_at and self.api_key_expires_at < timezone.now():
            return False
        return True

    def update_last_api_access(self) -> None:
        """Update the last API access timestamp."""
        self.last_api_access = timezone.now()
        self.save(update_fields=['last_api_access'])


class BudgetModel(models.Model):
    """
    Abstract model for budget management.
    """
    daily_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Daily budget limit")
    total_budget = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Total budget limit")
    current_spend = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Current amount spent")

    class Meta:
        abstract = True

    @property
    def remaining_budget(self) -> float:
        """Calculate remaining budget."""
        return float(self.total_budget - self.current_spend)

    @property
    def budget_utilization(self) -> float:
        """Calculate budget utilization percentage."""
        if self.total_budget == 0:
            return 0.0
        return float((self.current_spend / self.total_budget) * 100)

    def can_spend(self, amount: float) -> bool:
        """Check if spending amount is within budget."""
        return (self.current_spend + amount) <= self.total_budget

    def add_spend(self, amount: float) -> bool:
        """Add spend amount if within budget."""
        if self.can_spend(amount):
            self.current_spend += amount
            self.save(update_fields=['current_spend'])
            return True
        return False


class GeoModel(models.Model):
    """
    Abstract model for geographic targeting.
    """
    countries = models.JSONField(
        default=list,
        blank=True,
        help_text="List of country codes for targeting"
    )
    regions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of regions/states for targeting"
    )
    cities = models.JSONField(
        default=list,
        blank=True,
        help_text="List of cities for targeting"
    )
    postal_codes = models.JSONField(
        default=list,
        blank=True,
        help_text="List of postal codes for targeting"
    )
    geo_coordinates = models.JSONField(
        default=list,
        blank=True,
        help_text="List of latitude/longitude coordinates"
    )
    radius = models.IntegerField(
        null=True,
        blank=True,
        help_text="Radius in kilometers for coordinate targeting"
    )

    class Meta:
        abstract = True


class TrackingModel(models.Model):
    """
    Abstract model for tracking and analytics.
    """
    impressions = models.BigIntegerField(default=0, help_text="Total impressions")
    clicks = models.BigIntegerField(default=0, help_text="Total clicks")
    conversions = models.BigIntegerField(default=0, help_text="Total conversions")
    cost = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Total cost")
    revenue = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text="Total revenue")

    class Meta:
        abstract = True

    @property
    def ctr(self) -> float:
        """Calculate Click-Through Rate."""
        if self.impressions == 0:
            return 0.0
        return float((self.clicks / self.impressions) * 100)

    @property
    def conversion_rate(self) -> float:
        """Calculate Conversion Rate."""
        if self.clicks == 0:
            return 0.0
        return float((self.conversions / self.clicks) * 100)

    @property
    def cpc(self) -> float:
        """Calculate Cost Per Click."""
        if self.clicks == 0:
            return 0.0
        return float(self.cost / self.clicks)

    @property
    def cpm(self) -> float:
        """Calculate Cost Per Mille (Cost per 1000 impressions)."""
        if self.impressions == 0:
            return 0.0
        return float((self.cost / self.impressions) * 1000)

    @property
    def cpa(self) -> float:
        """Calculate Cost Per Action/Conversion."""
        if self.conversions == 0:
            return 0.0
        return float(self.cost / self.conversions)

    @property
    def roas(self) -> float:
        """Calculate Return on Ad Spend."""
        if self.cost == 0:
            return 0.0
        return float(self.revenue / self.cost)

    @property
    def roi(self) -> float:
        """Calculate Return on Investment."""
        if self.cost == 0:
            return 0.0
        return float(((self.revenue - self.cost) / self.cost) * 100)
