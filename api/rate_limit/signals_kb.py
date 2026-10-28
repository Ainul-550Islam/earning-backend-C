# api/rate_limit/signals_kb.py
"""
Knowledge base signals for rate limit module.

Provides signals for knowledge base operations and learning.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db.models import Count, Q, Avg

from api.rate_limit.models import RateLimitLog, RateLimitConfig, UserRateLimitProfile, AbuseReport
from api.rate_limit.logic import AbuseDetectionLogic, RateLimitOptimization

logger = logging.getLogger(__name__)


class KnowledgeBaseSignalHandler:
    """
    Handler for knowledge base related signals.
    """
    
    def __init__(self):
        self.learning_data = []
        self.patterns = {}
        self.anomalies = []
    
    def collect_learning_data(self, event_type: str, data: Dict[str, Any]):
        """
        Collect learning data from rate limit events.
        
        Args:
            event_type: Type of event
            data: Event data
        """
        learning_entry = {
            'event_type': event_type,
            'timestamp': timezone.now().isoformat(),
            'data': data
        }
        
        self.learning_data.append(learning_entry)
        
        # Keep only last 1000 entries
        if len(self.learning_data) > 1000:
            self.learning_data = self.learning_data[-1000:]
        
        logger.debug(f"Collected learning data: {event_type}")
    
    def detect_patterns(self) -> List[Dict[str, Any]]:
        """
        Detect patterns from collected learning data.
        
        Returns:
            List of detected patterns
        """
        patterns = []
        
        # Analyze recent data
        recent_data = self.learning_data[-100:] if len(self.learning_data) >= 100 else self.learning_data
        
        # Pattern 1: High frequency requests from same IP
        ip_requests = {}
        for entry in recent_data:
            if entry['event_type'] == 'rate_limit_exceeded':
                ip = entry['data'].get('ip_address')
                if ip:
                    ip_requests[ip] = ip_requests.get(ip, 0) + 1
        
        for ip, count in ip_requests.items():
            if count > 5:  # Threshold for pattern detection
                patterns.append({
                    'type': 'high_frequency_ip',
                    'ip_address': ip,
                    'count': count,
                    'severity': 'high' if count > 10 else 'medium',
                    'detected_at': timezone.now().isoformat()
                })
        
        # Pattern 2: Repeated abuse from same user
        user_abuse = {}
        for entry in recent_data:
            if entry['event_type'] == 'abuse_detected':
                user_id = entry['data'].get('user_id')
                if user_id:
                    user_abuse[user_id] = user_abuse.get(user_id, 0) + 1
        
        for user_id, count in user_abuse.items():
            if count > 3:  # Threshold for pattern detection
                patterns.append({
                    'type': 'repeated_abuse',
                    'user_id': user_id,
                    'count': count,
                    'severity': 'high' if count > 5 else 'medium',
                    'detected_at': timezone.now().isoformat()
                })
        
        # Pattern 3: Time-based anomalies
        hourly_events = {}
        for entry in recent_data:
            hour = datetime.fromisoformat(entry['timestamp']).hour
            event_type = entry['event_type']
            
            if hour not in hourly_events:
                hourly_events[hour] = {}
            
            hourly_events[hour][event_type] = hourly_events[hour].get(event_type, 0) + 1
        
        # Find unusual hours
        avg_events_per_hour = len(recent_data) / 24  # Average across 24 hours
        for hour, events in hourly_events.items():
            total_events = sum(events.values())
            if total_events > avg_events_per_hour * 3:  # 3x above average
                patterns.append({
                    'type': 'time_anomaly',
                    'hour': hour,
                    'event_count': total_events,
                    'events': events,
                    'severity': 'medium',
                    'detected_at': timezone.now().isoformat()
                })
        
        self.patterns = patterns
        return patterns
    
    def detect_anomalies(self) -> List[Dict[str, Any]]:
        """
        Detect anomalies from collected learning data.
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Analyze recent data
        recent_data = self.learning_data[-50:] if len(self.learning_data) >= 50 else self.learning_data
        
        # Anomaly 1: Sudden spike in rate limit exceeded events
        exceeded_events = [entry for entry in recent_data if entry['event_type'] == 'rate_limit_exceeded']
        
        if len(exceeded_events) > 20:  # Threshold for anomaly
            anomalies.append({
                'type': 'spike_rate_limit_exceeded',
                'count': len(exceeded_events),
                'severity': 'high',
                'detected_at': timezone.now().isoformat()
            })
        
        # Anomaly 2: Multiple abuse types from same IP
        ip_abuse_types = {}
        for entry in recent_data:
            if entry['event_type'] == 'abuse_detected':
                ip = entry['data'].get('ip_address')
                abuse_type = entry['data'].get('abuse_type')
                
                if ip and abuse_type:
                    if ip not in ip_abuse_types:
                        ip_abuse_types[ip] = set()
                    ip_abuse_types[ip].add(abuse_type)
        
        for ip, abuse_types in ip_abuse_types.items():
            if len(abuse_types) > 3:  # Multiple abuse types
                anomalies.append({
                    'type': 'multiple_abuse_types',
                    'ip_address': ip,
                    'abuse_types': list(abuse_types),
                    'severity': 'high',
                    'detected_at': timezone.now().isoformat()
                })
        
        # Anomaly 3: Unusual endpoint combinations
        endpoint_combinations = {}
        for entry in recent_data:
            if 'endpoint' in entry['data']:
                endpoint = entry['data']['endpoint']
                user_id = entry['data'].get('user_id')
                
                if endpoint and user_id:
                    key = f"{user_id}:{endpoint}"
                    endpoint_combinations[key] = endpoint_combinations.get(key, 0) + 1
        
        for combination, count in endpoint_combinations.items():
            if count > 15:  # Unusual frequency
                anomalies.append({
                    'type': 'unusual_endpoint_combination',
                    'combination': combination,
                    'count': count,
                    'severity': 'medium',
                    'detected_at': timezone.now().isoformat()
                })
        
        self.anomalies = anomalies
        return anomalies


