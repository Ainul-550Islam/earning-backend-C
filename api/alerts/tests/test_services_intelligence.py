"""
Tests for Intelligence Services
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
import json

from alerts.models.core import AlertRule, AlertLog
from alerts.models.intelligence import (
    AlertCorrelation, AlertPrediction, AnomalyDetectionModel, AlertNoise, RootCauseAnalysis
)
from alerts.services.intelligence import (
    CorrelationAnalysisService, PredictionService, AnomalyDetectionService,
    NoiseFilteringService, RootCauseAnalysisService
)


class CorrelationAnalysisServiceTest(TestCase):
    """Test cases for CorrelationAnalysisService"""
    
    def setUp(self):
        self.service = CorrelationAnalysisService()
        
        # Create test data
        self.alert_rule1 = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        self.alert_rule2 = AlertRule.objects.create(
            name='Memory Alert',
            alert_type='memory_usage',
            severity='high',
            threshold_value=85.0
        )
        
        # Create correlated alerts
        base_time = timezone.now() - timedelta(hours=2)
        for i in range(20):
            # CPU alerts
            AlertLog.objects.create(
                rule=self.alert_rule1,
                trigger_value=85.0 + (i % 10),
                threshold_value=80.0,
                message=f'CPU alert {i}',
                triggered_at=base_time + timedelta(minutes=i * 5)
            )
            
            # Memory alerts (correlated with CPU)
            if i % 3 == 0:
                AlertLog.objects.create(
                    rule=self.alert_rule2,
                    trigger_value=90.0 + (i % 8),
                    threshold_value=85.0,
                    message=f'Memory alert {i}',
                    triggered_at=base_time + timedelta(minutes=i * 5 + 2)
                )
    
    def test_analyze_temporal_correlation(self):
        """Test analyzing temporal correlation"""
        correlation_data = {
            'rule_ids': [self.alert_rule1.id, self.alert_rule2.id],
            'time_window_minutes': 30,
            'correlation_method': 'pearson'
        }
        
        result = self.service.analyze_temporal_correlation(correlation_data)
        
        self.assertIn('correlation_coefficient', result)
        self.assertIn('p_value', result)
        self.assertIn('confidence_level', result)
        self.assertIn('sample_size', result)
        self.assertIn('correlation_strength', result)
    
    def test_analyze_causal_correlation(self):
        """Test analyzing causal correlation"""
        causal_data = {
            'cause_rule_id': self.alert_rule1.id,
            'effect_rule_id': self.alert_rule2.id,
            'time_lag_minutes': 5,
            'method': 'granger'
        }
        
        result = self.service.analyze_causal_correlation(causal_data)
        
        self.assertIn('causality_score', result)
        self.assertIn('time_lag', result)
        self.assertIn('confidence', result)
        self.assertIn('causal_relationship', result)
    
    def test_find_correlated_patterns(self):
        """Test finding correlated patterns"""
        pattern_data = {
            'time_period_hours': 24,
            'min_correlation_threshold': 0.7,
            'min_occurrences': 5
        }
        
        patterns = self.service.find_correlated_patterns(pattern_data)
        
        self.assertIsInstance(patterns, list)
        self.assertGreater(len(patterns), 0)
        
        for pattern in patterns:
            self.assertIn('rule_pairs', pattern)
            self.assertIn('correlation_coefficient', pattern)
            self.assertIn('frequency', pattern)
            self.assertIn('time_windows', pattern)
    
    def test_predict_correlation(self):
        """Test predicting correlation"""
        prediction_data = {
            'rule_ids': [self.alert_rule1.id, self.alert_rule2.id],
            'prediction_horizon_hours': 6,
            'historical_days': 30
        }
        
        result = self.service.predict_correlation(prediction_data)
        
        self.assertIn('predicted_correlation', result)
        self.assertIn('confidence_interval', result)
        self.assertIn('prediction_accuracy', result)
        self.assertIn('factors', result)
    
    def test_create_correlation_model(self):
        """Test creating correlation model"""
        model_data = {
            'name': 'CPU-Memory Correlation',
            'correlation_type': 'temporal',
            'primary_rules': [self.alert_rule1.id, self.alert_rule2.id],
            'model_parameters': {
                'method': 'pearson',
                'window_size': 30,
                'threshold': 0.7
            }
        }
        
        result = self.service.create_correlation_model(model_data)
        
        self.assertTrue(result['success'])
        self.assertIn('model_id', result)
        self.assertIn('model_status', result)
    
    def test_update_correlation_model(self):
        """Test updating correlation model"""
        # Create a correlation model first
        correlation = AlertCorrelation.objects.create(
            name='Test Correlation',
            correlation_type='temporal',
            status='pending'
        )
        correlation.primary_rules.add(self.alert_rule1, self.alert_rule2)
        
        update_data = {
            'correlation_coefficient': 0.85,
            'p_value': 0.001,
            'confidence_level': 0.9,
            'status': 'confirmed'
        }
        
        result = self.service.update_correlation_model(correlation.id, update_data)
        
        self.assertTrue(result['success'])
        self.assertIn('updated_fields', result)
    
    def test_get_correlation_insights(self):
        """Test getting correlation insights"""
        insights = self.service.get_correlation_insights(days=7)
        
        self.assertIn('top_correlations', insights)
        self.assertIn('correlation_trends', insights)
        self.assertIn('anomalous_correlations', insights)
        self.assertIn('recommendations', insights)


class PredictionServiceTest(TestCase):
    """Test cases for PredictionService"""
    
    def setUp(self):
        self.service = PredictionService()
        
        self.alert_rule = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        # Create historical data for training
        base_time = timezone.now() - timedelta(days=30)
        for i in range(100):
            AlertLog.objects.create(
                rule=self.alert_rule,
                trigger_value=75.0 + (i % 20),
                threshold_value=80.0,
                message=f'CPU alert {i}',
                triggered_at=base_time + timedelta(hours=i)
            )
    
    def test_train_prediction_model(self):
        """Test training prediction model"""
        training_data = {
            'rule_id': self.alert_rule.id,
            'model_type': 'linear_regression',
            'features': ['cpu_usage', 'memory_usage', 'disk_io'],
            'target': 'alert_probability',
            'training_days': 30,
            'validation_split': 0.2
        }
        
        result = self.service.train_prediction_model(training_data)
        
        self.assertIn('model_id', result)
        self.assertIn('training_metrics', result)
        self.assertIn('accuracy_score', result)
        self.assertIn('precision_score', result)
        self.assertIn('recall_score', result)
        self.assertIn('f1_score', result)
    
    def test_predict_alert_probability(self):
        """Test predicting alert probability"""
        # Create a prediction model first
        prediction = AlertPrediction.objects.create(
            name='CPU Prediction',
            prediction_type='threshold_breach',
            model_type='linear_regression',
            training_status='completed',
            target_rules=self.alert_rule
        )
        
        prediction_data = {
            'model_id': prediction.id,
            'features': {
                'cpu_usage': 85.0,
                'memory_usage': 70.0,
                'disk_io': 50.0
            },
            'prediction_horizon_hours': 6
        }
        
        result = self.service.predict_alert_probability(prediction_data)
        
        self.assertIn('predicted_probability', result)
        self.assertIn('confidence_interval', result)
        self.assertIn('risk_level', result)
        self.assertIn('factors', result)
    
    def test_predict_alert_volume(self):
        """Test predicting alert volume"""
        volume_data = {
            'rule_ids': [self.alert_rule.id],
            'prediction_horizon_hours': 24,
            'historical_days': 30,
            'model_type': 'time_series'
        }
        
        result = self.service.predict_alert_volume(volume_data)
        
        self.assertIn('predicted_volume', result)
        self.assertIn('confidence_interval', result)
        self.assertIn('trend', result)
        self.assertIn('seasonal_pattern', result)
    
    def test_predict_severity_trend(self):
        """Test predicting severity trend"""
        trend_data = {
            'rule_id': self.alert_rule.id,
            'prediction_horizon_hours': 12,
            'historical_days': 14
        }
        
        result = self.service.predict_severity_trend(trend_data)
        
        self.assertIn('severity_trend', result)
        self.assertIn('probability_by_severity', result)
        self.assertIn('trend_direction', result)
        self.assertIn('confidence', result)
    
    def test_evaluate_model_performance(self):
        """Test evaluating model performance"""
        # Create a prediction model
        prediction = AlertPrediction.objects.create(
            name='Test Model',
            prediction_type='threshold_breach',
            model_type='linear_regression',
            training_status='completed',
            target_rules=self.alert_rule
        )
        
        evaluation_data = {
            'model_id': prediction.id,
            'test_period_days': 7,
            'metrics': ['accuracy', 'precision', 'recall', 'f1', 'auc']
        }
        
        result = self.service.evaluate_model_performance(evaluation_data)
        
        self.assertIn('performance_metrics', result)
        self.assertIn('confusion_matrix', result)
        self.assertIn('roc_curve', result)
        self.assertIn('feature_importance', result)
    
    def test_retrain_model(self):
        """Test retraining model"""
        prediction = AlertPrediction.objects.create(
            name='Retrain Model',
            prediction_type='threshold_breach',
            model_type='linear_regression',
            training_status='completed',
            target_rules=self.alert_rule
        )
        
        retrain_data = {
            'model_id': prediction.id,
            'additional_training_days': 7,
            'update_strategy': 'incremental'
        }
        
        result = self.service.retrain_model(retrain_data)
        
        self.assertIn('retrain_result', result)
        self.assertIn('performance_improvement', result)
        self.assertIn('new_metrics', result)
    
    def test_get_prediction_accuracy_trends(self):
        """Test getting prediction accuracy trends"""
        trends = self.service.get_prediction_accuracy_trends(days=30)
        
        self.assertIn('accuracy_trend', trends)
        self.assertIn('model_comparison', trends)
        self.assertIn('accuracy_by_day', trends)
        self.assertIn('recommendations', trends)


class AnomalyDetectionServiceTest(TestCase):
    """Test cases for AnomalyDetectionService"""
    
    def setUp(self):
        self.service = AnomalyDetectionService()
        
        self.alert_rule = AlertRule.objects.create(
            name='CPU Alert',
            alert_type='cpu_usage',
            severity='high',
            threshold_value=80.0
        )
        
        # Create anomaly model
        self.anomaly_model = AnomalyDetectionModel.objects.create(
            name='CPU Anomaly Detection',
            detection_method='statistical',
            target_rules=self.alert_rule,
            sensitivity=0.8,
            window_size_minutes=60,
            baseline_days=7
        )
    
    def test_detect_anomalies(self):
        """Test detecting anomalies"""
        # Create test data with anomalies
        data_points = []
        for i in range(100):
            value = 50.0 + (i % 10)
            if i % 20 == 0:  # Add anomaly every 20 points
                value = 100.0
            data_points.append(value)
        
        detection_data = {
            'model_id': self.anomaly_model.id,
            'data_points': data_points,
            'detection_method': 'z_score',
            'threshold': 2.0
        }
        
        result = self.service.detect_anomalies(detection_data)
        
        self.assertIn('anomalies', result)
        self.assertIn('anomaly_count', result)
        self.assertIn('anomaly_score', result)
        self.assertIsInstance(result['anomalies'], list)
    
    def test_train_anomaly_model(self):
        """Test training anomaly model"""
        training_data = {
            'model_id': self.anomaly_model.id,
            'training_data': [50.0 + (i % 15) for i in range(1000)],
            'method': 'isolation_forest',
            'contamination': 0.1
        }
        
        result = self.service.train_anomaly_model(training_data)
        
        self.assertIn('training_result', result)
        self.assertIn('model_accuracy', result)
        self.assertIn('false_positive_rate', result)
        self.assertIn('detection_threshold', result)
    
    def test_detect_real_time_anomaly(self):
        """Test detecting real-time anomaly"""
        realtime_data = {
            'model_id': self.anomaly_model.id,
            'current_value': 95.0,
            'recent_values': [50.0, 52.0, 48.0, 51.0, 49.0],
            'context': {
                'time_of_day': timezone.now().hour,
                'day_of_week': timezone.now().weekday()
            }
        }
        
        result = self.service.detect_real_time_anomaly(realtime_data)
        
        self.assertIn('is_anomaly', result)
        self.assertIn('anomaly_score', result)
        self.assertIn('confidence', result)
        self.assertIn('explanation', result)
    
    def test_update_anomaly_threshold(self):
        """Test updating anomaly threshold"""
        update_data = {
            'model_id': self.anomaly_model.id,
            'new_threshold': 2.5,
            'new_sensitivity': 0.9,
            'reason': 'High false positive rate'
        }
        
        result = self.service.update_anomaly_threshold(update_data)
        
        self.assertTrue(result['success'])
        self.assertIn('updated_at', result)
    
    def test_get_anomaly_patterns(self):
        """Test getting anomaly patterns"""
        patterns = self.service.get_anomaly_patterns(
            model_id=self.anomaly_model.id,
            days=30
        )
        
        self.assertIn('pattern_types', patterns)
        self.assertIn('frequency_analysis', patterns)
        self.assertIn('seasonal_patterns', patterns)
        self.assertIn('anomaly_clusters', patterns)
    
    def test_get_anomaly_impact_analysis(self):
        """Test getting anomaly impact analysis"""
        impact_data = {
            'anomaly_ids': [1, 2, 3],  # Mock IDs
            'impact_metrics': ['alert_volume', 'severity_distribution', 'system_performance']
        }
        
        impact = self.service.get_anomaly_impact_analysis(impact_data)
        
        self.assertIn('impact_summary', impact)
        self.assertIn('affected_systems', impact)
        self.assertIn('business_impact', impact)
        self.assertIn('recommendations', impact)


class NoiseFilteringServiceTest(TestCase):
    """Test cases for NoiseFilteringService"""
    
    def setUp(self):
        self.service = NoiseFilteringService()
        
        self.alert_rule = AlertRule.objects.create(
            name='Test Alert',
            alert_type='test_metric',
            severity='low',
            threshold_value=80.0
        )
        
        # Create noise filter
        self.noise_filter = AlertNoise.objects.create(
            name='Test Noise Filter',
            noise_type='suppression',
            action='suppress',
            target_rules=self.alert_rule,
            message_patterns=['test', 'debug', 'maintenance'],
            severity_filter=['low']
        )
    
    def test_should_filter_alert(self):
        """Test filtering alert"""
        alert_data = {
            'rule_id': self.alert_rule.id,
            'message': 'Test alert for debugging',
            'severity': 'low',
            'source': 'test-environment',
            'timestamp': timezone.now()
        }
        
        result = self.service.should_filter_alert(alert_data)
        
        self.assertIn('should_filter', result)
        self.assertIn('filter_reason', result)
        self.assertIn('filter_type', result)
    
    def test_filter_alert(self):
        """Test filtering alert"""
        filter_data = {
            'alert_id': 1,  # Mock ID
            'filter_id': self.noise_filter.id,
            'filter_action': 'suppress',
            'reason': 'Test environment alert'
        }
        
        result = self.service.filter_alert(filter_data)
        
        self.assertTrue(result['success'])
        self.assertIn('filtered_at', result)
        self.assertIn('filter_details', result)
    
    def test_group_similar_alerts(self):
        """Test grouping similar alerts"""
        grouping_data = {
            'alert_ids': [1, 2, 3, 4, 5],  # Mock IDs
            'grouping_criteria': ['message_similarity', 'time_proximity', 'same_rule'],
            'time_window_minutes': 15,
            'similarity_threshold': 0.8
        }
        
        result = self.service.group_similar_alerts(grouping_data)
        
        self.assertIn('groups', result)
        self.assertIn('ungrouped_alerts', result)
        self.assertIn('grouping_statistics', result)
    
    def test_delay_alert(self):
        """Test delaying alert"""
        delay_data = {
            'alert_id': 1,  # Mock ID
            'delay_minutes': 30,
            'delay_reason': 'Low priority, batch processing'
        }
        
        result = self.service.delay_alert(delay_data)
        
        self.assertTrue(result['success'])
        self.assertIn('delayed_until', result)
        self.assertIn('delay_reason', result)
    
    def test_modify_alert_severity(self):
        """Test modifying alert severity"""
        modification_data = {
            'alert_id': 1,  # Mock ID
            'original_severity': 'low',
            'new_severity': 'medium',
            'reason': 'Contextual importance increase'
        }
        
        result = self.service.modify_alert_severity(modification_data)
        
        self.assertTrue(result['success'])
        self.assertIn('modified_at', result)
        self.assertIn('severity_change', result)
    
    def test_get_noise_filtering_statistics(self):
        """Test getting noise filtering statistics"""
        stats = self.service.get_noise_filtering_statistics(days=7)
        
        self.assertIn('total_processed', stats)
        self.assertIn('total_suppressed', stats)
        self.assertIn('total_grouped', stats)
        self.assertIn('total_delayed', stats)
        self.assertIn('effectiveness_rate', stats)
    
    def test_optimize_noise_filters(self):
        """Test optimizing noise filters"""
        optimization_data = {
            'filter_id': self.noise_filter.id,
            'optimization_period_days': 30,
            'optimization_goals': ['reduce_false_positives', 'improve_detection'],
            'target_effectiveness': 0.9
        }
        
        result = self.service.optimize_noise_filters(optimization_data)
        
        self.assertIn('optimization_result', result)
        self.assertIn('recommended_changes', result)
        self.assertIn('expected_improvement', result)
    
    def test_get_noise_patterns(self):
        """Test getting noise patterns"""
        patterns = self.service.get_noise_patterns(days=30)
        
        self.assertIn('noise_sources', patterns)
        self.assertIn('noise_types', patterns)
        self.assertIn('time_patterns', patterns)
        self.assertIn('content_patterns', patterns)


class RootCauseAnalysisServiceTest(TestCase):
    """Test cases for RootCauseAnalysisService"""
    
    def setUp(self):
        self.service = RootCauseAnalysisService()
        
        self.alert_rule = AlertRule.objects.create(
            name='Database Alert',
            alert_type='database_error',
            severity='critical',
            threshold_value=1.0
        )
        
        # Create RCA
        self.rca = RootCauseAnalysis.objects.create(
            title='Database Connection Failure RCA',
            analysis_method='5_why',
            confidence_level='high',
            status='completed',
            target_alerts=self.alert_rule
        )
    
    def test_perform_root_cause_analysis(self):
        """Test performing root cause analysis"""
        rca_data = {
            'alert_ids': [1, 2, 3],  # Mock IDs
            'analysis_method': '5_why',
            'time_period_hours': 24,
            'include_related_alerts': True
        }
        
        result = self.service.perform_root_cause_analysis(rca_data)
        
        self.assertIn('root_causes', result)
        self.assertIn('contributing_factors', result)
        self.assertIn('confidence_level', result)
        self.assertIn('evidence', result)
    
    def test_analyze_timeline(self):
        """Test analyzing timeline"""
        timeline_data = {
            'alert_ids': [1, 2, 3],  # Mock IDs
            'time_window_hours': 12,
            'include_system_events': True
        }
        
        result = self.service.analyze_timeline(timeline_data)
        
        self.assertIn('timeline_events', result)
        self.assertIn('critical_path', result)
        self.assertIn('time_correlations', result)
        self.assertIn('causal_chain', result)
    
    def test_identify_root_causes(self):
        """Test identifying root causes"""
        identification_data = {
            'alert_data': {
                'symptoms': ['Database connection failed', 'High response time'],
                'system_logs': ['Connection timeout', 'Pool exhausted'],
                'metrics': ['CPU spike', 'Memory usage high']
            },
            'analysis_method': 'fishbone'
        }
        
        result = self.service.identify_root_causes(identification_data)
        
        self.assertIn('primary_causes', result)
        self.assertIn('secondary_causes', result)
        self.assertIn('cause_hierarchy', result)
        self.assertIn('confidence_scores', result)
    
    def test_generate_recommendations(self):
        """Test generating recommendations"""
        # Set some analysis data
        self.rca.root_causes = 'Database connection pool exhausted'
        self.rca.contributing_factors = 'High load, insufficient monitoring'
        self.rca.save()
        
        recommendations = self.service.generate_recommendations(self.rca.id)
        
        self.assertIsInstance(recommendations, list)
        self.assertGreater(len(recommendations), 0)
        
        for rec in recommendations:
            self.assertIn('recommendation', rec)
            self.assertIn('priority', rec)
            self.assertIn('category', rec)
            self.assertIn('estimated_impact', rec)
    
    def test_validate_rca_findings(self):
        """Test validating RCA findings"""
        validation_data = {
            'rca_id': self.rca.id,
            'validation_criteria': ['evidence_support', 'logical_consistency', 'completeness'],
            'cross_reference_data': True
        }
        
        result = self.service.validate_rca_findings(validation_data)
        
        self.assertIn('validation_score', result)
        self.assertIn('validation_issues', result)
        self.assertIn('recommendations', result)
        self.assertIn('confidence_adjustment', result)
    
    def test_get_rca_templates(self):
        """Test getting RCA templates"""
        templates = self.service.get_rca_templates()
        
        self.assertIsInstance(templates, list)
        self.assertGreater(len(templates), 0)
        
        for template in templates:
            self.assertIn('template_name', template)
            self.assertIn('analysis_method', template)
            self.assertIn('sections', template)
            self.assertIn('questions', template)
    
    def test_create_rca_from_template(self):
        """Test creating RCA from template"""
        creation_data = {
            'template_name': '5_why_template',
            'alert_ids': [1, 2, 3],  # Mock IDs
            'title': 'New RCA from Template',
            'customizations': {
                'additional_sections': ['Business Impact'],
                'custom_questions': ['What was the user impact?']
            }
        }
        
        result = self.service.create_rca_from_template(creation_data)
        
        self.assertTrue(result['success'])
        self.assertIn('rca_id', result)
        self.assertIn('template_applied', result)
    
    def test_get_rca_effectiveness_metrics(self):
        """Test getting RCA effectiveness metrics"""
        metrics = self.service.get_rca_effectiveness_metrics(days=90)
        
        self.assertIn('rca_completion_rate', metrics)
        self.assertIn('average_analysis_time', metrics)
        self.assertIn('recommendation_implementation_rate', metrics)
        self.assertIn('recurrence_prevention_rate', metrics)
        self.assertIn('user_satisfaction_score', metrics)
