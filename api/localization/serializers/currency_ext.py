# serializers/currency_ext.py
from rest_framework import serializers

class ExchangeRateProviderSerializer(serializers.ModelSerializer):
    base_currency_code = serializers.CharField(source='base_currency.code', read_only=True, default=None)
    class Meta:
        from ..models.currency import ExchangeRateProvider
        model = ExchangeRateProvider
        exclude = ['api_key']
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_fetch_at',
                            'last_success_at', 'total_requests', 'failed_requests', 'requests_this_month']

class CurrencyFormatSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    language_code = serializers.CharField(source='language.code', read_only=True)
    class Meta:
        from ..models.currency import CurrencyFormat
        model = CurrencyFormat
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class CurrencyConversionLogSerializer(serializers.ModelSerializer):
    from_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_code = serializers.CharField(source='to_currency.code', read_only=True)
    class Meta:
        from ..models.currency import CurrencyConversionLog
        model = CurrencyConversionLog
        fields = '__all__'
        read_only_fields = ['id', 'created_at']
