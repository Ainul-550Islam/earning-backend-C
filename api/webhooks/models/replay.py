"""
Replay Models for Webhooks System

This module contains models for webhook replay functionality
allowing to resend specific events or event ranges.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

from .constants import (
    ReplayStatus
)

User = get_user_model()


class WebhookReplay(models.Model):
    """
    Individual webhook replay operations.
    Tracks replay of specific webhook events.
    """
    
    original_log = models.ForeignKey(
        'WebhookDeliveryLog',
        on_delete=models.CASCADE,
        related_name='replays',
        verbose_name=_('Original Log'),
    )
    replayed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replayed_webhooks',
        verbose_name=_('Replayed By'),
    )
    new_log = models.ForeignKey(
        'WebhookDeliveryLog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replay_source',
        verbose_name=_('New Log'),
    )
    reason = models.TextField(
        verbose_name=_('Reason'),
        help_text=_('Reason for replay (debug, error recovery, etc.)')
    )
    status = models.CharField(
        max_length=20,
        choices=ReplayStatus.choices,
        default=ReplayStatus.PENDING,
        verbose_name=_('Status'),
    )
    replayed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('Replayed At'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At'),
    )
    
    class Meta:
        verbose_name = _('Webhook Replay')
        verbose_name_plural = _('Webhook Replays')
        indexes = [
            models.Index(fields=['original_log', 'status'], name='wr_original_status_idx'),
            models.Index(fields=['replayed_by', 'replayed_at'], name='wr_replayed_by_at_idx'),
            models.Index(fields=['status', 'created_at'], name='wr_status_created_idx'),
        ]
    
    def __str__(self) -> str:
        return f"Replay of log {self.original_log_id} ({self.status})"


class WebhookReplayBatch(models.Model):
    """
    Batch replay operations for webhook events.
    Allows replaying multiple events within a date range.
    """
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replay_batches',
        verbose_name=_('Created By'),
    )
    event_type = models.CharField(
        max_length=100,
        verbose_name=_('Event Type'),
        help_text=_('Type of events to replay')
    )
    date_from = models.DateField(
        verbose_name=_('Date From'),
        help_text=_('Start date for event replay')
    )
    date_to = models.DateField(
        verbose_name=_('Date To'),
        help_text=_('End date for event replay')
    )
    count = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name=_('Count'),
        help_text=_('Number of events replayed')
    )
    status = models.CharField(
        max_length=20,
        choices=ReplayStatus.choices,
        default=ReplayStatus.PENDING,
        verbose_name=_('Status'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At'),
    )
    
    class Meta:
        verbose_name = _('Webhook Replay Batch')
        verbose_name_plural = _('Webhook Replay Batches')
        indexes = [
            models.Index(fields=['created_by', 'status'], name='wrb_created_by_status_idx'),
            models.Index(fields=['event_type'], name='wrb_event_type_idx'),
            models.Index(fields=['status', 'created_at'], name='wrb_status_created_idx'),
        ]
    
    def __str__(self) -> str:
        return f"Batch replay of {self.event_type} ({self.count} events)"


class WebhookReplayItem(models.Model):
    """
    Individual items within a replay batch.
    Links replay batches to specific delivery logs.
    """
    
    batch = models.ForeignKey(
        WebhookReplayBatch,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_('Batch'),
    )
    original_log = models.ForeignKey(
        'WebhookDeliveryLog',
        on_delete=models.CASCADE,
        related_name='replay_batch_items',
        verbose_name=_('Original Log'),
    )
    new_log = models.ForeignKey(
        'WebhookDeliveryLog',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replay_batch_new_logs',
        verbose_name=_('New Log'),
    )
    status = models.CharField(
        max_length=20,
        choices=ReplayStatus.choices,
        default=ReplayStatus.PENDING,
        verbose_name=_('Status'),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At'),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At'),
    )
    
    class Meta:
        verbose_name = _('Webhook Replay Item')
        verbose_name_plural = _('Webhook Replay Items')
        indexes = [
            models.Index(fields=['batch', 'status'], name='wri_batch_status_idx'),
            models.Index(fields=['original_log'], name='wri_original_log_idx'),
            models.Index(fields=['new_log'], name='wri_new_log_idx'),
        ]
        unique_together = [
            ['batch', 'original_log'],
        ]
    
    def __str__(self) -> str:
        return f"Replay item {self.id} in batch {self.batch.id}"
