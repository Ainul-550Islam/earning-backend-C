# serializers/translation_memory.py
from rest_framework import serializers

class TranslationMemorySerializer(serializers.ModelSerializer):
    source_lang = serializers.CharField(source='source_language.code', read_only=True)
    target_lang = serializers.CharField(source='target_language.code', read_only=True)
    class Meta:
        from ..models.translation import TranslationMemory
        model = TranslationMemory
        fields = [
            'id', 'created_at', 'updated_at',
            'source_language', 'target_language',
            'source_text', 'target_text',
            'domain', 'context',
            'usage_count', 'is_approved', 'quality_rating',
            'source_word_count', 'target_word_count',
            'client', 'project', 'tags', 'last_used_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'source_hash', 'usage_count', 'source_word_count', 'target_word_count']