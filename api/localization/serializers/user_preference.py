# serializers/user_preference.py
from rest_framework import serializers


class UserLanguagePreferenceSerializer(serializers.ModelSerializer):
    primary_language_code = serializers.CharField(
        source='primary_language.code', read_only=True, default=None
    )
    ui_language_code = serializers.CharField(
        source='ui_language.code', read_only=True, default=None
    )
    content_language_code = serializers.CharField(
        source='content_language.code', read_only=True, default=None
    )
    preferred_language_codes = serializers.SerializerMethodField()
    effective_language_code = serializers.SerializerMethodField()

    def get_preferred_language_codes(self, obj):
        return list(obj.preferred_languages.values_list('code', flat=True))

    def get_effective_language_code(self, obj):
        lang = obj.effective_language
        return getattr(lang, 'code', None) if lang else None

    class Meta:
        from ..models.core import UserLanguagePreference
        model = UserLanguagePreference
        fields = [
            'id', 'created_at', 'updated_at',
            'user',
            'primary_language', 'primary_language_code',
            'ui_language', 'ui_language_code',
            'content_language', 'content_language_code',
            'auto_translate',
            'preferred_languages', 'preferred_language_codes',
            'last_used_languages',
            'effective_language_code',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user']
        extra_kwargs = {
            'primary_language': {'write_only': True, 'required': False},
            'ui_language': {'write_only': True, 'required': False},
            'content_language': {'write_only': True, 'required': False},
            'preferred_languages': {'write_only': True, 'required': False},
        }
