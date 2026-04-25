# earning_backend/api/notifications/abstracts.py
"""
Abstract Base Models — Reusable abstract Django model mixins.

Every concrete model in the notification system inherits from one or more
of these abstract base classes to get common fields and behaviour without
code duplication.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

User = get_user_model()


# ---------------------------------------------------------------------------
# Timestamp mixin
# ---------------------------------------------------------------------------

class TimeStampedModel(models.Model):
    """
    Abstract base that adds created_at and updated_at to every model.
    All notification models inherit this.
    """
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']

    @property
    def age_seconds(self) -> float:
        """Return age of the record in seconds."""
        return (timezone.now() - self.created_at).total_seconds()

    @property
    def is_recent(self) -> bool:
        """True if record was created within the last hour."""
        return self.age_seconds < 3600


# ---------------------------------------------------------------------------
# UUID primary key mixin
# ---------------------------------------------------------------------------

class UUIDModel(models.Model):
    """
    Abstract base that uses UUID as the primary key instead of auto-int.
    Use for externally exposed resources where sequential IDs are undesirable.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Soft-delete mixin
# ---------------------------------------------------------------------------

class SoftDeleteModel(models.Model):
    """
    Abstract base that adds soft-delete support.
    Records are never hard-deleted — is_deleted=True hides them from queries.
    Use with SoftDeleteManager for transparent filtering.
    """
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='%(class)s_deleted',
    )

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, deleted_by=None):
        """Soft-delete: mark as deleted instead of removing from DB."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if deleted_by:
            self.deleted_by = deleted_by
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'updated_at'])

    def hard_delete(self):
        """Permanently remove from database."""
        super().delete()

    def restore(self):
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by', 'updated_at'])

    @classmethod
    def delete_expired(cls, days: int = 90) -> dict:
        """
        Hard-delete all soft-deleted records older than `days` days.
        Called by cleanup_tasks.py.
        """
        cutoff = timezone.now() - timezone.timedelta(days=days)
        qs = cls.objects.filter(is_deleted=True, deleted_at__lt=cutoff)
        count = qs.count()
        qs.delete()
        return {'deleted': count, 'model': cls.__name__}


# ---------------------------------------------------------------------------
# Owner / user ownership mixin
# ---------------------------------------------------------------------------

class OwnedModel(models.Model):
    """
    Abstract base for models that belong to a specific user.
    Provides ownership filtering helpers.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='%(class)s_owned',
        db_index=True,
    )

    class Meta:
        abstract = True

    @classmethod
    def for_user(cls, user):
        """Return queryset filtered to the given user."""
        return cls.objects.filter(user=user)

    def is_owned_by(self, user) -> bool:
        return self.user_id == user.pk


# ---------------------------------------------------------------------------
# Created-by audit mixin
# ---------------------------------------------------------------------------

class AuditedModel(models.Model):
    """
    Abstract base that tracks who created and last updated a record.
    """
    created_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='%(class)s_created',
    )
    updated_by = models.ForeignKey(
        User,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='%(class)s_updated',
    )

    class Meta:
        abstract = True

    def save_with_user(self, user, *args, **kwargs):
        """Save the model and record the user who made the change."""
        if not self.pk:
            self.created_by = user
        self.updated_by = user
        self.save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Status machine mixin
# ---------------------------------------------------------------------------

class StatusModel(models.Model):
    """
    Abstract base that adds a status field with transition tracking.
    Subclasses define STATUS_CHOICES and valid transitions.
    """
    status = models.CharField(max_length=30, db_index=True)
    status_changed_at = models.DateTimeField(null=True, blank=True)

    # Subclasses define: VALID_TRANSITIONS = {'draft': ['scheduled', 'cancelled'], ...}
    VALID_TRANSITIONS: dict = {}

    class Meta:
        abstract = True

    def transition_to(self, new_status: str, save: bool = True) -> bool:
        """
        Attempt to transition to new_status.
        Returns True on success, False if transition is invalid.
        """
        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            return False
        self.status = new_status
        self.status_changed_at = timezone.now()
        if save:
            self.save(update_fields=['status', 'status_changed_at', 'updated_at'])
        return True

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self.VALID_TRANSITIONS.get(self.status, [])


# ---------------------------------------------------------------------------
# Metadata / extra data mixin
# ---------------------------------------------------------------------------