# Global signal handler instance
kb_signal_handler = KnowledgeBaseSignalHandler()


@receiver(post_save, sender=RateLimitLog)
def rate_limit_log_kb_handler(sender, instance, created, **kwargs):
    """
    Handle rate limit log signals for knowledge base.
    
    Args:
        sender: Model class
        instance: Model instance
        created: Whether instance was created
        **kwargs: Additional arguments
    """
    if created:
        # Collect data for learning
        data = {
            'ip_address': instance.ip_address,
            'endpoint': instance.endpoint,
            'status': instance.status,
            'suspicion_score': instance.suspicion_score,
            'request_method': instance.request_method,
            'user_id': instance.user.id if instance.user else None
        }
        
        # Trigger pattern detection
        if instance.status == 'blocked':
            kb_signal_handler.collect_learning_data('rate_limit_exceeded', data)
        
        # Trigger anomaly detection if suspicious
        if instance.suspicion_score > 70:
            kb_signal_handler.collect_learning_data('suspicious_activity', data)


@receiver(post_save, sender=AbuseReport)
def abuse_report_kb_handler(sender, instance, created, **kwargs):
    """
    Handle abuse report signals for knowledge base.
    
    Args:
        sender: Model class
        instance: Model instance
        created: Whether instance was created
        **kwargs: Additional arguments
    """
    if created:
        # Collect data for learning
        data = {
            'abuse_type': instance.abuse_type,
            'severity': instance.severity,
            'ip_address': instance.ip_address,
            'user_id': instance.user.id if instance.user else None,
            'description': instance.description
        }
        
        kb_signal_handler.collect_learning_data('abuse_detected', data)
        
        # Trigger pattern detection
        if instance.severity >= 4:  # High severity
            kb_signal_handler.collect_learning_data('high_severity_abuse', data)


@receiver(pre_save, sender=RateLimitConfig)
def rate_limit_config_kb_handler(sender, instance, **kwargs):
    """
    Handle rate limit config signals for knowledge base.
    
    Args:
        sender: Model class
        instance: Model instance
        **kwargs: Additional arguments
    """
    # Collect configuration changes for learning
    if instance.pk:  # Update operation
        try:
            old_instance = RateLimitConfig.objects.get(pk=instance.pk)
            
            # Check for significant changes
            if (old_instance.requests_per_unit != instance.requests_per_unit or
                old_instance.time_unit != instance.time_unit or
                old_instance.is_active != instance.is_active):
                
                data = {
                    'config_id': instance.id,
                    'config_name': instance.name,
                    'old_requests_per_unit': old_instance.requests_per_unit,
                    'new_requests_per_unit': instance.requests_per_unit,
                    'old_time_unit': old_instance.time_unit,
                    'new_time_unit': instance.time_unit,
                    'old_is_active': old_instance.is_active,
                    'new_is_active': instance.is_active
                }
                
                kb_signal_handler.collect_learning_data('config_change', data)
        
        except RateLimitConfig.DoesNotExist:
            pass  # New instance, no old data to compare


