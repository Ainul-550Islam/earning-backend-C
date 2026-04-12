"""
Alert Intelligence Services
"""
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import logging

from ..models.intelligence import (
    AlertCorrelation, AlertPrediction, AnomalyDetectionModel, 
    AlertNoise, RootCauseAnalysis
)

logger = logging.getLogger(__name__)


class AlertCorrelationService:
    """Alert correlation analysis service"""
    
    @staticmethod
    def analyze_all_correlations():
        """Analyze all pending correlations"""
        try:
            correlations = AlertCorrelation.objects.filter(status='pending')
            
            analyzed_count = 0
            for correlation in correlations:
                correlation.analyze_correlation()
                analyzed_count += 1
            
            logger.info(f"Analyzed {analyzed_count} alert correlations")
            return analyzed_count
            
        except Exception as e:
            logger.error(f"Error analyzing correlations: {e}")
            return 0
    
    @staticmethod
    def get_correlation_insights(alert_log):
        """Get correlation insights for a specific alert"""
        try:
            insights = []
            
            # Check confirmed correlations
            confirmed_correlations = AlertCorrelation.objects.filter(
                status='confirmed'
            )
            
            for correlation in confirmed_correlations:
                if correlation.predict_correlation(alert_log):
                    insights.append({
                        'correlation_id': correlation.id,
                        'correlation_name': correlation.name,
                        'correlation_type': correlation.correlation_type,
                        'strength': correlation.correlation_strength,
                        'confidence': correlation.confidence_level,
                        'related_alerts': correlation.get_related_alerts(alert_log)
                    })
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting correlation insights: {e}")
            return []
    
    @staticmethod
    def create_correlation_from_pattern(correlation_data):
        """Create correlation from detected patterns"""
        try:
            correlation = AlertCorrelation.objects.create(**correlation_data)
            
            # Auto-analyze if data is provided
            if correlation_data.get('auto_analyze', False):
                correlation.analyze_correlation()
            
            logger.info(f"Created correlation: {correlation.name}")
            return correlation
            
        except Exception as e:
            logger.error(f"Error creating correlation: {e}")
            return None
    
    @staticmethod
    def get_correlation_summary(days=30):
        """Get correlation analysis summary"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            correlations = AlertCorrelation.objects.filter(
                last_analyzed__gte=cutoff_date
            )
            
            summary = {
                'total_correlations': correlations.count(),
                'confirmed': correlations.filter(status='confirmed').count(),
                'rejected': correlations.filter(status='rejected').count(),
                'pending': correlations.filter(status='pending').count(),
                'by_type': {},
                'average_strength': 0
            }
            
            # By type
            type_stats = correlations.values('correlation_type').annotate(
                count=models.Count('id'),
                avg_strength=models.Avg('correlation_strength')
            )
            
            for stat in type_stats:
                summary['by_type'][stat['correlation_type']] = {
                    'count': stat['count'],
                    'avg_strength': stat['avg_strength'] or 0
                }
            
            # Average strength
            confirmed_correlations = correlations.filter(status='confirmed')
            if confirmed_correlations.exists():
                summary['average_strength'] = confirmed_correlations.aggregate(
                    avg_strength=models.Avg('correlation_strength')
                )['avg_strength'] or 0
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting correlation summary: {e}")
            return None


class AlertPredictionService:
    """Alert prediction service"""
    
    @staticmethod
    def train_all_models():
        """Train all active prediction models"""
        try:
            models = AlertPrediction.objects.filter(is_active=True)
            
            trained_count = 0
            for model in models:
                model.train_model()
                trained_count += 1
            
            logger.info(f"Trained {trained_count} prediction models")
            return trained_count
            
        except Exception as e:
            logger.error(f"Error training models: {e}")
            return 0
    
    @staticmethod
    def make_predictions(alert_rules=None):
        """Make predictions for alert rules"""
        try:
            predictions = []
            
            if alert_rules is None:
                # Get all active prediction models
                models = AlertPrediction.objects.filter(
                    is_active=True,
                    training_status='completed'
                )
            else:
                # Get models for specific rules
                models = AlertPrediction.objects.filter(
                    target_rules__in=alert_rules,
                    is_active=True,
                    training_status='completed'
                ).distinct()
            
            for model in models:
                prediction = model.make_prediction()
                if prediction:
                    predictions.append({
                        'model_id': model.id,
                        'model_name': model.name,
                        'prediction_type': model.prediction_type,
                        'prediction': prediction
                    })
            
            return predictions
            
        except Exception as e:
            logger.error(f"Error making predictions: {e}")
            return []
    
    @staticmethod
    def evaluate_prediction_accuracy():
        """Evaluate accuracy of prediction models"""
        try:
            models = AlertPrediction.objects.filter(
                is_active=True,
                training_status='completed'
            )
            
            evaluations = []
            
            for model in models:
                # Compare predictions with actual outcomes
                accuracy_data = AlertPredictionService._evaluate_model_accuracy(model)
                
                evaluations.append({
                    'model_id': model.id,
                    'model_name': model.name,
                    'prediction_type': model.prediction_type,
                    'accuracy': accuracy_data
                })
            
            return evaluations
            
        except Exception as e:
            logger.error(f"Error evaluating prediction accuracy: {e}")
            return []
    
    @staticmethod
    def _evaluate_model_accuracy(model):
        """Evaluate accuracy of a specific model"""
        try:
            # Get recent predictions and actual outcomes
            # This is a simplified evaluation
            recent_period = timezone.now() - timedelta(days=7)
            
            if model.prediction_type == 'volume':
                actual_data = AlertPredictionService._get_volume_actuals(recent_period)
                predicted_data = model.make_prediction()
                
                if predicted_data and actual_data:
                    actual_volume = sum(actual_data.values())
                    predicted_volume = predicted_data.get('predicted_value', 0)
                    
                    # Calculate accuracy
                    if actual_volume > 0:
                        accuracy = max(0, 1 - abs(actual_volume - predicted_volume) / actual_volume)
                    else:
                        accuracy = 1.0 if predicted_volume == 0 else 0.0
                    
                    return {
                        'accuracy_score': accuracy,
                        'actual_volume': actual_volume,
                        'predicted_volume': predicted_volume,
                        'evaluation_period': '7_days'
                    }
            
            return {
                'accuracy_score': 0.5,  # Default accuracy
                'evaluation_period': '7_days'
            }
            
        except Exception as e:
            logger.error(f"Error evaluating model accuracy: {e}")
            return {
                'accuracy_score': 0.0,
                'error': str(e)
            }
    
    @staticmethod
    def _get_volume_actuals(period_start):
        """Get actual alert volume data"""
        try:
            from ..models.core import AlertLog
            
            daily_counts = {}
            current_date = period_start.date()
            
            for i in range(7):  # Last 7 days
                date = current_date + timedelta(days=i)
                count = AlertLog.objects.filter(triggered_at__date=date).count()
                daily_counts[date.isoformat()] = count
            
            return daily_counts
            
        except Exception as e:
            logger.error(f"Error getting volume actuals: {e}")
            return {}


class AnomalyDetectionService:
    """Anomaly detection service"""
    
    @staticmethod
    def run_anomaly_detection():
        """Run anomaly detection on all active models"""
        try:
            models = AnomalyDetectionModel.objects.filter(is_active=True)
            
            total_anomalies = []
            
            for model in models:
                anomalies = model.detect_anomalies()
                total_anomalies.extend(anomalies)
            
            logger.info(f"Detected {len(total_anomalies)} anomalies")
            return total_anomalies
            
        except Exception as e:
            logger.error(f"Error running anomaly detection: {e}")
            return []
    
    @staticmethod
    def get_anomaly_summary(hours=24):
        """Get anomaly detection summary"""
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)
            
            # Get recent anomalies (simulated)
            anomalies = AnomalyDetectionService.run_anomaly_detection()
            
            recent_anomalies = [
                anomaly for anomaly in anomalies
                if anomaly.get('detection_time', timezone.now()) >= cutoff_time
            ]
            
            # Group by type
            anomaly_types = {}
            for anomaly in recent_anomalies:
                anomaly_type = anomaly.get('type', 'unknown')
                anomaly_types[anomaly_type] = anomaly_types.get(anomaly_type, 0) + 1
            
            return {
                'period_hours': hours,
                'total_anomalies': len(recent_anomalies),
                'by_type': anomaly_types,
                'anomalies': recent_anomalies[:10]  # Top 10
            }
            
        except Exception as e:
            logger.error(f"Error getting anomaly summary: {e}")
            return None
    
    @staticmethod
    def create_anomaly_model(model_data):
        """Create new anomaly detection model"""
        try:
            model = AnomalyDetectionModel.objects.create(**model_data)
            
            logger.info(f"Created anomaly detection model: {model.name}")
            return model
            
        except Exception as e:
            logger.error(f"Error creating anomaly model: {e}")
            return None
    
    @staticmethod
    def update_anomaly_thresholds(model_id, new_thresholds):
        """Update anomaly detection thresholds"""
        try:
            model = AnomalyDetectionModel.objects.get(id=model_id)
            
            if 'sensitivity' in new_thresholds:
                model.sensitivity = new_thresholds['sensitivity']
            
            if 'anomaly_threshold' in new_thresholds:
                model.anomaly_threshold = new_thresholds['anomaly_threshold']
            
            if 'window_size_minutes' in new_thresholds:
                model.window_size_minutes = new_thresholds['window_size_minutes']
            
            model.save()
            
            logger.info(f"Updated thresholds for anomaly model {model_id}")
            return True
            
        except AnomalyDetectionModel.DoesNotExist:
            logger.error(f"Anomaly model {model_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error updating anomaly thresholds: {e}")
            return False


class NoiseFilterService:
    """Alert noise filtering service"""
    
    @staticmethod
    def filter_alerts(alert_logs):
        """Filter alerts through noise filters"""
        try:
            filters = AlertNoise.objects.filter(is_active=True)
            
            filtered_results = []
            
            for alert_log in alert_logs:
                filter_results = []
                
                for filter_config in filters:
                    result = filter_config.process_alert(alert_log)
                    if result:
                        filter_results.append({
                            'filter_id': filter_config.id,
                            'filter_name': filter_config.name,
                            'action': result['action'],
                            'reason': result.get('reason', ''),
                            'alert': alert_log
                        })
                
                if filter_results:
                    filtered_results.append({
                        'alert': alert_log,
                        'filters_applied': filter_results
                    })
            
            return filtered_results
            
        except Exception as e:
            logger.error(f"Error filtering alerts: {e}")
            return []
    
    @staticmethod
    def get_noise_effectiveness(days=30):
        """Get noise filter effectiveness metrics"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            filters = AlertNoise.objects.filter(is_active=True)
            
            effectiveness_data = []
            
            for filter_config in filters:
                score = filter_config.get_effectiveness_score()
                
                effectiveness_data.append({
                    'filter_id': filter_config.id,
                    'filter_name': filter_config.name,
                    'noise_type': filter_config.noise_type,
                    'action': filter_config.action,
                    'effectiveness_score': score,
                    'total_processed': filter_config.total_processed,
                    'total_suppressed': filter_config.total_suppressed,
                    'total_grouped': filter_config.total_grouped,
                    'total_delayed': filter_config.total_delayed
                })
            
            # Sort by effectiveness score
            effectiveness_data.sort(key=lambda x: x['effectiveness_score'], reverse=True)
            
            return effectiveness_data
            
        except Exception as e:
            logger.error(f"Error getting noise effectiveness: {e}")
            return []
    
    @staticmethod
    def create_noise_filter(filter_data):
        """Create new noise filter"""
        try:
            filter_config = AlertNoise.objects.create(**filter_data)
            
            logger.info(f"Created noise filter: {filter_config.name}")
            return filter_config
            
        except Exception as e:
            logger.error(f"Error creating noise filter: {e}")
            return None
    
    @staticmethod
    def optimize_noise_filters():
        """Optimize noise filter parameters"""
        try:
            filters = AlertNoise.objects.filter(is_active=True)
            
            optimizations = []
            
            for filter_config in filters:
                # Calculate current effectiveness
                current_score = filter_config.get_effectiveness_score()
                
                # Suggest optimizations based on performance
                suggestions = NoiseFilterService._generate_filter_suggestions(filter_config)
                
                optimizations.append({
                    'filter_id': filter_config.id,
                    'filter_name': filter_config.name,
                    'current_score': current_score,
                    'suggestions': suggestions
                })
            
            return optimizations
            
        except Exception as e:
            logger.error(f"Error optimizing noise filters: {e}")
            return []
    
    @staticmethod
    def _generate_filter_suggestions(filter_config):
        """Generate optimization suggestions for a filter"""
        suggestions = []
        
        # Analyze suppression rate
        if filter_config.total_processed > 0:
            suppression_rate = filter_config.total_suppressed / filter_config.total_processed
            
            if suppression_rate < 0.1:  # Less than 10% suppression
                suggestions.append({
                    'type': 'increase_sensitivity',
                    'message': 'Consider increasing sensitivity - current suppression rate is low'
                })
            elif suppression_rate > 0.8:  # More than 80% suppression
                suggestions.append({
                    'type': 'decrease_sensitivity',
                    'message': 'Consider decreasing sensitivity - current suppression rate is very high'
                })
        
        # Check action effectiveness
        if filter_config.action == 'suppress' and filter_config.total_suppressed > 100:
            suggestions.append({
                'type': 'consider_grouping',
                'message': 'High suppression volume - consider grouping instead of suppressing'
            })
        
        # Check filter age
        days_since_creation = (timezone.now() - filter_config.created_at).days
        if days_since_creation > 30:
            suggestions.append({
                'type': 'review_filter',
                'message': 'Filter is over 30 days old - consider reviewing and updating'
            })
        
        return suggestions


