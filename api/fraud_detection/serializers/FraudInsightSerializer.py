# =============================================================================
# fraud_detection/serializers/FraudInsightSerializer.py
#
# Read-only serializers for analytics, insight, and reporting endpoints.
# All fields are SerializerMethodField or plain Serializer fields —
# no model writes happen through these serializers.
# =============================================================================
from __future__ import annotations

from rest_framework import serializers


class FraudOverviewSerializer(serializers.Serializer):
    total_attempts      = serializers.IntegerField()
    confirmed_fraud     = serializers.IntegerField()
    dismissed           = serializers.IntegerField()
    pending_review      = serializers.IntegerField()
    avg_fraud_score     = serializers.FloatField()
    high_risk_users     = serializers.IntegerField()
    active_rules        = serializers.IntegerField()
    unresolved_alerts   = serializers.IntegerField()
    generated_at        = serializers.DateTimeField()


class FraudTrendDataSerializer(serializers.Serializer):
    date        = serializers.DateField()
    count       = serializers.IntegerField()
    avg_score   = serializers.FloatField()
    confirmed   = serializers.IntegerField()


class FraudTrendsSerializer(serializers.Serializer):
    period  = serializers.CharField()        # 'daily' | 'weekly' | 'monthly'
    data    = FraudTrendDataSerializer(many=True)
    total   = serializers.IntegerField()


class RiskFactorSerializer(serializers.Serializer):
    factor      = serializers.CharField()
    weight      = serializers.FloatField()
    count       = serializers.IntegerField()
    avg_impact  = serializers.FloatField()


class TopRiskFactorsSerializer(serializers.Serializer):
    factors     = RiskFactorSerializer(many=True)
    generated_at = serializers.DateTimeField()


class CountryRiskSerializer(serializers.Serializer):
    country     = serializers.CharField()
    attempts    = serializers.IntegerField()
    avg_score   = serializers.FloatField()
    risk_level  = serializers.CharField()


class GeographicAnalysisSerializer(serializers.Serializer):
    countries   = CountryRiskSerializer(many=True)
    total       = serializers.IntegerField()
    generated_at = serializers.DateTimeField()


class PerformanceMetricsSerializer(serializers.Serializer):
    true_positives      = serializers.IntegerField()
    false_positives     = serializers.IntegerField()
    true_negatives      = serializers.IntegerField()
    false_negatives     = serializers.IntegerField()
    precision           = serializers.FloatField()
    recall              = serializers.FloatField()
    f1_score            = serializers.FloatField()
    accuracy            = serializers.FloatField()
    avg_detection_time_ms = serializers.FloatField()


class ForecastDataSerializer(serializers.Serializer):
    date            = serializers.DateField()
    predicted_count = serializers.IntegerField()
    confidence      = serializers.FloatField()


class PredictiveInsightsSerializer(serializers.Serializer):
    forecast        = ForecastDataSerializer(many=True)
    risk_trend      = serializers.CharField()   # 'increasing' | 'stable' | 'decreasing'
    recommendation  = serializers.CharField()
    generated_at    = serializers.DateTimeField()


class AnalyticsExportSerializer(serializers.Serializer):
    format      = serializers.ChoiceField(choices=['csv', 'json', 'excel'], default='csv')
    date_from   = serializers.DateField(required=False)
    date_to     = serializers.DateField(required=False)
    fields      = serializers.ListField(child=serializers.CharField(), required=False)


class AnalyticsDataSerializer(serializers.Serializer):
    overview    = FraudOverviewSerializer()
    trends      = FraudTrendsSerializer()
    performance = PerformanceMetricsSerializer()
    geo         = GeographicAnalysisSerializer()


class InsightRequestSerializer(serializers.Serializer):
    date_from   = serializers.DateField(required=False)
    date_to     = serializers.DateField(required=False)
    group_by    = serializers.ChoiceField(
        choices=['day', 'week', 'month'], default='day', required=False
    )
    include     = serializers.ListField(
        child=serializers.ChoiceField(choices=['overview', 'trends', 'geo', 'performance', 'predictions']),
        required=False,
    )
