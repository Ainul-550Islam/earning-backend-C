# serializers/currency.py
from rest_framework import serializers


class CurrencySerializer(serializers.ModelSerializer):
    formatted_examples = serializers.SerializerMethodField()

    class Meta:
        from ..models.core import Currency
        model = Currency
        fields = [
            'id', 'created_at', 'updated_at',
            'code', 'name', 'symbol', 'symbol_native',
            'decimal_digits', 'is_active', 'is_default',
            'exchange_rate', 'exchange_rate_updated_at',
            'formatted_examples',
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'exchange_rate_updated_at', 'formatted_examples',
        ]

    def get_formatted_examples(self, obj):
        try:
            return {str(a): obj.format_amount(a) for a in [1, 100, 1000]}
        except Exception:
            return {}


class CurrencyMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.core import Currency
        model = Currency
        fields = ['code', 'symbol', 'name']


class CurrencyExchangeRateSerializer(serializers.ModelSerializer):
    from_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_code = serializers.CharField(source='to_currency.code', read_only=True)

    class Meta:
        from ..models.currency import ExchangeRate
        model = ExchangeRate
        fields = [
            'id', 'created_at', 'updated_at',
            'from_currency', 'from_code',
            'to_currency', 'to_code',
            'rate', 'bid_rate', 'ask_rate', 'mid_rate',
            'date', 'fetched_at', 'valid_until',
            'source', 'is_official', 'change_percent',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'fetched_at']
        extra_kwargs = {
            'from_currency': {'write_only': True},
            'to_currency': {'write_only': True},
        }
