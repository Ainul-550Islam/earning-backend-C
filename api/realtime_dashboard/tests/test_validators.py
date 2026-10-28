"""
Tests for Real-time Dashboard custom validators (validators.py).

Each validator is tested for:
- Valid input passes through unchanged
- Invalid input raises serializers.ValidationError with a useful message
"""
import pytest
from rest_framework import serializers

from api.realtime_dashboard.validators import (
    validate_json_metadata,
    validate_tags_list,
    validate_positive_integer,
    validate_widget_configuration,
    validate_name_no_special_chars,
    validate_thresholds,
    validate_widget_dimensions,
)


# ─── validate_json_metadata ──────────────────────────────────────────────────

class TestValidateJsonMetadata:

    def test_valid_dict_passes(self):
        value = {'key': 'value', 'nested': {'a': 1}}
        assert validate_json_metadata(value) == value

    def test_empty_dict_passes(self):
        assert validate_json_metadata({}) == {}

    def test_list_rejected(self):
        with pytest.raises(serializers.ValidationError, match='dict'):
            validate_json_metadata([1, 2, 3])

    def test_string_rejected(self):
        with pytest.raises(serializers.ValidationError, match='dict'):
            validate_json_metadata('{"key": "val"}')

    def test_none_rejected(self):
        with pytest.raises(serializers.ValidationError, match='dict'):
            validate_json_metadata(None)

    def test_integer_rejected(self):
        with pytest.raises(serializers.ValidationError, match='dict'):
            validate_json_metadata(42)


# ─── validate_tags_list ──────────────────────────────────────────────────────

class TestValidateTagsList:

    def test_valid_list_passes(self):
        value = ['tag1', 'tag2', 'tag-three']
        assert validate_tags_list(value) == value

    def test_empty_list_passes(self):
        assert validate_tags_list([]) == []

    def test_dict_rejected(self):
        with pytest.raises(serializers.ValidationError, match='list'):
            validate_tags_list({'tag': 'value'})

    def test_numeric_tag_rejected(self):
        with pytest.raises(serializers.ValidationError, match='string'):
            validate_tags_list(['valid', 123])

    def test_empty_string_tag_rejected(self):
        with pytest.raises(serializers.ValidationError, match='empty'):
            validate_tags_list(['valid', ''])

    def test_whitespace_only_tag_rejected(self):
        with pytest.raises(serializers.ValidationError, match='empty'):
            validate_tags_list(['valid', '   '])


# ─── validate_positive_integer ───────────────────────────────────────────────

class TestValidatePositiveInteger:

    def test_positive_value_passes(self):
        assert validate_positive_integer(1) == 1
        assert validate_positive_integer(100) == 100

    def test_none_passes(self):
        assert validate_positive_integer(None) is None

    def test_zero_rejected(self):
        with pytest.raises(serializers.ValidationError, match='positive'):
            validate_positive_integer(0)

    def test_negative_rejected(self):
        with pytest.raises(serializers.ValidationError, match='positive'):
            validate_positive_integer(-5)


# ─── validate_widget_configuration ──────────────────────────────────────────

class TestValidateWidgetConfiguration:

    def test_valid_dict_passes(self):
        value = {'color': 'blue', 'chart_type': 'bar'}
        assert validate_widget_configuration(value) == value

    def test_empty_dict_passes(self):
        assert validate_widget_configuration({}) == {}

    def test_list_rejected(self):
        with pytest.raises(serializers.ValidationError, match='dict'):
            validate_widget_configuration(['item'])

    def test_string_rejected(self):
        with pytest.raises(serializers.ValidationError, match='dict'):
            validate_widget_configuration('config')


# ─── validate_name_no_special_chars ─────────────────────────────────────────

class TestValidateNameNoSpecialChars:

    def test_alphanumeric_passes(self):
        """
        v1.5.0: validate_name_no_special_chars() is now typed -> None
        (DRF validators are conventionally Callable[[T], None] — the
        return value was never consumed by either call site, both of
        which use it via validators=[...]). These now assert "does not
        raise" instead of checking a return value that no longer exists.
        """
        validate_name_no_special_chars('CPU Usage')
        validate_name_no_special_chars('metric-1')
        validate_name_no_special_chars('widget_v2')

    def test_empty_string_passes(self):
        validate_name_no_special_chars('')

    def test_special_chars_rejected(self):
        with pytest.raises(serializers.ValidationError):
            validate_name_no_special_chars('<script>alert(1)</script>')

    def test_angle_brackets_rejected(self):
        with pytest.raises(serializers.ValidationError):
            validate_name_no_special_chars('Widget <v2>')

    def test_semicolon_rejected(self):
        with pytest.raises(serializers.ValidationError):
            validate_name_no_special_chars('widget; DROP TABLE widgets;')


# ─── validate_thresholds ─────────────────────────────────────────────────────

class TestValidateThresholds:

    def test_warning_less_than_critical_passes(self):
        # Should not raise
        validate_thresholds(warning=50.0, critical=90.0)

    def test_both_none_passes(self):
        validate_thresholds(warning=None, critical=None)

    def test_only_warning_set_passes(self):
        validate_thresholds(warning=50.0, critical=None)

    def test_only_critical_set_passes(self):
        validate_thresholds(warning=None, critical=90.0)

    def test_warning_equal_critical_rejected(self):
        with pytest.raises(serializers.ValidationError, match='warning_threshold'):
            validate_thresholds(warning=80.0, critical=80.0)

    def test_warning_greater_than_critical_rejected(self):
        with pytest.raises(serializers.ValidationError, match='warning_threshold'):
            validate_thresholds(warning=95.0, critical=80.0)


# ─── validate_widget_dimensions ─────────────────────────────────────────────

class TestValidateWidgetDimensions:

    def test_valid_dimensions_pass(self):
        # Should not raise
        validate_widget_dimensions(width=6, height=4)
        validate_widget_dimensions(width=1, height=1)
        validate_widget_dimensions(width=12, height=24)

    def test_both_none_passes(self):
        validate_widget_dimensions(width=None, height=None)

    def test_width_zero_rejected(self):
        with pytest.raises(serializers.ValidationError, match='width'):
            validate_widget_dimensions(width=0, height=4)

    def test_width_too_large_rejected(self):
        with pytest.raises(serializers.ValidationError, match='width'):
            validate_widget_dimensions(width=13, height=4)

    def test_height_zero_rejected(self):
        with pytest.raises(serializers.ValidationError, match='height'):
            validate_widget_dimensions(width=6, height=0)

    def test_height_too_large_rejected(self):
        with pytest.raises(serializers.ValidationError, match='height'):
            validate_widget_dimensions(width=6, height=25)
