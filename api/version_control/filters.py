# =============================================================================
# version_control/filters.py
# =============================================================================

import django_filters

from .choices import MaintenanceStatus, Platform, PolicyStatus, UpdateType
from .models import AppUpdatePolicy, MaintenanceSchedule, PlatformRedirect


class AppUpdatePolicyFilter(django_filters.FilterSet):
    """
    ?platform=ios
    ?update_type=critical
    ?status=active
    ?target_version=2.0.0
    """
    platform    = django_filters.MultipleChoiceFilter(choices=Platform.choices)
    update_type = django_filters.MultipleChoiceFilter(choices=UpdateType.choices)
    status      = django_filters.MultipleChoiceFilter(choices=PolicyStatus.choices)
    target_version = django_filters.CharFilter(lookup_expr="exact")
    created_after  = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model  = AppUpdatePolicy
        fields = ["platform", "update_type", "status", "target_version"]


class MaintenanceScheduleFilter(django_filters.FilterSet):
    """
    ?status=active
    ?platform=android
    ?start_after=2024-01-01T00:00:00Z
    """
    status = django_filters.MultipleChoiceFilter(choices=MaintenanceStatus.choices)
    start_after  = django_filters.IsoDateTimeFilter(
        field_name="scheduled_start", lookup_expr="gte"
    )
    start_before = django_filters.IsoDateTimeFilter(
        field_name="scheduled_start", lookup_expr="lte"
    )

    class Meta:
        model  = MaintenanceSchedule
        fields = ["status"]


class PlatformRedirectFilter(django_filters.FilterSet):
    platform  = django_filters.MultipleChoiceFilter(choices=Platform.choices)
    is_active = django_filters.BooleanFilter()

    class Meta:
        model  = PlatformRedirect
        fields = ["platform", "is_active"]