class RootCauseAnalysisService:
    """Root cause analysis service"""
    
    @staticmethod
    def perform_analysis_for_incident(incident_id, analysis_data):
        """Perform root cause analysis for an incident"""
        try:
            from ..models.incident import Incident
            
            incident = Incident.objects.get(id=incident_id)
            
            # Create RCA record
            rca = RootCauseAnalysis.objects.create(
                incident=incident,
                **analysis_data
            )
            
            # Perform the analysis
            rca.perform_analysis()
            
            logger.info(f"Completed RCA for incident {incident_id}")
            return rca
            
        except Incident.DoesNotExist:
            logger.error(f"Incident {incident_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error performing RCA: {e}")
            return None
    
    @staticmethod
    def get_rca_summary(days=30):
        """Get root cause analysis summary"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            rca_records = RootCauseAnalysis.objects.filter(
                created_at__gte=cutoff_date
            )
            
            summary = {
                'total_analyses': rca_records.count(),
                'by_status': {},
                'by_method': {},
                'completion_rate': 0,
                'average_confidence': 0
            }
            
            # By status
            status_stats = rca_records.values('status').annotate(count=models.Count('id'))
            for stat in status_stats:
                summary['by_status'][stat['status']] = stat['count']
            
            # By method
            method_stats = rca_records.values('analysis_method').annotate(count=models.Count('id'))
            for stat in method_stats:
                summary['by_method'][stat['analysis_method']] = stat['count']
            
            # Completion rate
            completed = rca_records.filter(status__in=['completed', 'verified']).count()
            summary['completion_rate'] = (completed / rca_records.count() * 100) if rca_records.count() > 0 else 0
            
            # Average confidence
            confidence_stats = rca_records.aggregate(
                avg_confidence=models.Avg(
                    models.Case(
                        models.When(confidence_level='high', then=4),
                        models.When(confidence_level='medium', then=3),
                        models.When(confidence_level='low', then=2),
                        models.When(confidence_level='very_high', then=5),
                        default=1,
                        output_field=models.IntegerField()
                    )
                )
            )
            
            summary['average_confidence'] = confidence_stats['avg_confidence'] or 0
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting RCA summary: {e}")
            return None
    
    @staticmethod
    def get_common_root_causes(days=90):
        """Get common root causes from recent analyses"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            rca_records = RootCauseAnalysis.objects.filter(
                created_at__gte=cutoff_date,
                status='completed'
            )
            
            # Aggregate root causes
            cause_frequency = {}
            
            for rca in rca_records:
                for cause in rca.root_causes:
                    cause_text = cause.get('cause', '')
                    if cause_text:
                        cause_frequency[cause_text] = cause_frequency.get(cause_text, 0) + 1
            
            # Sort by frequency
            common_causes = sorted(
                cause_frequency.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]  # Top 10
            
            return [
                {
                    'cause': cause,
                    'frequency': frequency,
                    'percentage': (frequency / rca_records.count() * 100) if rca_records.count() > 0 else 0
                }
                for cause, frequency in common_causes
            ]
            
        except Exception as e:
            logger.error(f"Error getting common root causes: {e}")
            return []
    
    @staticmethod
    def generate_recommendations_from_rca(rca_id):
        """Generate recommendations from RCA"""
        try:
            rca = RootCauseAnalysis.objects.get(id=rca_id)
            
            if rca.status != 'completed':
                rca.generate_recommendations()
            
            recommendations = {
                'immediate_actions': rca.immediate_actions,
                'preventive_actions': rca.preventive_actions,
                'long_term_improvements': rca.long_term_improvements
            }
            
            return recommendations
            
        except RootCauseAnalysis.DoesNotExist:
            logger.error(f"RCA {rca_id} not found")
            return None
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return None


