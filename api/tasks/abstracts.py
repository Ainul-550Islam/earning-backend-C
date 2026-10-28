"""
api/tasks/abstracts.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Abstract base classes and mixins for models, serializers,
views, and services in the task system.
All concrete classes should inherit from these.
"""

import uuid
import logging
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# ABSTRACT MODELS
# ══════════════════════════════════════════════════════════════════════════════

class TimestampedModel(models.Model):
    """
    Abstract model that adds created_at / updated_at timestamps.
    Inherit from this for any model that needs audit timestamps.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @property
    def age_seconds(self) -> float:
        return (timezone.now() - self.created_at).total_seconds()

    @property
    def age_hours(self) -> float:
        return self.age_seconds / 3600

    @property
    def age_days(self) -> int:
        return int(self.age_seconds / 86400)


class UUIDPrimaryKeyModel(models.Model):
    """
    Abstract model with a UUID primary key.
    Use for models where auto-increment IDs are not desired
    (e.g., transaction records, session IDs).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class SoftDeleteModel(models.Model):
    """
    Abstract model with soft-delete support.
    Records are never physically deleted; just flagged as deleted.
    """
    is_deleted      = models.BooleanField(default=False, db_index=True)
    deleted_at      = models.DateTimeField(null=True, blank=True)
    deleted_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        abstract = True

    def soft_delete(self, deleted_by=None):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = deleted_by
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])

    objects = models.Manager()  # includes deleted

    class ActiveManager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().filter(is_deleted=False)

    active_objects = ActiveManager()


class AuditedModel(TimestampedModel):
    """
    Abstract model with full audit trail:
    created_at, updated_at, created_by, updated_by.
    """
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='%(class)s_created',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='%(class)s_updated',
    )

    class Meta:
        abstract = True

    def save_with_user(self, user, **kwargs):
        if not self.pk:
            self.created_by = user
        self.updated_by = user
        self.save(**kwargs)


class MonetaryModel(models.Model):
    """
    Abstract model for anything involving money.
    Enforces Decimal storage and currency tracking.
    """
    amount   = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0'))
    currency = models.CharField(max_length=10, default='USD')

    class Meta:
        abstract = True

    @property
    def amount_display(self) -> str:
        return f"{self.currency} {self.amount:.4f}"

    def is_positive(self) -> bool:
        return self.amount > Decimal('0')

    def is_zero(self) -> bool:
        return self.amount == Decimal('0')


class StatusTrackingModel(TimestampedModel):
    """
    Abstract model that tracks status transitions with timestamps.
    Subclasses define their own status choices.
    """
    status     = models.CharField(max_length=30, db_index=True)
    status_at  = models.DateTimeField(default=timezone.now)
    status_log = models.JSONField(default=list, blank=True)

    class Meta:
        abstract = True

    def transition_to(self, new_status: str, notes: str = '',
                      save: bool = True) -> None:
        old_status    = self.status
        self.status   = new_status
        self.status_at = timezone.now()
        log_entry = {
            'from':  old_status,
            'to':    new_status,
            'at':    self.status_at.isoformat(),
            'notes': notes,
        }
        self.status_log = (self.status_log or []) + [log_entry]
        if save:
            self.save(update_fields=['status', 'status_at', 'status_log'])

    @property
    def status_duration_seconds(self) -> float:
        return (timezone.now() - self.status_at).total_seconds()


class GeoTargetedModel(models.Model):
    """
    Abstract model for resources with geographic targeting.
    Used by offers, campaigns, tasks, lockers.
    """
    target_countries = models.JSONField(
        default=list, blank=True,
        help_text='Empty list = all countries allowed',
    )
    target_devices = models.JSONField(
        default=list, blank=True,
        help_text='Empty list = all devices allowed',
    )
    target_os_types = models.JSONField(
        default=list, blank=True,
        help_text='Empty list = all OS types allowed',
    )
    geo_tier = models.CharField(
        max_length=20, default='all',
        help_text='tier_1, tier_2, tier_3, or all',
    )

    class Meta:
        abstract = True

    def is_eligible_for(self, country: str = None, device: str = None,
                        os_type: str = None) -> bool:
        if country and self.target_countries:
            if country not in self.target_countries:
                return False
        if device and self.target_devices:
            if device not in self.target_devices:
                return False
        if os_type and self.target_os_types:
            if os_type not in self.target_os_types:
                return False
        return True


