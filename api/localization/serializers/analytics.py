# serializers/analytics.py
from rest_framework import serializers

class LocalizationInsightSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True, default=None)
    cache_hit_rate = serializers.FloatField(read_only=True)
    translation_hit_rate = serializers.FloatField(read_only=True)
    class Meta:
        from ..models.analytics import LocalizationInsight
        model = LocalizationInsight
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class TranslationCoverageSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)
    language_name = serializers.CharField(source='language.name', read_only=True)
    class Meta:
        from ..models.analytics import TranslationCoverage
        model = TranslationCoverage
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

class LanguageUsageStatSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)
    class Meta:
        from ..models.analytics import LanguageUsageStat
        model = LanguageUsageStat
        fields = '__all__'
        read_only_fields = ['id', 'created_at']

class GeoInsightSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.analytics import GeoInsight
        model = GeoInsight
        fields = '__all__'
        read_only_fields = ['id', 'created_at']
