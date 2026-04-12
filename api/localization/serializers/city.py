# serializers/city.py
from rest_framework import serializers

class CitySerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source='country.code', read_only=True)
    country_name = serializers.CharField(source='country.name', read_only=True)
    class Meta:
        from ..models.core import City
        model = City
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class CityMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.core import City
        model = City
        fields = ['id', 'name', 'native_name', 'is_capital']
