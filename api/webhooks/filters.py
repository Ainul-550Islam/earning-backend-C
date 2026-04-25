"""Webhooks Filters Module

This module contains Django filter classes for the webhooks system,
provides filtering capabilities for API endpoints and admin interfaces.
"""

import django_filters
from django.utils.translation import gettext_lazy as _
from django.db import models

from .models import (
    WebhookEndpoint, WebhookSubscription, WebhookDeliveryLog,
    WebhookFilter, WebhookBatch, WebhookTemplate, WebhookSecret,
    InboundWebhook, InboundWebhookLog, InboundWebhookRoute, InboundWebhookError,
    WebhookAnalytics, WebhookHealthLog, WebhookEventStat, WebhookRateLimit,
    WebhookRetryAnalysis, WebhookReplay, WebhookReplayBatch, WebhookReplayItem
)
from .constants import (
    WebhookStatus, HttpMethod, DeliveryStatus, FilterOperator,
    BatchStatus, ReplayStatus, InboundSource, ErrorType
)


class WebhookEndpointFilter(django_filters.FilterSet):
    """Filter for webhook endpoints."""
    
    status = django_filters.ChoiceFilter(
        choices=WebhookStatus.CHOICES,
        label=_('Status')
    )
    
    url = django_filters.CharFilter(
        lookup_expr='icontains',
        label=_('URL')
    )
    
    http_method = django_filters.ChoiceFilter(
        choices=HttpMethod.CHOICES,
        label=_('HTTP Method')
    )
    
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        label=_('Created Date Range')
    )
    
    updated_at = django_filters.DateTimeFromToRangeFilter(
        field_name='updated_at',
        label=_('Updated Date Range')
    )
    
    class Meta:
        model = WebhookEndpoint
        fields = ['status', 'url', 'http_method', 'created_at', 'updated_at']


class WebhookSubscriptionFilter(django_filters.FilterSet):
    """Filter for webhook subscriptions."""
    
    endpoint = django_filters.ModelChoiceFilter(
        queryset=WebhookEndpoint.objects.all(),
        label=_('Endpoint')
    )
    
    event_type = django_filters.CharFilter(
        lookup_expr='icontains',
        label=_('Event Type')
    )
    
    is_active = django_filters.BooleanFilter(
        label=_('Is Active')
    )
    
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        label=_('Created Date Range')
    )
    
    class Meta:
        model = WebhookSubscription
        fields = ['endpoint', 'event_type', 'is_active', 'created_at']


class WebhookDeliveryLogFilter(django_filters.FilterSet):
    """Filter for webhook delivery logs."""
    
    endpoint = django_filters.ModelChoiceFilter(
        queryset=WebhookEndpoint.objects.all(),
        label=_('Endpoint')
    )
    
    event_type = django_filters.CharFilter(
        lookup_expr='icontains',
        label=_('Event Type')
    )
    
    status = django_filters.ChoiceFilter(
        choices=DeliveryStatus.CHOICES,
        label=_('Status')
    )
    
    response_code = django_filters.NumberFilter(
        label=_('Response Code')
    )
    
    attempt_number = django_filters.NumberFilter(
        label=_('Attempt Number')
    )
    
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        label=_('Created Date Range')
    )
    
    class Meta:
        model = WebhookDeliveryLog
        fields = ['endpoint', 'event_type', 'status', 'response_code', 'attempt_number', 'created_at']


class WebhookFilterFilter(django_filters.FilterSet):
    """Filter for webhook filters."""
    
    endpoint = django_filters.ModelChoiceFilter(
        queryset=WebhookEndpoint.objects.all(),
        label=_('Endpoint')
    )
    
    field_path = django_filters.CharFilter(
        lookup_expr='icontains',
        label=_('Field Path')
    )
    
    operator = django_filters.ChoiceFilter(
        choices=FilterOperator.CHOICES,
        label=_('Operator')
    )
    
    is_active = django_filters.BooleanFilter(
        label=_('Is Active')
    )
    
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        label=_('Created Date Range')
    )
    
    class Meta:
        model = WebhookFilter
        fields = ['endpoint', 'field_path', 'operator', 'is_active', 'created_at']