class LearningEngine:
    """
    Learning engine for rate limit knowledge base.
    """
    
    def __init__(self):
        self.signal_handler = kb_signal_handler
        self.ml_models = {}
        self.training_data = []
    
    def train_models(self):
        """
        Train machine learning models from collected data.
        """
        try:
            logger.info("Training rate limit learning models...")
            
            # Get patterns and anomalies
            patterns = self.signal_handler.detect_patterns()
            anomalies = self.signal_handler.detect_anomalies()
            
            # Train anomaly detection model
            self._train_anomaly_detection_model(anomalies)
            
            # Train pattern recognition model
            self._train_pattern_recognition_model(patterns)
            
            # Train prediction model
            self._train_prediction_model()
            
            logger.info("Learning models trained successfully")
            
        except Exception as e:
            logger.error(f"Failed to train learning models: {str(e)}")
    
    def _train_anomaly_detection_model(self, anomalies: List[Dict[str, Any]]):
        """
        Train anomaly detection model.
        
        Args:
            anomalies: List of detected anomalies
        """
        # This would integrate with a machine learning library
        # For now, just store the patterns
        self.ml_models['anomaly_detection'] = {
            'patterns': anomalies,
            'trained_at': timezone.now().isoformat()
        }
    
    def _train_pattern_recognition_model(self, patterns: List[Dict[str, Any]]):
        """
        Train pattern recognition model.
        
        Args:
            patterns: List of detected patterns
        """
        self.ml_models['pattern_recognition'] = {
            'patterns': patterns,
            'trained_at': timezone.now().isoformat()
        }
    
    def _train_prediction_model(self):
        """
        Train prediction model for future events.
        """
        # This would implement predictive analytics
        self.ml_models['prediction'] = {
            'trained_at': timezone.now().isoformat()
        }
    
    def predict_abuse_probability(self, request_data: Dict[str, Any]) -> float:
        """
        Predict probability of abuse for a request.
        
        Args:
            request_data: Request data
            
        Returns:
            Abuse probability (0-1)
        """
        try:
            # Simple heuristic-based prediction
            probability = 0.0
            
            # Check IP history
            ip_address = request_data.get('ip_address')
            if ip_address:
                recent_logs = RateLimitLog.objects.filter(
                    ip_address=ip_address,
                    timestamp__gte=timezone.now() - timedelta(hours=24)
                )
                
                blocked_count = recent_logs.filter(status='blocked').count()
                total_count = recent_logs.count()
                
                if total_count > 0:
                    probability += (blocked_count / total_count) * 0.4
            
            # Check user history
            user_id = request_data.get('user_id')
            if user_id:
                try:
                    profile = UserRateLimitProfile.objects.get(user_id=user_id)
                    
                    # High suspicion score increases probability
                    if profile.suspicion_score > 70:
                        probability += 0.3
                    elif profile.suspicion_score > 50:
                        probability += 0.2
                    
                    # Low health score increases probability
                    if profile.api_health_score < 30:
                        probability += 0.2
                    elif profile.api_health_score < 50:
                        probability += 0.1
                
                except UserRateLimitProfile.DoesNotExist:
                    pass
            
            # Check endpoint
            endpoint = request_data.get('endpoint')
            if endpoint:
                # Check if endpoint is commonly abused
                abuse_reports = AbuseReport.objects.filter(
                    description__icontains=endpoint
                ).count()
                
                if abuse_reports > 10:
                    probability += 0.1
            
            return min(1.0, probability)
            
        except Exception as e:
            logger.error(f"Failed to predict abuse probability: {str(e)}")
            return 0.0
    
    def get_insights(self) -> Dict[str, Any]:
        """
        Get insights from learning engine.
        
        Returns:
            Insights dictionary
        """
        try:
            patterns = self.signal_handler.detect_patterns()
            anomalies = self.signal_handler.detect_anomalies()
            
            return {
                'patterns_detected': len(patterns),
                'anomalies_detected': len(anomalies),
                'patterns': patterns[:5],  # Top 5 patterns
                'anomalies': anomalies[:3],  # Top 3 anomalies
                'learning_data_count': len(self.signal_handler.learning_data),
                'models_trained': list(self.ml_models.keys()),
                'last_training': self.ml_models.get('prediction', {}).get('trained_at')
            }
            
        except Exception as e:
            logger.error(f"Failed to get insights: {str(e)}")
            return {'error': str(e)}


# Global learning engine instance
learning_engine = LearningEngine()


# Schedule periodic training
def schedule_periodic_training():
    """
    Schedule periodic training of learning models.
    """
    try:
        from django.core.management import call_command
        from celery import shared_task
        
        @shared_task
        def train_learning_models():
            learning_engine.train_models()
        
        # Schedule to run every hour
        train_learning_models.delay()
        
        logger.info("Scheduled periodic learning model training")
        
    except Exception as e:
        logger.error(f"Failed to schedule periodic training: {str(e)}")


# Auto-schedule on import
try:
    schedule_periodic_training()
except Exception as e:
    logger.error(f"Failed to auto-schedule training: {str(e)}")


# Export signal handlers and learning engine
__all__ = [
    'KnowledgeBaseSignalHandler',
    'LearningEngine',
    'kb_signal_handler',
    'learning_engine'
]
