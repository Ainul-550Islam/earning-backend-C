"""
Analytics Models for Webhooks System

This module contains analytics and health monitoring models
for webhook performance and statistics.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

from .constants import (
    WebhookStatus, DeliveryStatus, ErrorType
)

User = get_user_model()


class WebhookAnalytics(models.Model):
    """
    Daily analytics for webhook endpoints.
    Tracks delivery statistics, success rates, and performance metrics.
    """
    
    date = models.DateField(
        verbose_name=_('Date'),
        help_text=_('Date for these analytics')
    )
    endpoint = models.ForeignKey(
        'WebhookEndpoint',
        on_delete=models.CASCADE,
        related_name='analytics',
        verbose_name=_('Endpoint'),
    )
    total_sent = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Total Sent'),
    )
    success_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Success Count'),
    )
    failed_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Failed Count'),
    )
    avg_latency_ms = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Average Latency (ms)'),
    )
    success_rate = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_('Success Rate (%)'),
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
        verbose_name = _('Webhook Analytics')
        verbose_name_plural = _('Webhook Analytics')
        indexes = [
            models.Index(fields=['date', 'endpoint'], name='wa_date_endpoint_idx'),
            models.Index(fields=['date'], name='wa_date_idx'),
        ]
        unique_together = [
            ['date', 'endpoint'],
        ]
    
    def __str__(self) -> str:
        return f"Analytics for {self.endpoint.url} on {self.date}"
    
    def save(self, *args, **kwargs):
        """Calculate success rate before saving."""
        if self.total_sent > 0:
            self.success_rate = (self.success_count / self.total_sent) * 100
        super().save(*args, **kwargs)


class WebhookHealthLog(models.Model):
    """
    Health check logs for webhook endpoints.
    Tracks endpoint availability and response times.
    """
    
    endpoint = models.ForeignKey(
        'WebhookEndpoint',
        on_delete=models.CASCADE,
        related_name='health_logs',
        verbose_name=_('Endpoint'),
    )
    checked_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Checked At'),
    )
    is_healthy = models.BooleanField(
        default=True,
        verbose_name=_('Is Healthy'),
    )
    response_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_('Response Time (ms)'),
    )
    status_code = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(100), MaxValueValidator(599)],
        verbose_name=_('Status Code'),
    )
    error = models.TextField(
        blank=True,
        default='',
        verbose_name=_('Error Message'),
    )
    
    class Meta:
        verbose_name = _('Webhook Health Log')
        verbose_name_plural = _('Webhook Health Logs')
        indexes = [
            models.Index(fields=['endpoint', 'checked_at'], name='whl_endpoint_checked_idx'),
            models.Index(fields=['checked_at'], name='whl_checked_at_idx'),
            models.Index(fields=['is_healthy'], name='whl_healthy_idx'),
        ]
    
    def __str__(self) -> str:
        status = "Healthy" if self.is_healthy else "Unhealthy"
        return f"Health check for {self.endpoint.url}: {status}"


class WebhookEventStat(models.Model):
    """
    Event type statistics for webhooks.
    Tracks which events are fired most frequently.
    """
    
    date = models.DateField(
        verbose_name=_('Date'),
        help_text=_('Date for these event statistics')
    )
    event_type = models.CharField(
        max_length=100,
        verbose_name=_('Event Type'),
        help_text=_('Type of event tracked')
    )
    fired_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Fired Count'),
    )
    delivered_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Delivered Count'),
    )
    failed_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Failed Count'),
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
        verbose_name = _('Webhook Event Stat')
        verbose_name_plural = _('Webhook Event Stats')
        indexes = [
            models.Index(fields=['date', 'event_type'], name='wes_date_event_idx'),
            models.Index(fields=['event_type'], name='wes_event_idx'),
        ]
        unique_together = [
            ['date', 'event_type'],
        ]
    
    def __str__(self) -> str:
        return f"Event stats for {self.event_type} on {self.date}"


class WebhookRateLimit(models.Model):
    """
    Rate limiting configuration for webhook endpoints.
    Tracks API usage and implements throttling.
    """
    
    endpoint = models.ForeignKey(
        'WebhookEndpoint',
        on_delete=models.CASCADE,
        related_name='rate_limits',
        verbose_name=_('Endpoint'),
    )
    window_seconds = models.PositiveIntegerField(
        default=3600,
        validators=[MinValueValidator(60)],
        verbose_name=_('Window Seconds'),
        help_text=_('Time window for rate limiting in seconds')
    )
    max_requests = models.PositiveIntegerField(
        default=1000,
        validators=[MinValueValidator(1)],
        verbose_name=_('Max Requests'),
        help_text=_('Maximum requests allowed in the time window')
    )
    current_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Current Count'),
    )
    reset_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Reset At'),
        help_text=_('When the counter will reset')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At'),
    )
    
    class Meta:
        verbose_name = _('Webhook Rate Limit')
        verbose_name_plural = _('Webhook Rate Limits')
        indexes = [
            models.Index(fields=['endpoint', 'reset_at'], name='wrl_endpoint_reset_idx'),
            models.Index(fields=['reset_at'], name='wrl_reset_at_idx'),
        ]
    
    def __str__(self) -> str:
        return f"Rate limit for {self.endpoint.url}: {self.current_count}/{self.max_requests}"
    
    def is_exceeded(self) -> bool:
        """Check if rate limit is exceeded."""
        return self.current_count >= self.max_requests
    
    def reset_counter(self):
        """Reset the rate limit counter."""
        self.current_count = 0
        self.reset_at = timezone.now()
        self.save()


class WebhookRetryAnalysis(models.Model):
    """
    Analysis of webhook retry patterns.
    Helps identify problematic endpoints and optimize retry strategy.
    """
    
    endpoint = models.ForeignKey(
        'WebhookEndpoint',
        on_delete=models.CASCADE,
        related_name='retry_analyses',
        verbose_name=_('Endpoint'),
    )
    period = models.CharField(
        max_length=20,
        choices=[
            ('hourly', _('Hourly')),
            ('daily', _('Daily')),
            ('weekly', _('Weekly')),
            ('monthly', _('Monthly')),
        ],
        default='daily',
        verbose_name=_('Period'),
    )
    avg_attempts_before_success = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Avg Attempts Before Success'),
    )
    exhausted_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_('Exhausted Count'),
        help_text=_('Number of times retry limit was exhausted')
    )
    success_rate = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_('Success Rate (%)'),
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
        verbose_name = _('Webhook Retry Analysis')
        verbose_name_plural = _('Webhook Retry Analyses')
        indexes = [
            models.Index(fields=['endpoint', 'period'], name='wra_endpoint_period_idx'),
            models.Index(fields=['period'], name='wra_period_idx'),
        ]
        unique_together = [
            ['endpoint', 'period'],
        ]
    
    def __str__(self) -> str:
        return f"Retry analysis for {self.endpoint.url} ({self.period})"
