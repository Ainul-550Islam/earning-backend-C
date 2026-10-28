# serializers/extra.py
from rest_framework import serializers
from .base import BaseModelSerializer


class ExchangeRateSerializer(BaseModelSerializer):
    from_code = serializers.CharField(source='from_currency.code', read_only=True)
    to_code = serializers.CharField(source='to_currency.code', read_only=True)

    class Meta:
        from ..models.currency import ExchangeRate
        model = ExchangeRate
        fields = [
            'id', 'created_at', 'updated_at',
            'from_currency', 'from_code',
            'to_currency', 'to_code',
            'rate', 'bid_rate', 'ask_rate', 'mid_rate',
            'date', 'fetched_at', 'valid_until',
            'source', 'is_official', 'change_percent',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'fetched_at']
        extra_kwargs = {
            'from_currency': {'write_only': True},
            'to_currency': {'write_only': True},
        }


class AutoTranslateSerializer(serializers.Serializer):
    language_code = serializers.CharField(max_length=10)
    source_language_code = serializers.CharField(max_length=10, default='en')
    dry_run = serializers.BooleanField(default=False)
    provider = serializers.CharField(max_length=50, required=False, allow_blank=True)


class ImportExportSerializer(serializers.Serializer):
    FORMAT_CHOICES = [('json', 'JSON'), ('po', 'PO'), ('csv', 'CSV'), ('xlsx', 'XLSX')]
    language_code = serializers.CharField(max_length=10)
    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default='json')
    namespace = serializers.CharField(required=False, allow_blank=True)
    include_empty = serializers.BooleanField(default=False)


class AdminSerializer(serializers.Serializer):
    action = serializers.CharField(max_length=100)
    params = serializers.JSONField(default=dict, required=False)
    confirm = serializers.BooleanField(default=False)


class PublicTranslationSerializer(serializers.Serializer):
    language_code = serializers.CharField(max_length=10)
    namespace = serializers.CharField(required=False, allow_blank=True)
    keys = serializers.ListField(
        child=serializers.CharField(), required=False
    )
    flat = serializers.BooleanField(default=False)
