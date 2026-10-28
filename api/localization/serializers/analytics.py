# serializers/analytics.py
from rest_framework import serializers


class LocalizationInsightSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(
        source='language.code', read_only=True, default=None
    )
    cache_hit_rate = serializers.FloatField(read_only=True)
    translation_hit_rate = serializers.FloatField(read_only=True)

    class Meta:
        from ..models.analytics import LocalizationInsight
        model = LocalizationInsight
        fields = [
            'id', 'created_at', 'updated_at',
            'date', 'language', 'language_code', 'country',
            'total_requests', 'unique_users',
            'translation_hits', 'translation_misses', 'translation_hit_rate',
            'cache_hits', 'cache_misses', 'cache_hit_rate',
            'avg_response_time_ms',
            'currency_conversions', 'language_switches', 'geo_lookups',
            'top_missing_keys', 'top_endpoints', 'platform_breakdown',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'language': {'write_only': True, 'required': False},
        }


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


class LanguageUsageStatSerializer(serializers.ModelSerializer):
    language_code = serializers.CharField(source='language.code', read_only=True)

    class Meta:
        from ..models.analytics import LanguageUsageStat
        model = LanguageUsageStat
        fields = [
            'id', 'created_at',
            'date', 'language', 'language_code',
            'dau', 'mau', 'new_users', 'returning_users',
            'session_count', 'avg_session_duration_seconds',
            'page_views', 'api_calls', 'translation_requests',
            'top_countries', 'top_pages',
            'device_breakdown', 'source_breakdown',
        ]
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {'language': {'write_only': True}}


class GeoInsightSerializer(serializers.ModelSerializer):
    class Meta:
        from ..models.analytics import GeoInsight
        model = GeoInsight
        fields = [
            'id', 'created_at',
            'date', 'country', 'country_code',
            'region_name', 'city_name',
            'total_users', 'total_requests',
            'top_language', 'language_distribution', 'currency_distribution',
            'vpn_users', 'mobile_users', 'desktop_users',
            'avg_response_time_ms',
        ]
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {'country': {'write_only': True, 'required': False}}
