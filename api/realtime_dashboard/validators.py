"""
Reusable serializer validators for Real-time Dashboard Backend.

Each validator is a callable that DRF serializers call during .is_valid().
Validators defined here are the single owner of field-level and
object-level validation rules. Serializers import from here; business
rules are never duplicated across multiple serializers.

Usage:
    from ..validators import validate_json_metadata, validate_tags_list
    from rest_framework import serializers

    class MySerializer(serializers.ModelSerializer):
        metadata = serializers.JSONField(validators=[validate_json_metadata])
        tags = serializers.JSONField(validators=[validate_tags_list])
"""
from rest_framework import serializers


# ── Field validators ─────────────────────────────────────────────────────────

def validate_json_metadata(value):
    """
    Validate that metadata is a plain dict (not a list or scalar).

    Models define `metadata = models.JSONField(default=dict)` — allowing a
    list or string here would break any code that does metadata.get(...).
    """
    if not isinstance(value, dict):
        raise serializers.ValidationError(
            f'metadata must be a JSON object (dict), got {type(value).__name__}.'
        )
    return value


def validate_tags_list(value):
    """
    Validate that tags is a list of non-empty strings.

    Models define `tags = models.JSONField(default=list)`. A tag must be
    a string; numeric tags make filtering/display logic ambiguous.
    """
    if not isinstance(value, list):
        raise serializers.ValidationError(
            f'tags must be a JSON array (list), got {type(value).__name__}.'
        )
    for i, tag in enumerate(value):
        if not isinstance(tag, str):
            raise serializers.ValidationError(
                f'tags[{i}] must be a string, got {type(tag).__name__}.'
            )
        if not tag.strip():
            raise serializers.ValidationError(
                f'tags[{i}] must not be an empty or whitespace-only string.'
            )
    return value


def validate_positive_integer(value):
    """Validate that an integer field is strictly positive (> 0)."""
    if value is not None and value <= 0:
        raise serializers.ValidationError('Value must be a positive integer greater than zero.')
    return value


def validate_widget_configuration(value):
    """
    Validate that widget configuration is a dict.

    Configuration is stored as JSONField(default=dict); a non-dict value
    breaks every part of the codebase that does configuration.get(...).
    """
    if not isinstance(value, dict):
        raise serializers.ValidationError(
            f'configuration must be a JSON object (dict), got {type(value).__name__}.'
        )
    return value


def validate_name_no_special_chars(value: str) -> None:
    """
    Validate that a name contains only alphanumeric characters, spaces,
    hyphens, and underscores. Prevents XSS-risk characters from entering
    names that are later reflected in WebSocket payloads or admin pages.

    v1.5.0: signature was `(value: str) -> str` with a trailing
    `return value`, but every call site uses this only via
    `validators=[validate_name_no_special_chars]`, where DRF discards
    the return value — validators in that list are conventionally
    Callable[[T], None] (raise to reject, return nothing to accept).
    The stale `-> str` was flagged by mypy as an incompatible type at
    both of this function's call sites (dashboard_widget_serializer.py,
    dashboard_layout_serializer.py); fixed at the source rather than
    silencing it twice downstream.
    """
    import re
    if value and not re.match(r'^[\w\s\-]+$', value):
        raise serializers.ValidationError(
            'Name may only contain letters, numbers, spaces, hyphens, and underscores.'
        )


# ── Cross-field / object-level validators ────────────────────────────────────

def validate_thresholds(warning, critical):
    """
    Validate that warning_threshold < critical_threshold when both are set.

    Used as a cross-field check in RealTimeMetricSerializer.validate().
    """
    if warning is not None and critical is not None:
        if warning >= critical:
            raise serializers.ValidationError(
                'warning_threshold must be less than critical_threshold.'
            )


def validate_widget_dimensions(width, height):
    """
    Validate that widget width and height are within the 12-column grid.

    Width must be 1–12 (full row); height must be 1–24 (max 24 grid units).
    """
    if width is not None and not (1 <= width <= 12):
        raise serializers.ValidationError(
            {'width': 'Widget width must be between 1 and 12 (grid columns).'}
        )
    if height is not None and not (1 <= height <= 24):
        raise serializers.ValidationError(
            {'height': 'Widget height must be between 1 and 24 (grid rows).'}
        )
