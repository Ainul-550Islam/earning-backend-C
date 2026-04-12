"""
Intelligence Serializers
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model

from ..models.intelligence import (
    AlertCorrelation, AlertPrediction, AnomalyDetectionModel, 
    AlertNoise, RootCauseAnalysis
)

User = get_user_model()


class AlertCorrelationSerializer(serializers.ModelSerializer):
    """AlertCorrelation serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    primary_rules_count = serializers.SerializerMethodField()
    secondary_rules_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertCorrelation
        fields = [
            'id', 'name', 'description', 'correlation_type', 'status',
            'primary_rules', 'secondary_rules', 'time_window_minutes',
            'correlation_threshold', 'minimum_occurrences', 'correlation_coefficient',
            'p_value', 'confidence_level', 'pattern_description', 'pattern_regex',
            'model_type', 'model_parameters', 'correlation_strength', 'prediction_accuracy',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
            'last_analyzed', 'primary_rules_count', 'secondary_rules_count'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'correlation_coefficient',
                          'p_value', 'confidence_level', 'correlation_strength', 'prediction_accuracy',
                          'last_analyzed']
    
    def get_primary_rules_count(self, obj):
        return obj.primary_rules.count()
    
    def get_secondary_rules_count(self, obj):
        return obj.secondary_rules.count()
    
    def validate_time_window_minutes(self, value):
        if not 1 <= value <= 1440:
            raise serializers.ValidationError("Time window must be between 1 and 1440 minutes")
        return value
    
    def validate_correlation_threshold(self, value):
        if not 0 <= value <= 1:
            raise serializers.ValidationError("Correlation threshold must be between 0 and 1")
        return value
    
    def validate_minimum_occurrences(self, value):
        if not 2 <= value <= 100:
            raise serializers.ValidationError("Minimum occurrences must be between 2 and 100")
        return value


class AlertPredictionSerializer(serializers.ModelSerializer):
    """AlertPrediction serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    target_rules_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertPrediction
        fields = [
            'id', 'name', 'description', 'prediction_type', 'model_type', 'is_active',
            'target_rules', 'training_days', 'prediction_horizon_hours', 'model_parameters',
            'feature_columns', 'accuracy_score', 'precision_score', 'recall_score',
            'f1_score', 'mean_absolute_error', 'training_status', 'last_trained',
            'created_by', 'created_by_name', 'created_at', 'updated_at', 'target_rules_count'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'accuracy_score',
                          'precision_score', 'recall_score', 'f1_score', 'mean_absolute_error',
                          'last_trained']
    
    def get_target_rules_count(self, obj):
        return obj.target_rules.count()
    
    def validate_training_days(self, value):
        if not 7 <= value <= 365:
            raise serializers.ValidationError("Training days must be between 7 and 365")
        return value
    
    def validate_prediction_horizon_hours(self, value):
        if not 1 <= value <= 168:
            raise serializers.ValidationError("Prediction horizon must be between 1 and 168 hours")
        return value
    
    def validate_model_type(self, value):
        valid_types = ['linear_regression', 'arima', 'lstm', 'prophet', 'ensemble']
        if value not in valid_types:
            raise serializers.ValidationError(f"Model type must be one of: {valid_types}")
        return value


class AnomalyDetectionModelSerializer(serializers.ModelSerializer):
    """AnomalyDetectionModel serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    target_rules_count = serializers.SerializerMethodField()
    
    class Meta:
        model = AnomalyDetectionModel
        fields = [
            'id', 'name', 'description', 'detection_method', 'target_anomaly_types',
            'target_rules', 'sensitivity', 'window_size_minutes', 'baseline_days',
            'anomaly_threshold', 'min_alert_count', 'model_parameters', 'is_active',
            'last_trained', 'created_by', 'created_by_name', 'created_at', 'updated_at',
            'target_rules_count'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'last_trained']
    
    def get_target_rules_count(self, obj):
        return obj.target_rules.count()
    
    def validate_sensitivity(self, value):
        if not 0.1 <= value <= 1.0:
            raise serializers.ValidationError("Sensitivity must be between 0.1 and 1.0")
        return value
    
    def validate_window_size_minutes(self, value):
        if not 5 <= value <= 1440:
            raise serializers.ValidationError("Window size must be between 5 and 1440 minutes")
        return value
    
    def validate_baseline_days(self, value):
        if not 7 <= value <= 90:
            raise serializers.ValidationError("Baseline days must be between 7 and 90")
        return value
    
    def validate_anomaly_threshold(self, value):
        if value < 0:
            raise serializers.ValidationError("Anomaly threshold must be non-negative")
        return value
    
    def validate_min_alert_count(self, value):
        if value < 1:
            raise serializers.ValidationError("Minimum alert count must be at least 1")
        return value
    
    def validate_detection_method(self, value):
        valid_methods = ['statistical', 'ml_isolation_forest', 'ml_one_class_svm', 'time_series', 'threshold_based']
        if value not in valid_methods:
            raise serializers.ValidationError(f"Detection method must be one of: {valid_methods}")
        return value


