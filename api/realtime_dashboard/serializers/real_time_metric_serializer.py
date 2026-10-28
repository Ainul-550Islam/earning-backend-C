"""
Real-time Metric serializer for Real-time Dashboard Backend.

WIRED (v1.1.0): utils.py defined format_metric_value, calculate_metric_delta,
calculate_metric_percentage, and check_metric_thresholds but they were never
called from any serializer or view. These are now exposed as SerializerMethodFields
so API consumers receive pre-computed display values in every metric response:

    {
        "id": 1,
        "name": "CPU Usage",
        "value": 87.3,
        "unit": "%",
        "formatted_value": "87.3 %",      ← format_metric_value
        "delta": 2.1,                      ← calculate_metric_delta
        "delta_percentage": 2.47,          ← calculate_metric_percentage
        "threshold_status": "warning",     ← check_metric_thresholds
        ...
    }
"""
from rest_framework import serializers

from ..models.real_time_metric import RealTimeMetric
from ..utils import (
    format_metric_value,
    calculate_metric_delta,
    calculate_metric_percentage,
    check_metric_thresholds,
)
from ..validators import (
    validate_json_metadata,
    validate_tags_list,
    validate_thresholds,
)
from .base_serializer import BaseSerializer


class RealTimeMetricSerializer(BaseSerializer):
    """
    Full serializer for RealTimeMetric — used on create / retrieve / update.

    Computed read-only fields (SerializerMethodField):
        formatted_value   — value with unit appended, e.g. "87.3 %"
        delta             — current minus previous_value (0.0 if no history)
        delta_percentage  — percentage change from previous_value (0.0 if no history)
        threshold_status  — 'normal' | 'warning' | 'critical'
    """

    metadata = serializers.JSONField(
        default=dict,
        validators=[validate_json_metadata],
    )
    tags = serializers.JSONField(
        default=list,  # type: ignore[arg-type]  # DRF stub types default as Mapping-only; list is valid
        validators=[validate_tags_list],
    )

    # ── Computed display fields ────────────────────────────────────────────────

    formatted_value = serializers.SerializerMethodField(
        help_text="Value with unit appended. e.g. '87.3 %'. Empty unit → plain number string."
    )
    delta = serializers.SerializerMethodField(
        help_text="Absolute change from previous_value. 0.0 when previous_value is None."
    )
    delta_percentage = serializers.SerializerMethodField(
        help_text="Percentage change from previous_value. 0.0 when previous_value is None or 0."
    )
    threshold_status = serializers.SerializerMethodField(
        help_text="'critical' if value ≥ critical_threshold, 'warning' if ≥ warning_threshold, else 'normal'."
    )

    class Meta:
        model = RealTimeMetric
        fields = [
            'id', 'name', 'description', 'metric_type', 'status', 'value',
            'previous_value', 'unit', 'warning_threshold', 'critical_threshold',
            # computed
            'formatted_value', 'delta', 'delta_percentage', 'threshold_status',
            # timestamps
            'last_updated', 'metadata', 'tags', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'last_updated',
            'formatted_value', 'delta', 'delta_percentage', 'threshold_status',
        ]

    def validate(self, attrs):
        """Cross-field: warning_threshold must be less than critical_threshold."""
        validate_thresholds(
            attrs.get('warning_threshold'),
            attrs.get('critical_threshold'),
        )
        return attrs

    # ── SerializerMethodField implementations ─────────────────────────────────

    def get_formatted_value(self, obj: RealTimeMetric) -> str:
        """
        Format value with unit for display.
        Delegates to utils.format_metric_value — single implementation,
        no duplication in templates or frontend helpers.
        """
        return format_metric_value(obj.value, obj.unit or '')

    def get_delta(self, obj: RealTimeMetric) -> float:
        """
        Absolute change: current_value - previous_value.
        Returns 0.0 when previous_value is None (first reading).
        """
        return calculate_metric_delta(obj.value, obj.previous_value)

    def get_delta_percentage(self, obj: RealTimeMetric) -> float:
        """
        Percentage change: ((current - previous) / previous) * 100.
        Returns 0.0 when previous_value is None or zero (division guard).
        """
        return round(calculate_metric_percentage(obj.value, obj.previous_value), 2)

    def get_threshold_status(self, obj: RealTimeMetric) -> str:
        """
        Threshold severity: 'critical', 'warning', or 'normal'.
        Delegates to utils.check_metric_thresholds for the comparison logic.
        """
        return check_metric_thresholds(
            obj.value,
            warning=obj.warning_threshold,
            critical=obj.critical_threshold,
        )


class RealTimeMetricListSerializer(BaseSerializer):
    """
    Compact serializer for list endpoints — omits heavy fields.
    Includes threshold_status so clients can show alert badges in lists
    without fetching the full detail object.
    """

    threshold_status = serializers.SerializerMethodField()

    class Meta:
        model = RealTimeMetric
        fields = [
            'id', 'name', 'metric_type', 'status', 'value', 'unit',
            'threshold_status', 'last_updated',
        ]
        read_only_fields = ['last_updated', 'threshold_status']

    def get_threshold_status(self, obj: RealTimeMetric) -> str:
        return check_metric_thresholds(
            obj.value,
            warning=obj.warning_threshold,
            critical=obj.critical_threshold,
        )
