# serializers/currency.py
from rest_framework import serializers

class CurrencySerializer(serializers.ModelSerializer):
    formatted_examples = serializers.SerializerMethodField()
    class Meta:
        from ..models.core import Currency
        model = Currency
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
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
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
