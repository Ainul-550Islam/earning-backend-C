# serializers/settings.py
from rest_framework import serializers


class LocalizationConfigSerializer(serializers.ModelSerializer):
    default_language_code = serializers.CharField(
        source='default_language.code', read_only=True
    )
    default_currency_code = serializers.CharField(
        source='default_currency.code', read_only=True, default=None
    )
    supported_language_codes = serializers.SerializerMethodField()

    def get_supported_language_codes(self, obj):
        return list(obj.supported_languages.values_list('code', flat=True))

    class Meta:
        from ..models.settings import LocalizationConfig
        model = LocalizationConfig
        fields = [
            'id', 'created_at', 'updated_at',
            'tenant_id',
            'default_language', 'default_language_code',
            'fallback_language',
            'default_currency', 'default_currency_code',
            'default_timezone',
            'detect_language_from_browser', 'detect_language_from_ip',
            'auto_translate_missing', 'auto_translate_provider',
            'require_translation_approval', 'show_untranslated_keys',
            'translation_cache_ttl', 'log_missing_translations',
            'enable_rtl_support', 'enable_translation_memory',
            'enable_glossary', 'enable_content_localization',
            'supported_languages', 'supported_language_codes',
            'supported_currencies', 'is_active',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'default_language': {'write_only': True, 'required': False},
            'fallback_language': {'write_only': True, 'required': False},
            'default_currency': {'write_only': True, 'required': False},
        }


class DateTimeFormatSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)
    country_code = serializers.CharField(
        source='country.code', read_only=True, default=None
    )

    class Meta:
        from ..models.settings import DateTimeFormat
        model = DateTimeFormat
        fields = [
            'id', 'created_at', 'updated_at',
            'language', 'language_code',
            'country', 'country_code',
            'calendar_system',
            'date_short', 'date_medium', 'date_long', 'date_full',
            'time_short', 'time_medium', 'time_long',
            'datetime_short',
            'first_day_of_week',
            'am_symbol', 'pm_symbol',
            'month_names', 'month_names_short',
            'day_names', 'day_names_short', 'day_names_min',
            'use_native_numerals',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'language': {'write_only': True},
            'country': {'write_only': True, 'required': False},
        }


class NumberFormatSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)
    country_code = serializers.CharField(
        source='country.code', read_only=True, default=None
    )

    class Meta:
        from ..models.settings import NumberFormat
        model = NumberFormat
        fields = [
            'id', 'created_at', 'updated_at',
            'language', 'language_code',
            'country', 'country_code',
            'decimal_symbol', 'grouping_symbol', 'grouping_size',
            'negative_sign', 'positive_sign',
            'percent_symbol',
            'min_fraction_digits', 'max_fraction_digits',
            'use_grouping', 'number_system',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'language': {'write_only': True},
            'country': {'write_only': True, 'required': False},
        }


class AddressFormatSerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source='country.code', read_only=True)

    class Meta:
        from ..models.settings import AddressFormat
        model = AddressFormat
        fields = [
            'id', 'created_at', 'updated_at',
            'country', 'country_code',
            'format_template', 'required_fields', 'optional_fields',
            'postal_code_label', 'postal_code_regex', 'postal_code_example',
            'state_label', 'district_label', 'city_label',
            'uses_state', 'uses_district', 'uses_postal_code',
            'uses_upazila', 'uses_thana', 'has_apartment_field',
            'address_line_count', 'example_address',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'country': {'write_only': True}}
