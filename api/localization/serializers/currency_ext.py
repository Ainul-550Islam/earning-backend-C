# serializers/currency_ext.py
from rest_framework import serializers


class ExchangeRateProviderSerializer(serializers.ModelSerializer):
    base_currency_code = serializers.CharField(
        source='base_currency.code', read_only=True, default=None
    )

    class Meta:
        from ..models.currency import ExchangeRateProvider
        model = ExchangeRateProvider
        # api_key intentionally excluded — never expose secrets via API
        fields = [
            'id', 'created_at', 'updated_at',
            'name', 'provider_type',
            'base_url', 'base_currency', 'base_currency_code',
            'is_active', 'is_default',
            'fetch_interval_minutes',
            'last_fetch_at', 'last_success_at', 'last_error',
            'total_requests', 'failed_requests',
            'rate_limit_per_month', 'requests_this_month',
            'priority',
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'last_fetch_at', 'last_success_at',
            'total_requests', 'failed_requests', 'requests_this_month',
        ]
        extra_kwargs = {'base_currency': {'write_only': True, 'required': False}}


class CurrencyFormatSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    language_code = serializers.CharField(
        source='language.code', read_only=True, default=None
    )
    country_code = serializers.CharField(
        source='country.code', read_only=True, default=None
    )

    class Meta:
        from ..models.currency import CurrencyFormat
        model = CurrencyFormat
        fields = [
            'id', 'created_at', 'updated_at',
            'currency', 'currency_code',
            'language', 'language_code',
            'country', 'country_code',
            'symbol_position', 'symbol_spacing',
            'thousands_separator', 'decimal_separator',
            'grouping_pattern', 'decimal_places',
            'negative_format', 'positive_format', 'zero_format',
            'rounding_rule', 'native_digits',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'currency': {'write_only': True},
            'language': {'write_only': True, 'required': False},
            'country': {'write_only': True, 'required': False},
        }


class CurrencyConversionLogSerializer(serializers.ModelSerializer):
    from_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_code = serializers.CharField(source='to_currency.code', read_only=True)

    class Meta:
        from ..models.currency import CurrencyConversionLog
        model = CurrencyConversionLog
        fields = [
            'id', 'created_at',
            'from_currency', 'from_code',
            'to_currency', 'to_code',
            'amount', 'converted_amount', 'rate_used', 'rate_source',
            'response_time_ms', 'was_cached',
            'error_occurred', 'error_message',
        ]
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'from_currency': {'write_only': True},
            'to_currency': {'write_only': True},
        }
