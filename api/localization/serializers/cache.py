# serializers/cache.py
from rest_framework import serializers

class TranslationCacheSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.translation import TranslationCache
        model = TranslationCache
        fields = ['id', 'created_at', 'updated_at', 'language_code', 'cache_key', 'cache_data', 'expires_at', 'hits']
        read_only_fields = ['id', 'created_at', 'updated_at', 'hits']