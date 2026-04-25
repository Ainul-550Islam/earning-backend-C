# earning_backend/api/notifications/filters.py
"""
Django-filter FilterSet classes for all notification endpoints.
Enables powerful API filtering: /notifications/?channel=push&is_read=false&date_from=2024-01-01
"""
import django_filters
from django.db.models import Q
from django_filters import rest_framework as filters


class NotificationFilter(filters.FilterSet):
    """Filter for the main Notification model."""
    from api.notifications.models import Notification

    is_read = filters.BooleanFilter()
    is_archived = filters.BooleanFilter()
    is_pinned = filters.BooleanFilter()
    is_sent = filters.BooleanFilter()
    is_delivered = filters.BooleanFilter()
    channel = filters.ChoiceFilter(choices=[
        ('in_app', 'In-App'), ('push', 'Push'), ('email', 'Email'),
        ('sms', 'SMS'), ('telegram', 'Telegram'), ('whatsapp', 'WhatsApp'),
        ('browser', 'Browser'), ('all', 'All'),
    ])
    priority = filters.ChoiceFilter(choices=[
        ('lowest', 'Lowest'), ('low', 'Low'), ('medium', 'Medium'),
        ('high', 'High'), ('urgent', 'Urgent'), ('critical', 'Critical'),
    ])
    notification_type = filters.CharFilter()
    status = filters.CharFilter()
    date_from = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    date_to = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    search = filters.CharFilter(method='search_filter')
    campaign_id = filters.CharFilter()
    group_id = filters.CharFilter()

    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(title__icontains=value) | Q(message__icontains=value)
        )

    class Meta:
        model = Notification
        fields = [
            'is_read', 'is_archived', 'is_pinned', 'is_sent', 'is_delivered',
            'channel', 'priority', 'notification_type', 'status',
            'date_from', 'date_to', 'search', 'campaign_id', 'group_id',
        ]


class PushDeviceFilter(filters.FilterSet):
    """Filter for PushDevice model."""
    from api.notifications.models.channel import PushDevice

    is_active = filters.BooleanFilter()
    device_type = filters.ChoiceFilter(choices=[
        ('android', 'Android'), ('ios', 'iOS'), ('web', 'Web'),
        ('desktop', 'Desktop'), ('other', 'Other'),
    ])
    last_used_from = filters.DateTimeFilter(field_name='last_used', lookup_expr='gte')
    last_used_to = filters.DateTimeFilter(field_name='last_used', lookup_expr='lte')

    class Meta:
        model = PushDevice
        fields = ['is_active', 'device_type', 'last_used_from', 'last_used_to']


class InAppMessageFilter(filters.FilterSet):
    """Filter for InAppMessage model."""
    from api.notifications.models.channel import InAppMessage

    is_read = filters.BooleanFilter()
    is_dismissed = filters.BooleanFilter()
    message_type = filters.ChoiceFilter(choices=[
        ('banner', 'Banner'), ('modal', 'Modal'), ('toast', 'Toast'),
        ('bottom_sheet', 'Bottom Sheet'), ('full_screen', 'Full Screen'),
    ])
    expired = filters.BooleanFilter(method='filter_expired')
    created_from = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_to = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    def filter_expired(self, queryset, name, value):
        from django.utils import timezone as tz
        now = tz.now()
        if value:
            return queryset.filter(expires_at__lt=now)
        return queryset.filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))

    class Meta:
        model = InAppMessage
        fields = ['is_read', 'is_dismissed', 'message_type', 'expired', 'created_from', 'created_to']


class NotificationScheduleFilter(filters.FilterSet):
    """Filter for NotificationSchedule model."""
    from api.notifications.models.schedule import NotificationSchedule

    status = filters.ChoiceFilter(choices=[
        ('pending', 'Pending'), ('processing', 'Processing'), ('sent', 'Sent'),
        ('cancelled', 'Cancelled'), ('failed', 'Failed'), ('skipped', 'Skipped'),
    ])
    send_at_from = filters.DateTimeFilter(field_name='send_at', lookup_expr='gte')
    send_at_to = filters.DateTimeFilter(field_name='send_at', lookup_expr='lte')

    class Meta:
        model = NotificationSchedule
        fields = ['status', 'send_at_from', 'send_at_to']


class NotificationBatchFilter(filters.FilterSet):
    """Filter for NotificationBatch model."""
    from api.notifications.models.schedule import NotificationBatch

    status = filters.CharFilter()
    created_from = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_to = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = NotificationBatch
        fields = ['status', 'created_from', 'created_to']


class CampaignFilter(filters.FilterSet):
    """Filter for NewNotificationCampaign."""
    from api.notifications.models.campaign import NotificationCampaign

    status = filters.CharFilter()
    send_at_from = filters.DateTimeFilter(field_name='send_at', lookup_expr='gte')
    send_at_to = filters.DateTimeFilter(field_name='send_at', lookup_expr='lte')
    search = filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        model = NotificationCampaign
        fields = ['status', 'send_at_from', 'send_at_to', 'search']


class NotificationInsightFilter(filters.FilterSet):
    """Filter for NotificationInsight analytics."""
    from api.notifications.models.analytics import NotificationInsight

    channel = filters.CharFilter()
    date_from = filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = filters.DateFilter(field_name='date', lookup_expr='lte')

    class Meta:
        model = NotificationInsight
        fields = ['channel', 'date_from', 'date_to']


class OptOutTrackingFilter(filters.FilterSet):
    """Filter for OptOutTracking."""
    from api.notifications.models.analytics import OptOutTracking

    channel = filters.CharFilter()
    is_active = filters.BooleanFilter()
    reason = filters.CharFilter()
    opted_out_from = filters.DateTimeFilter(field_name='opted_out_at', lookup_expr='gte')
    opted_out_to = filters.DateTimeFilter(field_name='opted_out_at', lookup_expr='lte')

    class Meta:
        model = OptOutTracking
        fields = ['channel', 'is_active', 'reason', 'opted_out_from', 'opted_out_to']


class DeliveryRateFilter(filters.FilterSet):
    """Filter for DeliveryRate."""
    from api.notifications.models.analytics import DeliveryRate

    channel = filters.CharFilter()
    date_from = filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = filters.DateFilter(field_name='date', lookup_expr='lte')

    class Meta:
        model = DeliveryRate
        fields = ['channel', 'date_from', 'date_to']