class WebhookBatchFilter(django_filters.FilterSet):
    """Filter for webhook batches."""
    
    endpoint = django_filters.ModelChoiceFilter(
        queryset=WebhookEndpoint.objects.all(),
        label=_('Endpoint')
    )
    
    status = django_filters.ChoiceFilter(
        choices=BatchStatus.CHOICES,
        label=_('Status')
    )
    
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        label=_('Created Date Range')
    )
    
    completed_at = django_filters.DateTimeFromToRangeFilter(
        field_name='completed_at',
        label=_('Completed Date Range')
    )
    
    class Meta:
        model = WebhookBatch
        fields = ['endpoint', 'status', 'created_at', 'completed_at']


class WebhookTemplateFilter(django_filters.FilterSet):
    """Filter for webhook templates."""
    
    event_type = django_filters.CharFilter(
        lookup_expr='icontains',
        label=_('Event Type')
    )
    
    is_active = django_filters.BooleanFilter(
        label=_('Is Active')
    )
    
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        label=_('Created Date Range')
    )
    
    class Meta:
        model = WebhookTemplate
        fields = ['event_type', 'is_active', 'created_at']


class InboundWebhookFilter(django_filters.FilterSet):
    """Filter for inbound webhooks."""
    
    source = django_filters.ChoiceFilter(
        choices=InboundSource.CHOICES,
        label=_('Source')
    )
    
    is_active = django_filters.BooleanFilter(
        label=_('Is Active')
    )
    
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        label=_('Created Date Range')
    )
    
    class Meta:
        model = InboundWebhook
        fields = ['source', 'is_active', 'created_at']


class InboundWebhookLogFilter(django_filters.FilterSet):
    """Filter for inbound webhook logs."""
    
    inbound = django_filters.ModelChoiceFilter(
        queryset=InboundWebhook.objects.all(),
        label=_('Inbound Webhook')
    )
    
    ip_address = django_filters.CharFilter(
        lookup_expr='icontains',
        label=_('IP Address')
    )
    
    signature_valid = django_filters.BooleanFilter(
        label=_('Signature Valid')
    )
    
    processed = django_filters.BooleanFilter(
        label=_('Processed')
    )
    
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        label=_('Created Date Range')
    )
    
    class Meta:
        model = InboundWebhookLog
        fields = ['inbound', 'ip_address', 'signature_valid', 'processed', 'created_at']


class WebhookAnalyticsFilter(django_filters.FilterSet):
    """Filter for webhook analytics."""
    
    endpoint = django_filters.ModelChoiceFilter(
        queryset=WebhookEndpoint.objects.all(),
        label=_('Endpoint')
    )
    
    date = django_filters.DateFromToRangeFilter(
        field_name='date',
        label=_('Date Range')
    )
    
    total_sent = django_filters.NumberFilter(
        label=_('Total Sent')
    )
    
    success_count = django_filters.NumberFilter(
        label=_('Success Count')
    )
    
    failed_count = django_filters.NumberFilter(
        label=_('Failed Count')
    )
    
    avg_latency_ms = django_filters.NumberFilter(
        label=_('Avg Latency (ms)')
    )
    
    class Meta:
        model = WebhookAnalytics
        fields = ['endpoint', 'date', 'total_sent', 'success_count', 'failed_count', 'avg_latency_ms']


