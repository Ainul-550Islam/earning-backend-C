"""
Intelligence Tasks
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from ..services.intelligence import (
    AlertCorrelationService, AlertPredictionService, AnomalyDetectionService,
    NoiseFilterService, RootCauseAnalysisService, IntelligenceIntegrationService
)

logger = logging.getLogger(__name__)


@shared_task
def analyze_all_correlations():
    """Analyze all pending alert correlations"""
    try:
        analyzed_count = AlertCorrelationService.analyze_all_correlations()
        logger.info(f"Analyzed {analyzed_count} alert correlations")
        return analyzed_count
        
    except Exception as e:
        logger.error(f"Error in analyze_all_correlations: {e}")
        return 0


@shared_task
def train_prediction_models():
    """Train all active prediction models"""
    try:
        trained_count = AlertPredictionService.train_all_models()
        logger.info(f"Trained {trained_count} prediction models")
        return trained_count
        
    except Exception as e:
        logger.error(f"Error in train_prediction_models: {e}")
        return 0


@shared_task
def detect_anomalies():
    """Run anomaly detection on all active models"""
    try:
        anomalies = AnomalyDetectionService.run_anomaly_detection()
        logger.info(f"Detected {len(anomalies)} anomalies")
        return len(anomalies)
        
    except Exception as e:
        logger.error(f"Error in detect_anomalies: {e}")
        return 0


@shared_task
def optimize_noise_filters():
    """Optimize noise filter parameters"""
    try:
        optimizations = NoiseFilterService.optimize_noise_filters()
        logger.info(f"Generated {len(optimizations)} noise filter optimizations")
        return optimizations
        
    except Exception as e:
        logger.error(f"Error in optimize_noise_filters: {e}")
        return []


@shared_task
def run_intelligence_pipeline():
    """Run complete intelligence analysis pipeline"""
    try:
        results = IntelligenceIntegrationService.run_intelligence_pipeline()
        logger.info(f"Intelligence pipeline completed: {results}")
        return results
        
    except Exception as e:
        logger.error(f"Error in run_intelligence_pipeline: {e}")
        return None


@shared_task
def update_correlation_insights():
    """Update correlation insights for recent alerts"""
    try:
        from ..models.intelligence import AlertCorrelation
        from ..models.core import AlertLog
        
        # Get recent alerts
        recent_alerts = AlertLog.objects.filter(
            triggered_at__gte=timezone.now() - timedelta(hours=24)
        )
        
        updated_count = 0
        for alert in recent_alerts:
            # Get correlation insights
            insights = AlertCorrelationService.get_correlation_insights(alert)
            
            # Store insights in alert details
            alert.details['correlation_insights'] = insights
            alert.save(update_fields=['details'])
            updated_count += 1
        
        logger.info(f"Updated correlation insights for {updated_count} alerts")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error in update_correlation_insights: {e}")
        return 0


@shared_task
def evaluate_model_accuracy():
    """Evaluate accuracy of prediction models"""
    try:
        evaluations = AlertPredictionService.evaluate_prediction_accuracy()
        logger.info(f"Evaluated {len(evaluations)} prediction models")
        return evaluations
        
    except Exception as e:
        logger.error(f"Error in evaluate_model_accuracy: {e}")
        return []


@shared_task
def generate_anomaly_report():
    """Generate anomaly detection report"""
    try:
        hours = 24
        summary = AnomalyDetectionService.get_anomaly_summary(hours)
        
        logger.info(f"Generated anomaly report for last {hours} hours: {summary}")
        return summary
        
    except Exception as e:
        logger.error(f"Error in generate_anomaly_report: {e}")
        return None


@shared_task
def update_noise_effectiveness():
    """Update noise filter effectiveness metrics"""
    try:
        days = 30
        effectiveness_data = NoiseFilterService.get_noise_effectiveness(days)
        
        # Update effectiveness for each filter
        from ..models.intelligence import AlertNoise
        
        updated_count = 0
        for filter_data in effectiveness_data:
            filter_id = filter_data['filter_id']
            effectiveness_score = filter_data['effectiveness_score']
            
            AlertNoise.objects.filter(id=filter_id).update(
                effectiveness_score=effectiveness_score
            )
            updated_count += 1
        
        logger.info(f"Updated effectiveness for {updated_count} noise filters")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error in update_noise_effectiveness: {e}")
        return 0


@shared_task
def create_rca_for_incidents():
    """Create root cause analysis for high-severity incidents"""
    try:
        from ..models.incident import Incident
        
        # Get recent high-severity incidents without RCA
        incidents = Incident.objects.filter(
            severity__in=['high', 'critical'],
            detected_at__gte=timezone.now() - timedelta(days=7)
        ).exclude(
            rca__isnull=False
        )
        
        created_count = 0
        for incident in incidents:
            # Create basic RCA
            analysis_data = {
                'title': f"RCA for {incident.title}",
                'description': "Automatically generated root cause analysis",
                'analysis_method': '5_whys'
            }
            
            rca = RootCauseAnalysisService.perform_analysis_for_incident(
                incident.id, analysis_data
            )
            
            if rca:
                created_count += 1
        
        logger.info(f"Created RCA for {created_count} incidents")
        return created_count
        
    except Exception as e:
        logger.error(f"Error in create_rca_for_incidents: {e}")
        return 0


@shared_task
def generate_intelligence_dashboard_data():
    """Generate intelligence dashboard data"""
    try:
        dashboard_data = IntelligenceIntegrationService.get_intelligence_dashboard_data()
        
        # Cache the dashboard data
        from django.core.cache import cache
        cache.set('intelligence_dashboard_data', dashboard_data, timeout=300)  # 5 minutes
        
        logger.info("Generated intelligence dashboard data")
        return dashboard_data
        
    except Exception as e:
        logger.error(f"Error in generate_intelligence_dashboard_data: {e}")
        return None


@shared_task
def cleanup_old_intelligence_data():
    """Clean up old intelligence data"""
    try:
        from ..models.intelligence import (
            AlertCorrelation, AlertPrediction, AnomalyDetectionModel,
            AlertNoise, RootCauseAnalysis
        )
        
        days_to_keep = 90
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        # Clean up old correlation history
        from ..models.intelligence import ThresholdHistory
        deleted_history = ThresholdHistory.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        # Clean up old health logs
        from ..models.channel import ChannelHealthLog
        deleted_health_logs = ChannelHealthLog.objects.filter(
            checked_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_history} correlation history and {deleted_health_logs} health logs")
        return {
            'correlation_history_deleted': deleted_history,
            'health_logs_deleted': deleted_health_logs
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_intelligence_data: {e}")
        return {'correlation_history_deleted': 0, 'health_logs_deleted': 0}


@shared_task
def train_correlation_model(correlation_id):
    """Train a specific correlation model"""
    try:
        from ..models.intelligence import AlertCorrelation
        
        correlation = AlertCorrelation.objects.get(id=correlation_id)
        correlation.analyze_correlation()
        
        logger.info(f"Trained correlation model {correlation_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error in train_correlation_model: {e}")
        return False


@shared_task
def test_prediction_model(model_id):
    """Test a specific prediction model"""
    try:
        from ..models.intelligence import AlertPrediction
        
        model = AlertPrediction.objects.get(id=model_id)
        prediction = model.make_prediction()
        
        logger.info(f"Tested prediction model {model_id}: {prediction}")
        return prediction
        
    except Exception as e:
        logger.error(f"Error in test_prediction_model: {e}")
        return None


@shared_task
def update_anomaly_thresholds():
    """Update anomaly detection thresholds automatically"""
    try:
        from ..models.intelligence import AnomalyDetectionModel
        
        models = AnomalyDetectionModel.objects.filter(is_active=True)
        updated_count = 0
        
        for model in models:
            # Calculate optimal thresholds based on recent data
            success = AnomalyDetectionService.update_anomaly_thresholds(
                model.id, {'sensitivity': model.sensitivity}
            )
            
            if success:
                updated_count += 1
        
        logger.info(f"Updated thresholds for {updated_count} anomaly models")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error in update_anomaly_thresholds: {e}")
        return 0


@shared_task
def generate_correlation_report():
    """Generate correlation analysis report"""
    try:
        days = 30
        summary = AlertCorrelationService.get_correlation_summary(days)
        
        logger.info(f"Generated correlation report for last {days} days: {summary}")
        return summary
        
    except Exception as e:
        logger.error(f"Error in generate_correlation_report: {e}")
        return None


@shared_task
def optimize_intelligence_models():
    """Optimize all intelligence models"""
    try:
        optimizations = IntelligenceIntegrationService.optimize_intelligence_models()
        
        logger.info(f"Optimized intelligence models: {optimizations}")
        return optimizations
        
    except Exception as e:
        logger.error(f"Error in optimize_intelligence_models: {e}")
        return None


@shared_task
def update_prediction_accuracy_metrics():
    """Update prediction accuracy metrics"""
    try:
        from ..models.intelligence import AlertPrediction
        
        models = AlertPrediction.objects.filter(training_status='completed')
        
        updated_count = 0
        for model in models:
            # Calculate and update accuracy metrics
            accuracy_data = AlertPredictionService._evaluate_model_accuracy(model)
            
            if accuracy_data:
                model.accuracy_score = accuracy_data.get('accuracy_score', 0)
                model.save(update_fields=['accuracy_score'])
                updated_count += 1
        
        logger.info(f"Updated accuracy metrics for {updated_count} models")
        return updated_count
        
    except Exception as e:
        logger.error(f"Error in update_prediction_accuracy_metrics: {e}")
        return 0
