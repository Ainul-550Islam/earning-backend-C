# serializers/extra.py — Remaining serializers
from rest_framework import serializers
from .base import BaseModelSerializer


class ExchangeRateSerializer(BaseModelSerializer):
    from_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_code   = serializers.CharField(source='to_currency.code', read_only=True)
    class Meta:
        from ..models.currency import ExchangeRate
        model = ExchangeRate
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class AutoTranslateSerializer(serializers.Serializer):
    """Request serializer for auto-translate endpoint"""
    language_code = serializers.CharField(max_length=10)
    namespace     = serializers.CharField(max_length=100, default='', allow_blank=True)
    limit         = serializers.IntegerField(default=50, min_value=1, max_value=500)
    dry_run       = serializers.BooleanField(default=False)
    provider      = serializers.ChoiceField(
        choices=['google', 'deepl', 'azure', 'amazon', 'openai'],
        default='google'
    )
    source_language = serializers.CharField(max_length=10, default='en')

    def validate_language_code(self, value):
        from ..models.core import Language
        if not Language.objects.filter(code=value, is_active=True).exists():
            raise serializers.ValidationError(f"Language '{value}' not found or inactive")
        return value


class ImportExportSerializer(serializers.Serializer):
    """Import/Export serializer"""
    language_code  = serializers.CharField(max_length=10)
    format         = serializers.ChoiceField(choices=['json', 'po', 'xliff', 'csv'], default='json')
    namespace      = serializers.CharField(max_length=100, default='', allow_blank=True)
    approved_only  = serializers.BooleanField(default=True)
    include_empty  = serializers.BooleanField(default=False)

    # For import
    content = serializers.CharField(required=False, allow_blank=True,
                                    help_text="File content as string (for import)")
    data    = serializers.DictField(required=False, allow_empty=True,
                                    help_text="JSON dict (for JSON import)")


class AdminSerializer(serializers.Serializer):
    """Admin bulk operation serializer"""
    operation = serializers.ChoiceField(choices=[
        'seed_languages', 'seed_countries', 'seed_currencies', 'seed_timezones',
        'clear_cache', 'recalculate_coverage', 'run_qa', 'update_rates',
        'build_packs', 'index_tm',
    ])
    confirm      = serializers.BooleanField(default=False)
    language_code = serializers.CharField(max_length=10, required=False, allow_blank=True)
    dry_run      = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if not attrs.get('confirm'):
            raise serializers.ValidationError("Set confirm=true to execute admin operations")
        return attrs


class PublicTranslationSerializer(serializers.Serializer):
    """Public translation response serializer (no auth)"""
    language      = serializers.CharField(read_only=True)
    language_code = serializers.CharField(read_only=True)
    is_rtl        = serializers.BooleanField(read_only=True)
    text_direction = serializers.CharField(read_only=True)
    bcp47         = serializers.CharField(read_only=True)
    translations  = serializers.DictField(read_only=True)
    count         = serializers.IntegerField(read_only=True)
    version       = serializers.CharField(read_only=True, default='v2')
    cached        = serializers.BooleanField(read_only=True, default=False)
    timestamp     = serializers.DateTimeField(read_only=True)
