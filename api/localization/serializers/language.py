# serializers/language.py
from rest_framework import serializers


class LanguageSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        from ..models.core import Language
        model = Language
        fields = [
            'id', 'created_at', 'updated_at',
            'code', 'name', 'name_native',
            'is_active', 'is_default', 'is_rtl',
            'flag_emoji', 'locale_code',
            'display_name',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_display_name(self, obj):
        try:
            return obj.get_safe_display()
        except Exception:
            return obj.name

    def validate_code(self, value):
        if value and len(value) < 2:
            raise serializers.ValidationError(
                'Language code must be at least 2 characters'
            )
        return value.lower()


class LanguageDetailSerializer(LanguageSerializer):
    translations_count = serializers.SerializerMethodField()

    class Meta(LanguageSerializer.Meta):
        fields = LanguageSerializer.Meta.fields + ['translations_count']

    def get_translations_count(self, obj):
        try:
            return obj.translations.filter(is_approved=True).count()
        except Exception:
            return 0


class LanguageMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.core import Language
        model = Language
        fields = ['code', 'name', 'flag_emoji', 'is_rtl']