class WebhookHealthLogFilter(django_filters.FilterSet):
    """Filter for webhook health logs."""
    
    endpoint = django_filters.ModelChoiceFilter(
        queryset=WebhookEndpoint.objects.all(),
        label=_('Endpoint')
    )
    
    is_healthy = django_filters.BooleanFilter(
        label=_('Is Healthy')
    )
    
    response_time_ms = django_filters.NumberFilter(
        label=_('Response Time (ms)')
    )
    
    status_code = django_filters.NumberFilter(
        label=_('Status Code')
    )
    
    checked_at = django_filters.DateTimeFromToRangeFilter(
        field_name='checked_at',
        label=_('Checked Date Range')
    )
    
    class Meta:
        model = WebhookHealthLog
        fields = ['endpoint', 'is_healthy', 'response_time_ms', 'status_code', 'checked_at']


class WebhookReplayFilter(django_filters.FilterSet):
    """Filter for webhook replays."""
    
    original_log = django_filters.ModelChoiceFilter(
        queryset=WebhookDeliveryLog.objects.all(),
        label=_('Original Log')
    )
    
    replayed_by = django_filters.ModelChoiceFilter(
        queryset=get_user_model().objects.all(),
        label=_('Replayed By')
    )
    
    status = django_filters.ChoiceFilter(
        choices=ReplayStatus.CHOICES,
        label=_('Status')
    )
    
    replayed_at = django_filters.DateTimeFromToRangeFilter(
        field_name='replayed_at',
        label=_('Replayed Date Range')
    )
    
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        label=_('Created Date Range')
    )
    
    class Meta:
        model = WebhookReplay
        fields = ['original_log', 'replayed_by', 'status', 'replayed_at', 'created_at']


class WebhookReplayBatchFilter(django_filters.FilterSet):
    """Filter for webhook replay batches."""
    
    created_by = django_filters.ModelChoiceFilter(
        queryset=get_user_model().objects.all(),
        label=_('Created By')
    )
    
    event_type = django_filters.CharFilter(
        lookup_expr='icontains',
        label=_('Event Type')
    )
    
    status = django_filters.ChoiceFilter(
        choices=ReplayStatus.CHOICES,
        label=_('Status')
    )
    
    date_from = django_filters.DateFilter(
        label=_('Date From')
    )
    
    date_to = django_filters.DateFilter(
        label=_('Date To')
    )
    
    created_at = django_filters.DateTimeFromToRangeFilter(
        field_name='created_at',
        label=_('Created Date Range')
    )
    
    class Meta:
        model = WebhookReplayBatch
        fields = ['created_by', 'event_type', 'status', 'date_from', 'date_to', 'created_at']


class WebhookEventStatFilter(django_filters.FilterSet):
    """Filter for webhook event statistics."""
    
    event_type = django_filters.CharFilter(
        lookup_expr='icontains',
        label=_('Event Type')
    )
    
    date = django_filters.DateFromToRangeFilter(
        field_name='date',
        label=_('Date Range')
    )
    
    fired_count = django_filters.NumberFilter(
        label=_('Fired Count')
    )
    
    delivered_count = django_filters.NumberFilter(
        label=_('Delivered Count')
    )
    
    failed_count = django_filters.NumberFilter(
        label=_('Failed Count')
    )
    
    class Meta:
        model = WebhookEventStat
        fields = ['event_type', 'date', 'fired_count', 'delivered_count', 'failed_count']


class WebhookRateLimitFilter(django_filters.FilterSet):
    """Filter for webhook rate limits."""
    
    endpoint = django_filters.ModelChoiceFilter(
        queryset=WebhookEndpoint.objects.all(),
        label=_('Endpoint')
    )
    
    window_seconds = django_filters.NumberFilter(
        label=_('Window Seconds')
    )
    
    max_requests = django_filters.NumberFilter(
        label=_('Max Requests')
    )
    
    current_count = django_filters.NumberFilter(
        label=_('Current Count')
    )
    
    reset_at = django_filters.DateTimeFromToRangeFilter(
        field_name='reset_at',
        label=_('Reset Date Range')
    )
    
    class Meta:
        model = WebhookRateLimit
        fields = ['endpoint', 'window_seconds', 'max_requests', 'current_count', 'reset_at']
