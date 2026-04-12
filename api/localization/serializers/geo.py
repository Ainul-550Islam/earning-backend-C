# serializers/geo.py
from rest_framework import serializers

class RegionSerializer(serializers.ModelSerializer):
    full_path = serializers.CharField(read_only=True)
    class Meta:
        from ..models.geo import Region
        model = Region
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class CountryLanguageSerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source='country.code', read_only=True)
    language_code = serializers.CharField(source='language.code', read_only=True)
    class Meta:
        from ..models.geo import CountryLanguage
        model = CountryLanguage
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class GeoIPMappingSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.geo import GeoIPMapping
        model = GeoIPMapping
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class PhoneFormatSerializer(serializers.ModelSerializer):
    country_code_display = serializers.CharField(source='country.code', read_only=True)
    class Meta:
        from ..models.geo import PhoneFormat
        model = PhoneFormat
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
