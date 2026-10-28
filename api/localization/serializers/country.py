# serializers/country.py
from rest_framework import serializers


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.core import Country
        model = Country
        fields = [
            'id', 'created_at', 'updated_at',
            'code', 'code_alpha3',
            'name', 'native_name',
            'phone_code', 'phone_digits',
            'flag_emoji', 'flag_svg_url',
            'is_active',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CountryMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.core import Country
        model = Country
        fields = ['id', 'code', 'code_alpha3', 'name', 'native_name',
                  'phone_code', 'flag_emoji', 'is_active']
