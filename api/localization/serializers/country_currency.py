# serializers/country_currency.py
from rest_framework import serializers


class CountryCurrencySerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source='country.code', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    currency_code = serializers.CharField(source='currency.code', read_only=True)
    currency_name = serializers.CharField(source='currency.name', read_only=True)
    currency_symbol = serializers.CharField(source='currency.symbol', read_only=True)

    class Meta:
        from ..models.geo import CountryCurrency
        model = CountryCurrency
        fields = [
            'id', 'created_at', 'updated_at',
            'country', 'country_code', 'country_name',
            'currency', 'currency_code', 'currency_name', 'currency_symbol',
            'is_primary', 'is_legal_tender', 'is_accepted',
            'introduced_date', 'withdrawn_date',
            'notes',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'country': {'write_only': True},
            'currency': {'write_only': True},
        }
