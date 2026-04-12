# serializers/country.py
from rest_framework import serializers

class CountrySerializer(serializers.ModelSerializer):
    phone_code_display = serializers.SerializerMethodField()
    class Meta:
        from ..models.core import Country
        model = Country
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
    def get_phone_code_display(self, obj):
        return obj.get_safe_phone_code() if obj else ''

class CountryMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.core import Country
        model = Country
        fields = ['code', 'name', 'flag_emoji', 'phone_code', 'continent']
