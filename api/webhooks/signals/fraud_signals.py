"""Fraud Detection Signals

This module contains signals related to fraud detection and prevention.
These signals are triggered when fraud-related events occur and can be used
to send webhook notifications to subscribed endpoints.
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import Signal
from django.utils import timezone
from django.contrib.auth import get_user_model

from ..services.core import DispatchService
from ..models import WebhookSubscription

User = get_user_model()


# Signal definitions
fraud_detected = Signal()
fraud_flagged = Signal()
fraud_cleared = Signal()
fraud_investigation_started = Signal()
fraud_investigation_completed = Signal()


def on_fraud_detected(sender, instance, created, **kwargs):
    """
    Signal handler for fraud detection.
    Emits 'fraud.detected' webhook event.
    """
    if not created:
        return
    
    # Prepare webhook payload
    payload = {
        'fraud_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'fraud_type': instance.fraud_type,
        'risk_score': instance.risk_score if hasattr(instance, 'risk_score') else 0,
        'severity': instance.severity if hasattr(instance, 'severity') else 'medium',
        'description': instance.description or '',
        'detected_at': instance.created_at.isoformat(),
        'source': instance.source if hasattr(instance, 'source') else 'system',
        'ip_address': instance.ip_address if hasattr(instance, 'ip_address') else '',
        'device_id': instance.device_id if hasattr(instance, 'device_id') else '',
        'transaction_id': instance.transaction_id if hasattr(instance, 'transaction_id') else '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for fraud events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='fraud.detected',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filter_config:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filter_config,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='fraud.detected',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending fraud detected webhook: {e}")


def on_fraud_flagged(sender, instance, **kwargs):
    """
    Signal handler for fraud flagging.
    Emits 'fraud.flagged' webhook event.
    """
    if instance.status != 'flagged':
        return
    
    # Prepare webhook payload
    payload = {
        'fraud_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'fraud_type': instance.fraud_type,
        'risk_score': instance.risk_score if hasattr(instance, 'risk_score') else 0,
        'severity': instance.severity if hasattr(instance, 'severity') else 'medium',
        'status': instance.status,
        'flagged_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'flagged_by': getattr(instance, 'flagged_by', {}).get('username') if hasattr(instance, 'flagged_by') else None,
        'flag_reason': getattr(instance, 'flag_reason', ''),
        'description': instance.description or '',
        'source': instance.source if hasattr(instance, 'source') else 'system',
        'ip_address': instance.ip_address if hasattr(instance, 'ip_address') else '',
        'device_id': instance.device_id if hasattr(instance, 'device_id') else '',
        'transaction_id': instance.transaction_id if hasattr(instance, 'transaction_id') else '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for fraud events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='fraud.flagged',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filter_config:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filter_config,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='fraud.flagged',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending fraud flagged webhook: {e}")


def on_fraud_cleared(sender, instance, **kwargs):
    """
    Signal handler for fraud clearance.
    Emits 'fraud.cleared' webhook event.
    """
    if instance.status != 'cleared':
        return
    
    # Prepare webhook payload
    payload = {
        'fraud_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'fraud_type': instance.fraud_type,
        'risk_score': instance.risk_score if hasattr(instance, 'risk_score') else 0,
        'severity': instance.severity if hasattr(instance, 'severity') else 'medium',
        'status': instance.status,
        'cleared_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'cleared_by': getattr(instance, 'cleared_by', {}).get('username') if hasattr(instance, 'cleared_by') else None,
        'clearance_reason': getattr(instance, 'clearance_reason', ''),
        'description': instance.description or '',
        'source': instance.source if hasattr(instance, 'source') else 'system',
        'ip_address': instance.ip_address if hasattr(instance, 'ip_address') else '',
        'device_id': instance.device_id if hasattr(instance, 'device_id') else '',
        'transaction_id': instance.transaction_id if hasattr(instance, 'transaction_id') else '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for fraud events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='fraud.cleared',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filter_config:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filter_config,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='fraud.cleared',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending fraud cleared webhook: {e}")


def on_fraud_investigation_started(sender, instance, **kwargs):
    """
    Signal handler for fraud investigation start.
    Emits 'fraud.investigation.started' webhook event.
    """
    if instance.investigation_status != 'started':
        return
    
    # Prepare webhook payload
    payload = {
        'fraud_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'fraud_type': instance.fraud_type,
        'risk_score': instance.risk_score if hasattr(instance, 'risk_score') else 0,
        'severity': instance.severity if hasattr(instance, 'severity') else 'medium',
        'investigation_status': instance.investigation_status,
        'investigation_started_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'investigator': getattr(instance, 'investigator', {}).get('username') if hasattr(instance, 'investigator') else None,
        'investigation_priority': getattr(instance, 'investigation_priority', 'medium'),
        'description': instance.description or '',
        'source': instance.source if hasattr(instance, 'source') else 'system',
        'ip_address': instance.ip_address if hasattr(instance, 'ip_address') else '',
        'device_id': instance.device_id if hasattr(instance, 'device_id') else '',
        'transaction_id': instance.transaction_id if hasattr(instance, 'transaction_id') else '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for fraud events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='fraud.investigation.started',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filter_config:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filter_config,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='fraud.investigation.started',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending fraud investigation started webhook: {e}")


def on_fraud_investigation_completed(sender, instance, **kwargs):
    """
    Signal handler for fraud investigation completion.
    Emits 'fraud.investigation.completed' webhook event.
    """
    if instance.investigation_status != 'completed':
        return
    
    # Prepare webhook payload
    payload = {
        'fraud_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'fraud_type': instance.fraud_type,
        'risk_score': instance.risk_score if hasattr(instance, 'risk_score') else 0,
        'severity': instance.severity if hasattr(instance, 'severity') else 'medium',
        'investigation_status': instance.investigation_status,
        'investigation_completed_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'investigator': getattr(instance, 'investigator', {}).get('username') if hasattr(instance, 'investigator') else None,
        'investigation_result': getattr(instance, 'investigation_result', ''),
        'investigation_notes': getattr(instance, 'investigation_notes', ''),
        'action_taken': getattr(instance, 'action_taken', ''),
        'description': instance.description or '',
        'source': instance.source if hasattr(instance, 'source') else 'system',
        'ip_address': instance.ip_address if hasattr(instance, 'ip_address') else '',
        'device_id': instance.device_id if hasattr(instance, 'device_id') else '',
        'transaction_id': instance.transaction_id if hasattr(instance, 'transaction_id') else '',
        'amount': str(instance.amount) if hasattr(instance, 'amount') else '0',
        'currency': instance.currency if hasattr(instance, 'currency') else 'USD',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for fraud events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='fraud.investigation.completed',
        is_active=True
    ).select_related('endpoint')
    
    for subscription in subscriptions:
        try:
            # Apply filters if configured
            if subscription.filter_config:
                from ..services.filtering import FilterService
                filter_service = FilterService()
                if not filter_service.evaluate_filter(
                    subscription.filter_config,
                    payload
                ):
                    continue
            
            # Send webhook
            dispatch_service.emit(
                endpoint=subscription.endpoint,
                event_type='fraud.investigation.completed',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending fraud investigation completed webhook: {e}")


# Connect signal handlers
def connect_fraud_signals():
    """Connect fraud-related signals to their handlers."""
    from apps.fraud.models import FraudCase, FraudDetection
    
    try:
        post_save.connect(on_fraud_detected, sender=FraudDetection)
        post_save.connect(on_fraud_flagged, sender=FraudCase)
        post_save.connect(on_fraud_cleared, sender=FraudCase)
        post_save.connect(on_fraud_investigation_started, sender=FraudCase)
        post_save.connect(on_fraud_investigation_completed, sender=FraudCase)
        
        print("Fraud signals connected successfully")
    except ImportError:
        # Fraud app not available
        print("Fraud app not available, skipping signal connections")
    except Exception as e:
        print(f"Error connecting fraud signals: {e}")


def disconnect_fraud_signals():
    """Disconnect fraud-related signals."""
    from apps.fraud.models import FraudCase, FraudDetection
    
    try:
        post_save.disconnect(on_fraud_detected, sender=FraudDetection)
        post_save.disconnect(on_fraud_flagged, sender=FraudCase)
        post_save.disconnect(on_fraud_cleared, sender=FraudCase)
        post_save.disconnect(on_fraud_investigation_started, sender=FraudCase)
        post_save.disconnect(on_fraud_investigation_completed, sender=FraudCase)
        
        print("Fraud signals disconnected successfully")
    except ImportError:
        # Fraud app not available
        print("Fraud app not available, skipping signal disconnection")
    except Exception as e:
        print(f"Error disconnecting fraud signals: {e}")
