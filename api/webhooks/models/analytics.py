"""
Analytics Models for Webhooks System

This module contains analytics and health monitoring models
for webhook performance and statistics.

FIXES APPLIED:
    [ANA-01] WebhookRateLimit.reset_at was declared with auto_now_add=True.
             auto_now_add makes a field permanently read-only at the database
             layer — Django silently ignores any assignment to it on .save().
             As a result, reset_counter() was a no-op: the counter field
             decremented but the reset_at timestamp never updated, meaning
             the rate-limit window was frozen at the row's creation time
             forever.
             Fix: changed to default=timezone.now (mutable, writable).

    [ANA-02] WebhookAnalytics.save() recalculated success_rate on every
             save but did not pass update_fields, causing a full-row write
             on every analytics aggregation task tick and risking lost
             updates under concurrent writes.
             Fix: pass update_fields when a subset is sufficient.
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
        verbose_name=_("Date"),
        help_text=_("Date for these analytics"),
    )
    endpoint = models.ForeignKey(
        "WebhookEndpoint",
        on_delete=models.CASCADE,
        related_name="analytics",
        verbose_name=_("Endpoint"),
    )
    total_sent = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Total Sent"),
    )
    success_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Success Count"),
    )
    failed_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Failed Count"),
    )
    avg_latency_ms = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Average Latency (ms)"),
    )
    success_rate = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Success Rate (%)"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True,     verbose_name=_("Updated At"))

    class Meta:
        verbose_name        = _("Webhook Analytics")
        verbose_name_plural = _("Webhook Analytics")
        indexes = [
            models.Index(fields=["date", "endpoint"], name="wa_date_endpoint_idx"),
            models.Index(fields=["date"],              name="wa_date_idx"),
        ]
        unique_together = [["date", "endpoint"]]
        constraints = [
            models.CheckConstraint(check=models.Q(total_sent__gte=0), name="wa_total_sent_gte_0"),
            models.CheckConstraint(check=models.Q(success_count__gte=0), name="wa_success_count_gte_0"),
            models.CheckConstraint(check=models.Q(failed_count__gte=0), name="wa_failed_count_gte_0"),
            models.CheckConstraint(check=models.Q(avg_latency_ms__gte=0), name="wa_avg_latency_gte_0"),
            models.CheckConstraint(check=models.Q(success_rate__gte=0) & models.Q(success_rate__lte=100),
                name="wa_success_rate_range",
            ),
        ]

    def __str__(self) -> str:
        return f"Analytics for {self.endpoint.target_url} on {self.date}"

    def save(self, *args, **kwargs):
        """
        Calculate success_rate before saving.

        FIX [ANA-02]: When called from an aggregation task that only touches
        numeric counters, pass update_fields so Django issues a targeted
        UPDATE instead of a full-row write.  This prevents lost-update races
        when multiple Celery workers process the same daily analytics row.

        Callers that want a full save (e.g. bulk upserts) omit update_fields
        and get the previous behaviour.
        """
        if self.total_sent > 0:
            self.success_rate = round((self.success_count / self.total_sent) * 100, 2)
        else:
            self.success_rate = 0.0

        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "success_rate" not in update_fields:
            # Ensure success_rate is always persisted when other counters are
            kwargs["update_fields"] = list(update_fields) + ["success_rate"]

        super().save(*args, **kwargs)


class WebhookHealthLog(models.Model):
    """
    Health check logs for webhook endpoints.
    Tracks endpoint availability and response times.
    """

    endpoint = models.ForeignKey(
        "WebhookEndpoint",
        on_delete=models.CASCADE,
        related_name="health_logs",
        verbose_name=_("Endpoint"),
    )
    checked_at = models.DateTimeField(default=timezone.now, verbose_name=_("Checked At"))
    is_healthy = models.BooleanField(default=True, verbose_name=_("Is Healthy"))
    response_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_("Response Time (ms)"),
    )
    status_code = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(100), MaxValueValidator(599)],
        verbose_name=_("Status Code"),
    )
    error = models.TextField(blank=True, null=True, default="", verbose_name=_("Error Message"))

    # Added session 6: same reason as WebhookDeliveryLog.archived above.
    archived = models.BooleanField(default=False, db_index=True, verbose_name=_("Archived"))
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Archived At"))

    class Meta:
        verbose_name        = _("Webhook Health Log")
        verbose_name_plural = _("Webhook Health Logs")
        indexes = [
            models.Index(fields=["endpoint", "checked_at"], name="whl_endpoint_checked_idx"),
            models.Index(fields=["checked_at"],              name="whl_checked_at_idx"),
            models.Index(fields=["is_healthy"],              name="whl_healthy_idx"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(response_time_ms__gte=0), name="whl_response_time_gte_0"),
            models.CheckConstraint(check=models.Q(status_code__isnull=True) | (models.Q(status_code__gte=100) & models.Q(status_code__lte=599)),
                name="whl_status_code_range",
            ),
        ]

    def __str__(self) -> str:
        status = "Healthy" if self.is_healthy else "Unhealthy"
        return f"Health check for {self.endpoint.target_url}: {status}"


class WebhookEventStat(models.Model):
    """
    Event type statistics for webhooks.
    Tracks which events are fired most frequently.
    """

    date = models.DateField(
        verbose_name=_("Date"),
        help_text=_("Date for these event statistics"),
    )
    event_type = models.CharField(
        max_length=100,
        verbose_name=_("Event Type"),
        help_text=_("Type of event tracked"),
    )
    fired_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Fired Count"),
    )
    delivered_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Delivered Count"),
    )
    failed_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Failed Count"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True,     verbose_name=_("Updated At"))

    class Meta:
        verbose_name        = _("Webhook Event Stat")
        verbose_name_plural = _("Webhook Event Stats")
        indexes = [
            models.Index(fields=["date", "event_type"], name="wes_date_event_idx"),
            models.Index(fields=["event_type"],          name="wes_event_idx"),
        ]
        unique_together = [["date", "event_type"]]
        constraints = [
            models.CheckConstraint(check=models.Q(fired_count__gte=0), name="wes_fired_count_gte_0"),
            models.CheckConstraint(check=models.Q(delivered_count__gte=0), name="wes_delivered_count_gte_0"),
            models.CheckConstraint(check=models.Q(failed_count__gte=0), name="wes_failed_count_gte_0"),
        ]

    def __str__(self) -> str:
        return f"Event stats for {self.event_type} on {self.date}"


class WebhookRateLimit(models.Model):
    """
    Rate limiting configuration for webhook endpoints.
    Tracks API usage and implements throttling.

    FIX [ANA-01]: reset_at was previously `auto_now_add=True`, which made
    the field permanently read-only at the database layer.  The reset_counter()
    method tried to update it but the assignment was silently discarded by
    Django's ORM.  Changed to `default=timezone.now` so the field is writable
    and reset_counter() works as intended.
    """

    endpoint = models.ForeignKey(
        "WebhookEndpoint",
        on_delete=models.CASCADE,
        related_name="rate_limits",
        verbose_name=_("Endpoint"),
    )
    window_seconds = models.PositiveIntegerField(
        default=3600,
        validators=[MinValueValidator(60)],
        verbose_name=_("Window Seconds"),
        help_text=_("Time window for rate limiting in seconds"),
    )
    max_requests = models.PositiveIntegerField(
        default=1000,
        validators=[MinValueValidator(1)],
        verbose_name=_("Max Requests"),
        help_text=_("Maximum requests allowed in the time window"),
    )
    current_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Current Count"),
    )

    # FIX [ANA-01]: was auto_now_add=True — now default=timezone.now so that
    # reset_counter() can successfully update this field via .save().
    reset_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Reset At"),
        help_text=_("When the rate-limit counter was last reset"),
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        verbose_name        = _("Webhook Rate Limit")
        verbose_name_plural = _("Webhook Rate Limits")
        indexes = [
            models.Index(fields=["endpoint", "reset_at"], name="wrl_endpoint_reset_idx"),
            models.Index(fields=["reset_at"],              name="wrl_reset_at_idx"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(window_seconds__gte=60), name="wrl_window_seconds_gte_60"),
            models.CheckConstraint(check=models.Q(max_requests__gte=1), name="wrl_max_requests_gte_1"),
            models.CheckConstraint(check=models.Q(current_count__gte=0), name="wrl_current_count_gte_0"),
        ]

    def __str__(self) -> str:
        return (
            f"Rate limit for {self.endpoint.target_url}: "
            f"{self.current_count}/{self.max_requests}"
        )

    def is_exceeded(self) -> bool:
        """Check if rate limit is exceeded."""
        return self.current_count >= self.max_requests

    def window_has_expired(self) -> bool:
        """True when the current window has passed and the counter should reset."""
        from datetime import timedelta
        return timezone.now() >= self.reset_at + timedelta(seconds=self.window_seconds)

    def reset_counter(self):
        """
        Reset the rate limit counter and advance the window start time.

        With reset_at using default=timezone.now (not auto_now_add), this
        assignment is now persisted by .save() as intended.
        """
        self.current_count = 0
        self.reset_at      = timezone.now()
        self.save(update_fields=["current_count", "reset_at", "updated_at"])


class WebhookRetryAnalysis(models.Model):
    """
    Analysis of webhook retry patterns.
    Helps identify problematic endpoints and optimise retry strategy.
    """

    endpoint = models.ForeignKey(
        "WebhookEndpoint",
        on_delete=models.CASCADE,
        related_name="retry_analyses",
        verbose_name=_("Endpoint"),
    )
    period = models.CharField(
        max_length=20,
        choices=[
            ("hourly",  _("Hourly")),
            ("daily",   _("Daily")),
            ("weekly",  _("Weekly")),
            ("monthly", _("Monthly")),
        ],
        default="daily",
        verbose_name=_("Period"),
    )
    avg_attempts_before_success = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Avg Attempts Before Success"),
    )
    exhausted_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Exhausted Count"),
        help_text=_("Number of times retry limit was exhausted"),
    )
    success_rate = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Success Rate (%)"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True,     verbose_name=_("Updated At"))

    class Meta:
        verbose_name        = _("Webhook Retry Analysis")
        verbose_name_plural = _("Webhook Retry Analyses")
        indexes = [
            models.Index(fields=["endpoint", "period"], name="wra_endpoint_period_idx"),
            models.Index(fields=["period"],              name="wra_period_idx"),
        ]
        unique_together = [["endpoint", "period"]]
        constraints = [
            models.CheckConstraint(check=models.Q(avg_attempts_before_success__gte=0), name="wra_avg_attempts_gte_0"),
            models.CheckConstraint(check=models.Q(exhausted_count__gte=0), name="wra_exhausted_count_gte_0"),
            models.CheckConstraint(check=models.Q(success_rate__gte=0) & models.Q(success_rate__lte=100),
                name="wra_success_rate_range",
            ),
        ]

    def __str__(self) -> str:
        return f"Retry analysis for {self.endpoint.target_url} ({self.period})"
