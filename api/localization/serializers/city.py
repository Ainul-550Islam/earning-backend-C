# serializers/city.py
from rest_framework import serializers


class CitySerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source='country.code', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    timezone_name = serializers.CharField(source='timezone.name', read_only=True, default=None)

    class Meta:
        from ..models.core import City
        model = City
        fields = [
            'id', 'created_at', 'updated_at',
            'name', 'native_name',
            'country', 'country_code', 'country_name',
            'timezone', 'timezone_name',
            'latitude', 'longitude',
            'is_active', 'is_capital', 'population',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'country': {'write_only': True},
            'timezone': {'write_only': True, 'required': False},
        }


class CityMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.core import City
        model = City
        fields = ['id', 'name', 'native_name', 'is_capital']
