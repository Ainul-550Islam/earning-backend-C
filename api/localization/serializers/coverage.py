# serializers/coverage.py
from rest_framework import serializers


class TranslationCoverageSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)
    language_name = serializers.CharField(source='language.name', read_only=True)

    class Meta:
        from ..models.analytics import TranslationCoverage
        model = TranslationCoverage
        fields = [
            'id', 'created_at', 'updated_at',
            'language', 'language_code', 'language_name',
            'total_keys', 'translated_keys', 'approved_keys',
            'pending_review_keys', 'machine_translated_keys',
            'coverage_percent', 'approved_percent', 'missing_keys',
            'last_calculated_at',
            'coverage_by_namespace', 'top_missing',
            'trend_7d', 'trend_30d',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_calculated_at']
        extra_kwargs = {'language': {'write_only': True}}
