# serializers/geo.py
from rest_framework import serializers


class RegionSerializer(serializers.ModelSerializer):
    full_path = serializers.CharField(read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True, default=None)
    country_code = serializers.CharField(source='country.code', read_only=True, default=None)

    class Meta:
        from ..models.geo import Region
        model = Region
        fields = [
            'id', 'created_at', 'updated_at',
            'name', 'name_native', 'code', 'region_type',
            'parent', 'parent_name',
            'country', 'country_code',
            'latitude', 'longitude', 'population',
            'is_active', 'full_path',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'parent': {'write_only': True, 'required': False},
            'country': {'write_only': True, 'required': False},
        }


class CountryLanguageSerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source='country.code', read_only=True)
    language_code = serializers.CharField(source='language.code', read_only=True)
    language_name = serializers.CharField(source='language.name', read_only=True)

    class Meta:
        from ..models.geo import CountryLanguage
        model = CountryLanguage
        fields = [
            'id', 'created_at', 'updated_at',
            'country', 'country_code',
            'language', 'language_code', 'language_name',
            'is_official', 'is_national', 'is_regional', 'is_minority',
            'speaker_percentage', 'status', 'sort_order',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'country': {'write_only': True},
            'language': {'write_only': True},
        }


class GeoIPMappingSerializer(serializers.ModelSerializer):
    country_code_display = serializers.CharField(source='country.code', read_only=True, default=None)

    class Meta:
        from ..models.geo import GeoIPMapping
        model = GeoIPMapping
        fields = [
            'id', 'created_at', 'updated_at',
            'ip_start', 'ip_end',
            'country', 'country_code', 'country_code_display',
            'region_name', 'city_name', 'timezone',
            'latitude', 'longitude',
            'is_vpn', 'is_proxy', 'is_tor',
            'threat_score', 'source',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'country': {'write_only': True, 'required': False}}


class PhoneFormatSerializer(serializers.ModelSerializer):
    country_code_display = serializers.CharField(source='country.code', read_only=True)

    class Meta:
        from ..models.geo import PhoneFormat
        model = PhoneFormat
        fields = [
            'id', 'created_at', 'updated_at',
            'country', 'country_code_display',
            'country_dial_code', 'national_prefix',
            'mobile_pattern', 'landline_pattern',
            'mobile_length', 'landline_length',
            'display_format', 'input_mask',
            'example_mobile', 'example_landline',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {'country': {'write_only': True}}