class AlertNoiseSerializer(serializers.ModelSerializer):
    """AlertNoise serializer"""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    target_rules_count = serializers.SerializerMethodField()
    effectiveness_score = serializers.SerializerMethodField()
    
    class Meta:
        model = AlertNoise
        fields = [
            'id', 'name', 'description', 'noise_type', 'action', 'is_active',
            'target_rules', 'message_patterns', 'severity_filter', 'source_filter',
            'suppression_duration_minutes', 'max_suppressions_per_hour', 'group_window_minutes',
            'max_group_size', 'delay_minutes', 'total_processed', 'total_suppressed',
            'total_grouped', 'total_delayed', 'created_by', 'created_by_name',
            'created_at', 'updated_at', 'target_rules_count', 'effectiveness_score'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'total_processed',
                          'total_suppressed', 'total_grouped', 'total_delayed']
    
    def get_target_rules_count(self, obj):
        return obj.target_rules.count()
    
    def get_effectiveness_score(self, obj):
        return obj.get_effectiveness_score()
    
    def validate_suppression_duration_minutes(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError("Suppression duration must be at least 1 minute")
        return value
    
    def validate_max_suppressions_per_hour(self, value):
        if not 1 <= value <= 1000:
            raise serializers.ValidationError("Max suppressions per hour must be between 1 and 1000")
        return value
    
    def validate_group_window_minutes(self, value):
        if not 1 <= value <= 1440:
            raise serializers.ValidationError("Group window must be between 1 and 1440 minutes")
        return value
    
    def validate_max_group_size(self, value):
        if not 2 <= value <= 50:
            raise serializers.ValidationError("Max group size must be between 2 and 50")
        return value
    
    def validate_delay_minutes(self, value):
        if not 1 <= value <= 60:
            raise serializers.ValidationError("Delay minutes must be between 1 and 60")
        return value
    
    def validate_noise_type(self, value):
        valid_types = ['repeated', 'low_priority', 'known_issue', 'maintenance', 'test_environment', 'configuration_error']
        if value not in valid_types:
            raise serializers.ValidationError(f"Noise type must be one of: {valid_types}")
        return value
    
    def validate_action(self, value):
        valid_actions = ['suppress', 'group', 'delay', 'escalate', 'filter']
        if value not in valid_actions:
            raise serializers.ValidationError(f"Action must be one of: {valid_actions}")
        return value


class RootCauseAnalysisSerializer(serializers.ModelSerializer):
    """RootCauseAnalysis serializer"""
    incident_title = serializers.CharField(source='incident.title', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    analysis_score = serializers.SerializerMethodField()
    
    class Meta:
        model = RootCauseAnalysis
        fields = [
            'id', 'title', 'description', 'analysis_method', 'confidence_level',
            'related_alerts', 'related_incidents', 'timeline_events', 'causal_chain',
            'root_causes', 'contributing_factors', 'evidence', 'timeline_summary',
            'key_events', 'impact_assessment', 'affected_systems', 'business_impact',
            'technical_impact', 'customer_impact', 'financial_impact',
            'lessons_learned', 'action_items', 'preventive_measures',
            'process_improvements', 'tool_improvements', 'training_needs',
            'verification_method', 'verification_results', 'status', 'reviewed_by',
            'reviewed_by_name', 'approved_by', 'approved_by_name', 'published_at',
            'internal_only', 'external_summary', 'created_by', 'created_by_name',
            'created_at', 'updated_at', 'completed_at', 'analysis_score'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by', 'completed_at']
    
    def get_analysis_score(self, obj):
        return obj.get_analysis_score()
    
    def validate_analysis_method(self, value):
        valid_methods = ['5_whys', 'fishbone', 'fault_tree', 'pareto', 'statistical', 'ml_based']
        if value not in valid_methods:
            raise serializers.ValidationError(f"Analysis method must be one of: {valid_methods}")
        return value
    
    def validate_confidence_level(self, value):
        valid_levels = ['low', 'medium', 'high', 'very_high']
        if value not in valid_levels:
            raise serializers.ValidationError(f"Confidence level must be one of: {valid_levels}")
        return value


# Simplified serializers for list views
class AlertCorrelationListSerializer(serializers.ModelSerializer):
    """Simplified AlertCorrelation serializer for list views"""
    
    class Meta:
        model = AlertCorrelation
        fields = [
            'id', 'name', 'correlation_type', 'status', 'correlation_strength',
            'last_analyzed', 'created_at'
        ]


class AlertPredictionListSerializer(serializers.ModelSerializer):
    """Simplified AlertPrediction serializer for list views"""
    
    class Meta:
        model = AlertPrediction
        fields = [
            'id', 'name', 'prediction_type', 'model_type', 'is_active',
            'accuracy_score', 'training_status', 'last_trained'
        ]


class AnomalyDetectionModelListSerializer(serializers.ModelSerializer):
    """Simplified AnomalyDetectionModel serializer for list views"""
    
    class Meta:
        model = AnomalyDetectionModel
        fields = [
            'id', 'name', 'detection_method', 'is_active', 'sensitivity',
            'last_trained', 'created_at'
        ]


class AlertNoiseListSerializer(serializers.ModelSerializer):
    """Simplified AlertNoise serializer for list views"""
    
    class Meta:
        model = AlertNoise
        fields = [
            'id', 'name', 'noise_type', 'action', 'is_active',
            'total_processed', 'total_suppressed', 'created_at'
        ]


class RootCauseAnalysisListSerializer(serializers.ModelSerializer):
    """Simplified RootCauseAnalysis serializer for list views"""
    incident_title = serializers.CharField(source='incident.title', read_only=True)
    
    class Meta:
        model = RootCauseAnalysis
        fields = [
            'id', 'title', 'incident', 'incident_title', 'analysis_method',
            'status', 'created_at', 'completed_at'
        ]


# Action serializers
class AlertCorrelationAnalyzeSerializer(serializers.Serializer):
    """Serializer for analyzing correlations (no additional fields needed)"""
    pass


class AlertCorrelationPredictSerializer(serializers.Serializer):
    """Serializer for predicting correlations"""
    rule_id = serializers.IntegerField(required=True)
    trigger_value = serializers.FloatField(required=True)
    
    def validate_rule_id(self, value):
        from ..models.core import AlertRule
        try:
            AlertRule.objects.get(id=value)
        except AlertRule.DoesNotExist:
            raise serializers.ValidationError("Alert rule not found")
        return value


class AlertPredictionTrainSerializer(serializers.Serializer):
    """Serializer for training prediction models (no additional fields needed)"""
    pass


class AlertPredictionPredictSerializer(serializers.Serializer):
    """Serializer for making predictions"""
    context = serializers.DictField(required=False, default=dict)


class AnomalyDetectionModelDetectAnomaliesSerializer(serializers.Serializer):
    """Serializer for detecting anomalies (no additional fields needed)"""
    pass


class AnomalyDetectionModelUpdateThresholdsSerializer(serializers.Serializer):
    """Serializer for updating anomaly thresholds"""
    sensitivity = serializers.FloatField(required=False, min_value=0.1, max_value=1.0)
    anomaly_threshold = serializers.FloatField(required=False, min_value=0)
    window_size_minutes = serializers.IntegerField(required=False, min_value=5, max_value=1440)


class AlertNoiseTestFilterSerializer(serializers.Serializer):
    """Serializer for testing noise filters"""
    rule_id = serializers.IntegerField(required=True)
    trigger_value = serializers.FloatField(required=True)
    message = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_rule_id(self, value):
        from ..models.core import AlertRule
        try:
            AlertRule.objects.get(id=value)
        except AlertRule.DoesNotExist:
            raise serializers.ValidationError("Alert rule not found")
        return value


class RootCauseAnalysisPerformAnalysisSerializer(serializers.Serializer):
    """Serializer for performing RCA (no additional fields needed)"""
    pass


class RootCauseAnalysisGenerateRecommendationsSerializer(serializers.Serializer):
    """Serializer for generating recommendations (no additional fields needed)"""
    pass


class RootCauseAnalysisCreateFromIncidentSerializer(serializers.Serializer):
    """Serializer for creating RCA from incident"""
    incident_id = serializers.IntegerField(required=True)
    analysis_data = serializers.DictField(required=False, default=dict)
    
    def validate_incident_id(self, value):
        from ..models.incident import Incident
        try:
            Incident.objects.get(id=value)
        except Incident.DoesNotExist:
            raise serializers.ValidationError("Incident not found")
        return value


class AlertCorrelationCreateFromPatternSerializer(serializers.Serializer):
    """Serializer for creating correlation from pattern"""
    auto_analyze = serializers.BooleanField(default=False)
