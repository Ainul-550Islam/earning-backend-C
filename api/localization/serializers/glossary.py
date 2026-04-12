# serializers/glossary.py
from rest_framework import serializers

class GlossaryTermSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.translation import TranslationGlossary
        model = TranslationGlossary
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'usage_count']
