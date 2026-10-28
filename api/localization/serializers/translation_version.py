# serializers/translation_version.py
from rest_framework import serializers


class TranslationVersionSerializer(serializers.ModelSerializer):
    changed_by_email = serializers.SerializerMethodField()
    translation_key = serializers.SerializerMethodField()
    translation_language = serializers.SerializerMethodField()

    def get_changed_by_email(self, obj):
        if obj.changed_by:
            return getattr(obj.changed_by, 'email', None)
        return None

    def get_translation_key(self, obj):
        try:
            return obj.translation.key.key
        except Exception:
            return None

    def get_translation_language(self, obj):
        try:
            return obj.translation.language.code
        except Exception:
            return None

    class Meta:
        from ..models.translation import TranslationVersion
        model = TranslationVersion
        fields = [
            'id', 'created_at',
            'translation',
            'translation_key', 'translation_language',
            'version_number',
            'value', 'value_plural',
            'changed_by', 'changed_by_email',
            'change_reason',
            'source',
            'is_approved',
            'word_count', 'char_count',
            'diff_from_previous',
        ]
        read_only_fields = [
            'id', 'created_at', 'version_number',
            'word_count', 'char_count', 'diff_from_previous',
        ]
        extra_kwargs = {
            'translation': {'write_only': True},
            'changed_by': {'write_only': True, 'required': False},
        }