class IntelligenceIntegrationService:
    """Integration service for all intelligence components"""
    
    @staticmethod
    def run_intelligence_pipeline():
        """Run complete intelligence analysis pipeline"""
        try:
            results = {
                'correlations': AlertCorrelationService.analyze_all_correlations(),
                'predictions': AlertPredictionService.make_predictions(),
                'anomalies': AnomalyDetectionService.run_anomaly_detection(),
                'timestamp': timezone.now().isoformat()
            }
            
            logger.info(f"Intelligence pipeline completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error running intelligence pipeline: {e}")
            return None
    
    @staticmethod
    def get_intelligence_dashboard_data():
        """Get comprehensive intelligence dashboard data"""
        try:
            dashboard_data = {
                'correlation_summary': AlertCorrelationService.get_correlation_summary(),
                'anomaly_summary': AnomalyDetectionService.get_anomaly_summary(),
                'noise_effectiveness': NoiseFilterService.get_noise_effectiveness(),
                'rca_summary': RootCauseAnalysisService.get_rca_summary(),
                'common_causes': RootCauseAnalysisService.get_common_root_causes(),
                'prediction_models': AlertPredictionService.evaluate_prediction_accuracy(),
                'last_updated': timezone.now().isoformat()
            }
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error getting intelligence dashboard data: {e}")
            return None
    
    @staticmethod
    def optimize_intelligence_models():
        """Optimize all intelligence models"""
        try:
            optimizations = {
                'noise_filters': NoiseFilterService.optimize_noise_filters(),
                'prediction_accuracy': AlertPredictionService.evaluate_prediction_accuracy(),
                'correlation_performance': AlertCorrelationService.get_correlation_summary()
            }
            
            logger.info("Intelligence model optimization completed")
            return optimizations
            
        except Exception as e:
            logger.error(f"Error optimizing intelligence models: {e}")
            return None
