# =============================================================================
# behavior_analytics/filters.py
# =============================================================================
"""
django-filter FilterSet classes for all analytics models.

All date/time filters use timezone-aware ISO-8601 strings.
Numeric range filters are inclusive on both ends.
"""

from __future__ import annotations

import django_filters
from django.db import models as django_models

from .choices import ClickCategory, DeviceType, EngagementTier, SessionStatus
from .models import ClickMetric, EngagementScore, StayTime, UserPath


class UserPathFilter(django_filters.FilterSet):
    """
    Filterable fields for the UserPath list endpoint.

    Query-string examples:
      ?status=active
      ?device_type=mobile
      ?created_after=2024-01-01T00:00:00Z
      ?created_before=2024-02-01T00:00:00Z
    """

    status      = django_filters.MultipleChoiceFilter(choices=SessionStatus.choices)
    device_type = django_filters.MultipleChoiceFilter(choices=DeviceType.choices)

    created_after  = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )
    session_id = django_filters.CharFilter(lookup_expr="exact")

    class Meta:
        model  = UserPath
        fields = ["status", "device_type", "session_id"]


class ClickMetricFilter(django_filters.FilterSet):
    """
    Filterable fields for the ClickMetric list endpoint.

    Query-string examples:
      ?category=cta
      ?page_url__contains=product
      ?clicked_after=2024-03-01T08:00:00Z
    """

    category = django_filters.MultipleChoiceFilter(choices=ClickCategory.choices)

    clicked_after  = django_filters.IsoDateTimeFilter(
        field_name="clicked_at", lookup_expr="gte"
    )
    clicked_before = django_filters.IsoDateTimeFilter(
        field_name="clicked_at", lookup_expr="lte"
    )
    page_url_contains = django_filters.CharFilter(
        field_name="page_url", lookup_expr="icontains"
    )
    element_selector_contains = django_filters.CharFilter(
        field_name="element_selector", lookup_expr="icontains"
    )

    class Meta:
        model  = ClickMetric
        fields = ["category", "page_url_contains", "element_selector_contains"]


class StayTimeFilter(django_filters.FilterSet):
    """
    Filterable fields for the StayTime list endpoint.

    Query-string examples:
      ?min_duration=30
      ?max_duration=300
      ?is_active_time=true
    """

    min_duration = django_filters.NumberFilter(
        field_name="duration_seconds", lookup_expr="gte"
    )
    max_duration = django_filters.NumberFilter(
        field_name="duration_seconds", lookup_expr="lte"
    )
    is_active_time = django_filters.BooleanFilter()
    page_url_contains = django_filters.CharFilter(
        field_name="page_url", lookup_expr="icontains"
    )

    created_after  = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model  = StayTime
        fields = ["is_active_time", "page_url_contains"]


class EngagementScoreFilter(django_filters.FilterSet):
    """
    Filterable fields for the EngagementScore list endpoint.

    Query-string examples:
      ?tier=high
      ?date_after=2024-01-01
      ?score_min=70
    """

    tier       = django_filters.MultipleChoiceFilter(choices=EngagementTier.choices)
    date_after  = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_before = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    score_min   = django_filters.NumberFilter(field_name="score", lookup_expr="gte")
    score_max   = django_filters.NumberFilter(field_name="score", lookup_expr="lte")

    class Meta:
        model  = EngagementScore
        fields = ["tier"]
