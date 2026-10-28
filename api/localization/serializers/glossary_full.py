# serializers/glossary_full.py — full TranslationGlossary serializer (root term)
from rest_framework import serializers


class TranslationGlossarySerializer(serializers.ModelSerializer):
    """Serializer for the glossary root term (TranslationGlossary).
    Not to be confused with GlossaryTermSerializer (same model, legacy name)
    or TranslationGlossaryEntrySerializer (per-language translations).
    """
    source_language_code = serializers.CharField(
        source='source_language.code', read_only=True
    )
    entry_count = serializers.SerializerMethodField()
    approved_by_email = serializers.SerializerMethodField()

    def get_entry_count(self, obj):
        try:
            return obj.entries.count()
        except Exception:
            return 0

    def get_approved_by_email(self, obj):
        return getattr(obj.approved_by, 'email', None) if obj.approved_by else None

    class Meta:
        from ..models.translation import TranslationGlossary
        model = TranslationGlossary
        fields = [
            'id', 'created_at', 'updated_at',
            'source_language', 'source_language_code',
            'source_term', 'definition',
            'domain', 'part_of_speech',
            'is_do_not_translate', 'is_brand_term',
            'is_forbidden', 'forbidden_reason',
            'notes', 'tags', 'usage_count',
            'approved_by', 'approved_by_email',
            'entry_count',
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'usage_count', 'approved_by',
        ]
        extra_kwargs = {
            'source_language': {'write_only': True},
            'approved_by': {'write_only': True, 'required': False},
        }