class CapLimitedModel(models.Model):
    """
    Abstract model for resources with daily/total caps.
    Used by offers, campaigns, ad units.
    """
    daily_cap           = models.PositiveIntegerField(null=True, blank=True)
    total_cap           = models.PositiveIntegerField(null=True, blank=True)
    budget              = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    daily_clicks_used   = models.PositiveIntegerField(default=0)
    total_clicks_used   = models.PositiveIntegerField(default=0)
    total_spend         = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0'))

    class Meta:
        abstract = True

    @property
    def is_daily_capped(self) -> bool:
        return bool(self.daily_cap and self.daily_clicks_used >= self.daily_cap)

    @property
    def is_total_capped(self) -> bool:
        return bool(self.total_cap and self.total_clicks_used >= self.total_cap)

    @property
    def is_budget_exhausted(self) -> bool:
        return bool(self.budget and self.total_spend >= self.budget)

    @property
    def is_capped(self) -> bool:
        return self.is_daily_capped or self.is_total_capped or self.is_budget_exhausted

    def daily_cap_pct(self) -> float:
        if not self.daily_cap:
            return 0.0
        return round(self.daily_clicks_used / self.daily_cap * 100, 1)


class PublishableModel(models.Model):
    """
    Abstract model for items that go through a publish workflow.
    draft → review → approved/published → archived
    """
    DRAFT     = 'draft'
    REVIEW    = 'review'
    APPROVED  = 'approved'
    PUBLISHED = 'published'
    ARCHIVED  = 'archived'
    REJECTED  = 'rejected'

    PUBLISH_STATUS_CHOICES = [
        (DRAFT,     'Draft'),
        (REVIEW,    'Pending Review'),
        (APPROVED,  'Approved'),
        (PUBLISHED, 'Published'),
        (ARCHIVED,  'Archived'),
        (REJECTED,  'Rejected'),
    ]

    publish_status = models.CharField(
        max_length=20, choices=PUBLISH_STATUS_CHOICES,
        default=DRAFT, db_index=True,
    )
    published_at   = models.DateTimeField(null=True, blank=True)
    reviewed_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )

    class Meta:
        abstract = True

    def publish(self, reviewer=None):
        self.publish_status = self.PUBLISHED
        self.published_at   = timezone.now()
        self.reviewed_by    = reviewer
        self.save(update_fields=['publish_status', 'published_at', 'reviewed_by'])

    def unpublish(self):
        self.publish_status = self.DRAFT
        self.save(update_fields=['publish_status'])

    def archive(self):
        self.publish_status = self.ARCHIVED
        self.save(update_fields=['publish_status'])

    def reject(self, reviewer=None):
        self.publish_status = self.REJECTED
        self.reviewed_by    = reviewer
        self.save(update_fields=['publish_status', 'reviewed_by'])

    @property
    def is_published(self) -> bool:
        return self.publish_status == self.PUBLISHED

    @property
    def is_live(self) -> bool:
        return self.publish_status in (self.APPROVED, self.PUBLISHED)


# ══════════════════════════════════════════════════════════════════════════════
# ABSTRACT SERIALIZERS
# ══════════════════════════════════════════════════════════════════════════════

class TimestampedSerializer(serializers.ModelSerializer):
    """
    Base serializer with read-only created_at / updated_at fields.
    """
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class MonetarySerializer(serializers.ModelSerializer):
    """
    Base serializer that formats Decimal amounts as strings.
    """
    amount = serializers.DecimalField(max_digits=18, decimal_places=8, coerce_to_string=True)


