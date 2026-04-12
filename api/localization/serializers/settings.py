# serializers/settings.py
from rest_framework import serializers

class LocalizationConfigSerializer(serializers.ModelSerializer):
    default_language_code = serializers.CharField(source='default_language.code', read_only=True)
    default_currency_code = serializers.CharField(source='default_currency.code', read_only=True)
    supported_language_codes = serializers.SerializerMethodField()
    def get_supported_language_codes(self, obj):
        return list(obj.supported_languages.values_list('code', flat=True))
    class Meta:
        from ..models.settings import LocalizationConfig
        model = LocalizationConfig
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class DateTimeFormatSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)
    country_code = serializers.CharField(source='country.code', read_only=True, default=None)
    class Meta:
        from ..models.settings import DateTimeFormat
        model = DateTimeFormat
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class NumberFormatSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)
    class Meta:
        from ..models.settings import NumberFormat
        model = NumberFormat
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class AddressFormatSerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source='country.code', read_only=True)
    class Meta:
        from ..models.settings import AddressFormat
        model = AddressFormat
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
