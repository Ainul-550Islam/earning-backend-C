# =============================================================================
# fraud_detection/receivers.py
# =============================================================================
"""
Signal Receivers for Fraud Detection System.

Provides Django signal receivers for automatic fraud detection
triggering, audit logging, and system event handling.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from django.db.models.signals import post_save, pre_save, post_delete, pre_delete
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.core.signals import request_started, request_finished
from django.utils import timezone
from django.contrib.auth import get_user_model

from api.fraud_detection.interactors import get_interactor
from api.fraud_detection.repositories import fraud_case_repository, fraud_alert_repository
from api.fraud_detection.monitoring import record_fraud_metric, record_fraud_alert
from api.fraud_detection.feature_flags import is_fraud_detection_enabled
from api.fraud_detection.exceptions import FraudDetectionError


logger = logging.getLogger(__name__)

User = get_user_model()


@receiver(post_save, sender=User)
def user_created_receiver(sender, instance: User, created: bool, **kwargs):
    """
    Receiver for user creation events.
    
    Triggers fraud detection analysis when new users are created.
    """
    if not created:
        return
    
    try:
        if not is_fraud_detection_enabled():
            return
        
        logger.info(f"New user created: {instance.id} - triggering fraud detection")
        
        # Analyze new user for fraud indicators
        fraud_detector = get_interactor('fraud_detection')
        
        context = {
            'ip_address': getattr(instance, 'last_login_ip', ''),
            'user_agent': getattr(instance, 'last_login_user_agent', ''),
            'registration_time': instance.date_joined.isoformat(),
            'email': instance.email,
            'username': instance.username
        }
        
        # Run fraud detection in background
        from api.fraud_detection.background_jobs import submit_fraud_detection_job
        submit_fraud_detection_job(instance.id, {}, context, priority='high')
        
        # Record metric
        record_fraud_metric('user_created', 1, {
            'user_id': instance.id,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in user creation receiver: {e}")


@receiver(pre_save, sender=User)
def user_pre_save_receiver(sender, instance: User, **kwargs):
    """
    Receiver for user pre-save events.
    
    Monitors for suspicious changes to user accounts.
    """
    try:
        if not instance.pk:
            return  # New user, handled by post_save
        
        # Get original user from database
        try:
            original_user = User.objects.get(pk=instance.pk)
        except User.DoesNotExist:
            return
        
        # Check for suspicious changes
        suspicious_changes = []
        
        # Email change
        if original_user.email != instance.email:
            suspicious_changes.append('email')
        
        # Password change (if password field is different)
        if hasattr(instance, 'password') and original_user.password != instance.password:
            suspicious_changes.append('password')
        
        # Other sensitive fields
        if hasattr(instance, 'is_active') and original_user.is_active != instance.is_active:
            suspicious_changes.append('is_active')
        
        if suspicious_changes:
            logger.warning(f"Suspicious user changes detected for user {instance.id}: {suspicious_changes}")
            
            # Record metric
            record_fraud_metric('suspicious_user_change', 1, {
                'user_id': instance.id,
                'changes': suspicious_changes,
                'timestamp': timezone.now().isoformat()
            })
            
    except Exception as e:
        logger.error(f"Error in user pre-save receiver: {e}")


@receiver(user_logged_in)
def user_login_receiver(sender, request, user: User, **kwargs):
    """
    Receiver for user login events.
    
    Analyzes login patterns for fraud indicators.
    """
    try:
        if not is_fraud_detection_enabled():
            return
        
        # Get login context
        ip_address = request.META.get('REMOTE_ADDR', '')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        logger.info(f"User login: {user.id} from IP {ip_address}")
        
        # Check for suspicious login patterns
        from api.fraud_detection.use_cases import SuspiciousPatternDetectionUseCase
        pattern_detector = SuspiciousPatternDetectionUseCase()
        
        # Analyze login pattern
        login_context = {
            'ip_address': ip_address,
            'user_agent': user_agent,
            'timestamp': timezone.now().isoformat(),
            'login_type': 'standard'
        }
        
        # Run pattern detection
        pattern_result = pattern_detector.execute(user.id, [login_context])
        
        if pattern_result['risk_score'] >= 50:
            logger.warning(f"Suspicious login pattern detected for user {user.id}: {pattern_result['risk_score']}")
            
            # Create fraud alert
            alert_data = {
                'alert_type': 'suspicious_login',
                'severity_score': pattern_result['risk_score'],
                'user_id': user.id,
                'description': f"Suspicious login pattern detected with risk score {pattern_result['risk_score']}",
                'details': {
                    'ip_address': ip_address,
                    'user_agent': user_agent,
                    'pattern_analysis': pattern_result
                }
            }
            
            record_fraud_alert(alert_data)
        
        # Record metric
        record_fraud_metric('user_login', 1, {
            'user_id': user.id,
            'ip_address': ip_address,
            'risk_score': pattern_result['risk_score']
        })
        
    except Exception as e:
        logger.error(f"Error in user login receiver: {e}")


@receiver(user_logged_out)
def user_logout_receiver(sender, request, user: User, **kwargs):
    """
    Receiver for user logout events.
    
    Logs user activity for fraud analysis.
    """
    try:
        logger.info(f"User logout: {user.id}")
        
        # Record metric
        record_fraud_metric('user_logout', 1, {
            'user_id': user.id,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in user logout receiver: {e}")


@receiver(request_started)
def request_started_receiver(sender, environ, **kwargs):
    """
    Receiver for request started events.
    
    Monitors incoming requests for fraud detection.
    """
    try:
        # Extract request information
        ip_address = environ.get('REMOTE_ADDR', '')
        user_agent = environ.get('HTTP_USER_AGENT', '')
        path = environ.get('PATH_INFO', '')
        method = environ.get('REQUEST_METHOD', '')
        
        # Skip static files and health checks
        if path.startswith('/static/') or path.startswith('/health/'):
            return
        
        # Record request metric
        record_fraud_metric('http_request', 1, {
            'ip_address': ip_address,
            'path': path,
            'method': method,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in request started receiver: {e}")


@receiver(request_finished)
def request_finished_receiver(sender, request=None, **kwargs):
    """
    Receiver for request finished events.
    
    Analyzes request patterns for fraud indicators.
    """
    try:
        # Analyze request patterns
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_id = request.user.id
            
            # Check for rapid requests from same user
            recent_requests = getattr(request, '_recent_requests', [])
            recent_requests.append(timezone.now())
            
            # Keep only last 10 requests
            if len(recent_requests) > 10:
                recent_requests.pop(0)
            
            # Check for suspicious patterns
            if len(recent_requests) >= 5:
                time_diff = recent_requests[-1] - recent_requests[-5]
                if time_diff.total_seconds() < 10:  # 5 requests in 10 seconds
                    logger.warning(f"Rapid requests detected from user {user_id}")
                    
                    record_fraud_metric('rapid_requests', 1, {
                        'user_id': user_id,
                        'requests_count': len(recent_requests),
                        'time_window': time_diff.total_seconds()
                    })
        
    except Exception as e:
        logger.error(f"Error in request finished receiver: {e}")


@receiver(post_save, sender="fraud_detection.FraudCase", dispatch_uid="fraud_case_post_save")
def fraud_case_post_save_receiver(sender, instance, created: bool, **kwargs):
    """
    Receiver for fraud case post-save events.
    
    Triggers notifications and monitoring updates.
    """
    try:
        if created:
            logger.info(f"New fraud case created: {instance.pk}")
            
            # Send notification
            from api.fraud_detection.notifications_push import send_case_notification
            send_case_notification({
                'case_id': instance.pk,
                'user_id': instance.user_id,
                'risk_score': instance.risk_score,
                'severity': instance.severity
            }, 'created')
            
            record_fraud_metric('fraud_case_created', 1, {
                'case_id': instance.pk,
                'user_id': instance.user_id,
                'risk_score': instance.risk_score
            })
        else:
            # Case updated
            if hasattr(instance, 'status') and instance.status == 'escalated':
                logger.warning(f"Fraud case escalated: {instance.pk}")
                
                from api.fraud_detection.notifications_push import send_case_notification
                send_case_notification({
                    'case_id': instance.pk,
                    'user_id': instance.user_id,
                    'risk_score': instance.risk_score,
                    'severity': instance.severity
                }, 'escalated')
                
                record_fraud_metric('fraud_case_escalated', 1, {
                    'case_id': instance.pk,
                    'user_id': instance.user_id
                })
        
    except Exception as e:
        logger.error(f"Error in fraud case post-save receiver: {e}")


@receiver(post_save, sender="fraud_detection.FraudAlert", dispatch_uid="fraud_alert_post_save")
def fraud_alert_post_save_receiver(sender, instance, created: bool, **kwargs):
    """
    Receiver for fraud alert post-save events.
    
    Triggers monitoring updates and notifications.
    """
    try:
        if created:
            logger.info(f"New fraud alert created: {instance.pk}")
            
            # Record alert metric
            record_fraud_metric('fraud_alert_created', 1, {
                'alert_id': instance.pk,
                'user_id': instance.user_id,
                'severity_score': instance.severity_score,
                'alert_type': instance.alert_type
            })
            
            # Send notification for high severity alerts
            if instance.severity_score >= 70:
                from api.fraud_detection.notifications_push import send_fraud_alert_notification
                send_fraud_alert_notification({
                    'alert_id': instance.pk,
                    'user_id': instance.user_id,
                    'alert_type': instance.alert_type,
                    'severity': 'high' if instance.severity_score >= 80 else 'medium',
                    'description': instance.description
                })
        
    except Exception as e:
        logger.error(f"Error in fraud alert post-save receiver: {e}")


@receiver(pre_delete, sender="fraud_detection.FraudCase", dispatch_uid="fraud_case_pre_delete")
def fraud_case_pre_delete_receiver(sender, instance, **kwargs):
    """
    Receiver for fraud case pre-delete events.
    
    Logs case deletion for audit trail.
    """
    try:
        logger.info(f"Fraud case being deleted: {instance.pk}")
        
        record_fraud_metric('fraud_case_deleted', 1, {
            'case_id': instance.pk,
            'user_id': instance.user_id,
            'status': instance.status
        })
        
    except Exception as e:
        logger.error(f"Error in fraud case pre-delete receiver: {e}")


class FraudSignalManager:
    """
    Manager for custom fraud detection signals.
    
    Provides methods for sending custom signals and
    managing signal subscriptions.
    """
    
    def __init__(self):
        """Initialize signal manager."""
        self._custom_signals = {}
        self._subscribers = {}
    
    def register_signal(self, signal_name: str):
        """Register a custom signal."""
        if signal_name not in self._custom_signals:
            from django.dispatch import Signal
            self._custom_signals[signal_name] = Signal()
            logger.info(f"Registered custom signal: {signal_name}")
    
    def get_signal(self, signal_name: str):
        """Get a registered signal."""
        if signal_name not in self._custom_signals:
            self.register_signal(signal_name)
        return self._custom_signals[signal_name]
    
    def send_signal(self, signal_name: str, **kwargs):
        """Send a custom signal."""
        signal = self.get_signal(signal_name)
        return signal.send(sender=self.__class__, **kwargs)
    
    def connect_receiver(self, signal_name: str, receiver_func):
        """Connect a receiver to a signal."""
        signal = self.get_signal(signal_name)
        signal.connect(receiver_func)
        
        if signal_name not in self._subscribers:
            self._subscribers[signal_name] = []
        self._subscribers[signal_name].append(receiver_func)
        
        logger.info(f"Connected receiver to signal: {signal_name}")
    
    def disconnect_receiver(self, signal_name: str, receiver_func):
        """Disconnect a receiver from a signal."""
        if signal_name in self._custom_signals:
            signal = self._custom_signals[signal_name]
            signal.disconnect(receiver_func)
            
            if signal_name in self._subscribers:
                try:
                    self._subscribers[signal_name].remove(receiver_func)
                except ValueError:
                    pass
            
            logger.info(f"Disconnected receiver from signal: {signal_name}")


# Global signal manager instance
fraud_signal_manager = FraudSignalManager()

# Register custom signals
fraud_signal_manager.register_signal('fraud_detection_completed')
fraud_signal_manager.register_signal('risk_score_updated')
fraud_signal_manager.register_signal('sanctions_flag_raised')
fraud_signal_manager.register_signal('pattern_detected')
fraud_signal_manager.register_signal('case_escalated')


@receiver(fraud_signal_manager.get_signal('fraud_detection_completed'))
def fraud_detection_completed_receiver(sender, **kwargs):
    """Receiver for fraud detection completion."""
    try:
        user_id = kwargs.get('user_id')
        result = kwargs.get('result')
        
        logger.info(f"Fraud detection completed for user {user_id}")
        
        record_fraud_metric('fraud_detection_completed', 1, {
            'user_id': user_id,
            'risk_score': result.get('final_risk_score', 0) if result else 0,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in fraud detection completed receiver: {e}")


@receiver(fraud_signal_manager.get_signal('risk_score_updated'))
def risk_score_updated_receiver(sender, **kwargs):
    """Receiver for risk score updates."""
    try:
        user_id = kwargs.get('user_id')
        old_score = kwargs.get('old_score', 0)
        new_score = kwargs.get('new_score', 0)
        reason = kwargs.get('reason', 'unknown')
        
        logger.info(f"Risk score updated for user {user_id}: {old_score} -> {new_score}")
        
        record_fraud_metric('risk_score_updated', 1, {
            'user_id': user_id,
            'old_score': old_score,
            'new_score': new_score,
            'change': new_score - old_score,
            'reason': reason
        })
        
        # Send notification for significant changes
        if abs(new_score - old_score) >= 30:
            from api.fraud_detection.notifications_push import send_risk_score_notification
            send_risk_score_notification(user_id, old_score, new_score, reason)
        
    except Exception as e:
        logger.error(f"Error in risk score updated receiver: {e}")


@receiver(fraud_signal_manager.get_signal('sanctions_flag_raised'))
def sanctions_flag_raised_receiver(sender, **kwargs):
    """Receiver for sanctions flag events."""
    try:
        user_id = kwargs.get('user_id')
        sanction_type = kwargs.get('sanction_type')
        details = kwargs.get('details', {})
        
        logger.warning(f"Sanctions flag raised for user {user_id}: {sanction_type}")
        
        record_fraud_metric('sanctions_flag_raised', 1, {
            'user_id': user_id,
            'sanction_type': sanction_type,
            'timestamp': timezone.now().isoformat()
        })
        
        # Send high-priority notification
        from api.fraud_detection.notifications_push import send_system_alert
        send_system_alert({
            'alert_type': 'sanctions_flag',
            'message': f"Sanctions flag raised: {sanction_type}",
            'user_id': user_id,
            'details': details
        }, priority='high')
        
    except Exception as e:
        logger.error(f"Error in sanctions flag raised receiver: {e}")


@receiver(fraud_signal_manager.get_signal('pattern_detected'))
def pattern_detected_receiver(sender, **kwargs):
    """Receiver for pattern detection events."""
    try:
        user_id = kwargs.get('user_id')
        pattern_type = kwargs.get('pattern_type')
        confidence = kwargs.get('confidence', 0)
        details = kwargs.get('details', {})
        
        logger.info(f"Pattern detected for user {user_id}: {pattern_type} (confidence: {confidence})")
        
        record_fraud_metric('pattern_detected', 1, {
            'user_id': user_id,
            'pattern_type': pattern_type,
            'confidence': confidence,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in pattern detected receiver: {e}")


@receiver(fraud_signal_manager.get_signal('case_escalated'))
def case_escalated_receiver(sender, **kwargs):
    """Receiver for case escalation events."""
    try:
        case_id = kwargs.get('case_id')
        user_id = kwargs.get('user_id')
        escalation_reason = kwargs.get('reason')
        
        logger.warning(f"Case escalated: {case_id} for user {user_id} - {escalation_reason}")
        
        record_fraud_metric('case_escalated', 1, {
            'case_id': case_id,
            'user_id': user_id,
            'reason': escalation_reason,
            'timestamp': timezone.now().isoformat()
        })
        
        # Send critical notification
        from api.fraud_detection.notifications_push import send_system_alert
        send_system_alert({
            'alert_type': 'case_escalation',
            'message': f"Case {case_id} escalated",
            'case_id': case_id,
            'user_id': user_id,
            'reason': escalation_reason
        }, priority='critical')
        
    except Exception as e:
        logger.error(f"Error in case escalated receiver: {e}")


# Convenience functions for sending custom signals
def send_fraud_detection_completed(user_id: Union[int, str], result: Dict[str, Any]):
    """Send fraud detection completed signal."""
    fraud_signal_manager.send_signal('fraud_detection_completed', user_id=user_id, result=result)


def send_risk_score_updated(user_id: Union[int, str], old_score: int, new_score: int, reason: str):
    """Send risk score updated signal."""
    fraud_signal_manager.send_signal('risk_score_updated', user_id=user_id, old_score=old_score, new_score=new_score, reason=reason)


def send_sanctions_flag_raised(user_id: Union[int, str], sanction_type: str, details: Dict[str, Any]):
    """Send sanctions flag raised signal."""
    fraud_signal_manager.send_signal('sanctions_flag_raised', user_id=user_id, sanction_type=sanction_type, details=details)


def send_pattern_detected(user_id: Union[int, str], pattern_type: str, confidence: float, details: Dict[str, Any]):
    """Send pattern detected signal."""
    fraud_signal_manager.send_signal('pattern_detected', user_id=user_id, pattern_type=pattern_type, confidence=confidence, details=details)


def send_case_escalated(case_id: Union[int, str], user_id: Union[int, str], reason: str):
    """Send case escalated signal."""
    fraud_signal_manager.send_signal('case_escalated', case_id=case_id, user_id=user_id, reason=reason)
