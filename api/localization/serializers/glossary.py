# serializers/glossary.py
from rest_framework import serializers

class GlossaryTermSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.translation import TranslationGlossary
        model = TranslationGlossary
        fields = [
            'id', 'created_at', 'updated_at',
            'source_language', 'source_term', 'definition',
            'domain', 'part_of_speech',
            'is_do_not_translate', 'is_brand_term', 'is_forbidden',
            'forbidden_reason', 'notes', 'tags', 'usage_count',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'usage_count']