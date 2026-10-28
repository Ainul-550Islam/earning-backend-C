# serializers/glossary_entry.py
from rest_framework import serializers


class TranslationGlossaryEntrySerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)
    language_name = serializers.CharField(source='language.name', read_only=True)
    glossary_name = serializers.CharField(source='glossary.source_term', read_only=True)
    approved_by_email = serializers.SerializerMethodField()

    def get_approved_by_email(self, obj):
        if obj.approved_by:
            return getattr(obj.approved_by, 'email', None)
        return None

    class Meta:
        from ..models.translation import TranslationGlossaryEntry
        model = TranslationGlossaryEntry
        fields = [
            'id', 'created_at', 'updated_at',
            'glossary', 'glossary_name',
            'language', 'language_code', 'language_name',
            'translated_term',
            'alternative_terms',
            'forbidden_terms',
            'notes',
            'is_approved',
            'approved_by', 'approved_by_email',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'glossary': {'write_only': True},
            'language': {'write_only': True},
            'approved_by': {'write_only': True, 'required': False},
        }
