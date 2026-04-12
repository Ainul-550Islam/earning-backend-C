# serializers/language.py
from rest_framework import serializers

class LanguageSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    class Meta:
        from ..models.core import Language
        model = Language
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'coverage_percent']
    def get_display_name(self, obj):
        return obj.get_safe_display() if obj else ''
    def validate_code(self, value):
        if value and len(value) < 2:
            raise serializers.ValidationError("Language code must be at least 2 characters")
        return value.lower()

class LanguageDetailSerializer(LanguageSerializer):
    translations_count = serializers.SerializerMethodField()
    def get_translations_count(self, obj):
        try:
            return obj.translations.filter(is_approved=True).count()
        except Exception:
            return 0
    class Meta(LanguageSerializer.Meta):
        fields = '__all__'

class LanguageMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.core import Language
        model = Language
        fields = ['code', 'name', 'flag_emoji', 'is_rtl', 'text_direction']