class TaskStatsSerializer(serializers.Serializer):
    """
    Common schema for task statistics responses.
    """
    total       = serializers.IntegerField(default=0)
    success     = serializers.IntegerField(default=0)
    failed      = serializers.IntegerField(default=0)
    pending     = serializers.IntegerField(default=0)
    avg_duration = serializers.FloatField(default=0.0)
    success_rate = serializers.FloatField(default=100.0)
    period      = serializers.CharField(default='24h')
    timestamp   = serializers.DateTimeField(default=timezone.now)


class PaginatedResponseSerializer(serializers.Serializer):
    """
    Standard paginated response envelope.
    """
    count    = serializers.IntegerField()
    next     = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results  = serializers.ListField()


# ══════════════════════════════════════════════════════════════════════════════
# ABSTRACT SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class BaseTaskService:
    """
    Abstract base class for all task system services.
    Provides common logging, error handling, and EventBus integration.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__module__)
        self._cache = None

    def _emit_event(self, event: str, payload: dict) -> None:
        """Emit an EventBus event, ignoring failures."""
        try:
            from api.tasks.integration.event_bus import EventBus
            EventBus.emit(event, payload, async_dispatch=True)
        except Exception as e:
            self.logger.debug(f"[SERVICE EVENT] {event}: {e}")

    def _sync_to_bridge(self, key: str, value, ttl: int = 3600) -> None:
        """Sync data to DataBridge, ignoring failures."""
        try:
            from api.tasks.integration.data_bridge import DataBridge
            DataBridge.set(key, value, ttl=ttl)
        except Exception as e:
            self.logger.debug(f"[DATA BRIDGE] {key}: {e}")

    def _success(self, **kwargs) -> dict:
        return {'status': 'success', 'timestamp': timezone.now().isoformat(), **kwargs}

    def _error(self, message: str, code: str = 'error', **kwargs) -> dict:
        return {'status': 'error', 'error': code, 'message': message,
                'timestamp': timezone.now().isoformat(), **kwargs}

    def _skipped(self, reason: str, **kwargs) -> dict:
        return {'status': 'skipped', 'reason': reason,
                'timestamp': timezone.now().isoformat(), **kwargs}


# ══════════════════════════════════════════════════════════════════════════════
# ABSTRACT CELERY TASK BASE
# ══════════════════════════════════════════════════════════════════════════════

class BaseTaskResult:
    """
    Standard return value structure for all Celery tasks.
    All task functions should return instances compatible with this schema.
    """
    def __init__(self, status: str = 'success', message: str = '',
                 **extra):
        self.status    = status
        self.message   = message
        self.timestamp = timezone.now().isoformat()
        self.extra     = extra

    def to_dict(self) -> dict:
        return {
            'status':    self.status,
            'message':   self.message,
            'timestamp': self.timestamp,
            **self.extra,
        }

    @classmethod
    def success(cls, **kwargs) -> dict:
        return cls(status='success', **kwargs).to_dict()

    @classmethod
    def failure(cls, error: str = '', **kwargs) -> dict:
        return cls(status='failure', message=error, **kwargs).to_dict()

    @classmethod
    def skipped(cls, reason: str = '', **kwargs) -> dict:
        return cls(status='skipped', message=reason, **kwargs).to_dict()

    @classmethod
    def duplicate(cls, **kwargs) -> dict:
        return cls(status='duplicate', **kwargs).to_dict()

    @classmethod
    def fraud_detected(cls, score: int = 0, **kwargs) -> dict:
        return cls(status='fraud_detected', fraud_score=score, **kwargs).to_dict()


__all__ = [
    'TimestampedModel', 'UUIDPrimaryKeyModel', 'SoftDeleteModel',
    'AuditedModel', 'MonetaryModel', 'StatusTrackingModel',
    'GeoTargetedModel', 'CapLimitedModel', 'PublishableModel',
    'TimestampedSerializer', 'MonetarySerializer',
    'TaskStatsSerializer', 'PaginatedResponseSerializer',
    'BaseTaskService', 'BaseTaskResult',
]