class MetadataModel(models.Model):
    """
    Abstract base that adds a JSON metadata field for arbitrary extra data.
    Use to avoid schema migrations for minor data additions.
    """
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True

    def get_meta(self, key: str, default=None):
        return self.metadata.get(key, default)

    def set_meta(self, key: str, value, save: bool = False):
        self.metadata[key] = value
        if save:
            self.save(update_fields=['metadata', 'updated_at'])

    def update_meta(self, data: dict, save: bool = False):
        self.metadata.update(data)
        if save:
            self.save(update_fields=['metadata', 'updated_at'])


# ---------------------------------------------------------------------------
# Taggable mixin
# ---------------------------------------------------------------------------

class TaggableModel(models.Model):
    """
    Abstract base that adds a tags JSON array field.
    """
    tags = models.JSONField(default=list, blank=True)

    class Meta:
        abstract = True

    def add_tag(self, tag: str, save: bool = False):
        if tag not in self.tags:
            self.tags.append(tag)
            if save:
                self.save(update_fields=['tags', 'updated_at'])

    def remove_tag(self, tag: str, save: bool = False):
        self.tags = [t for t in self.tags if t != tag]
        if save:
            self.save(update_fields=['tags', 'updated_at'])

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags


# ---------------------------------------------------------------------------
# Priority mixin
# ---------------------------------------------------------------------------

class PriorityModel(models.Model):
    """
    Abstract base that adds priority field with helpers.
    """
    from .choices import PRIORITY_CHOICES, PRIORITY_SCORE

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default='medium',
        db_index=True,
    )

    class Meta:
        abstract = True

    @property
    def priority_score(self) -> int:
        from .choices import PRIORITY_SCORE
        return PRIORITY_SCORE.get(self.priority, 5)

    def is_high_priority(self) -> bool:
        return self.priority_score >= 7

    def is_critical(self) -> bool:
        return self.priority == 'critical'


# ---------------------------------------------------------------------------
# Schedulable mixin
# ---------------------------------------------------------------------------

class SchedulableModel(models.Model):
    """
    Abstract base for models that can be scheduled for future execution.
    """
    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    @property
    def is_scheduled(self) -> bool:
        return self.scheduled_at is not None

    @property
    def is_overdue(self) -> bool:
        if not self.scheduled_at:
            return False
        return timezone.now() > self.scheduled_at and not self.executed_at

    @property
    def is_due(self) -> bool:
        if not self.scheduled_at:
            return False
        return timezone.now() >= self.scheduled_at and not self.executed_at


# ---------------------------------------------------------------------------
# Channel-aware mixin
# ---------------------------------------------------------------------------

class ChannelModel(models.Model):
    """
    Abstract base for models tied to a specific notification channel.
    """
    from .choices import CHANNEL_CHOICES

    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default='in_app',
        db_index=True,
    )

    class Meta:
        abstract = True

    def is_push_channel(self) -> bool:
        return self.channel in ('push', 'browser')

    def is_messaging_channel(self) -> bool:
        return self.channel in ('sms', 'whatsapp', 'telegram')

    def is_email_channel(self) -> bool:
        return self.channel == 'email'

    def is_social_channel(self) -> bool:
        return self.channel in ('slack', 'discord')


# ---------------------------------------------------------------------------
# Retry-able mixin
# ---------------------------------------------------------------------------

class RetryableModel(models.Model):
    """
    Abstract base for models that support retry logic.
    """
    retry_count = models.PositiveSmallIntegerField(default=0)
    max_retries = models.PositiveSmallIntegerField(default=3)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        abstract = True

    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries

    def record_retry(self, error: str = '', save: bool = True):
        self.retry_count += 1
        self.last_retry_at = timezone.now()
        self.last_error = error
        if save:
            self.save(update_fields=[
                'retry_count', 'last_retry_at', 'last_error', 'updated_at'
            ])

    def reset_retries(self, save: bool = True):
        self.retry_count = 0
        self.last_retry_at = None
        self.last_error = ''
        if save:
            self.save(update_fields=[
                'retry_count', 'last_retry_at', 'last_error', 'updated_at'
            ])

    @property
    def has_exceeded_retries(self) -> bool:
        return self.retry_count >= self.max_retries


# ---------------------------------------------------------------------------
# Base Notification Model (combines all mixins)
# ---------------------------------------------------------------------------

class BaseNotificationModel(
    TimeStampedModel,
    SoftDeleteModel,
    MetadataModel,
    TaggableModel,
):
    """
    Full-featured abstract base for notification-related models.
    Combine: timestamps + soft-delete + metadata + tags.
    """

    class Meta:
        abstract = True
        ordering = ['-created_at']
