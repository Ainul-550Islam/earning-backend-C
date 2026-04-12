# serializers/cache.py
from rest_framework import serializers

class TranslationCacheSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.translation import TranslationCache
        model = TranslationCache
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'hits']
