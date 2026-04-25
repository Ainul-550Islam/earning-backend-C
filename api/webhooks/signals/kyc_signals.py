"""KYC Signals

This module contains signals related to Know Your Customer (KYC) processes.
These signals are triggered when KYC-related events occur and can be used
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
kyc_submitted = Signal()
kyc_verified = Signal()
kyc_rejected = Signal()
kyc_status_changed = Signal()
kyc_document_uploaded = Signal()
kyc_review_started = Signal()


def on_kyc_submitted(sender, instance, created, **kwargs):
    """
    Signal handler for KYC submission.
    Emits 'kyc.submitted' webhook event.
    """
    if not created:
        return
    
    # Prepare webhook payload
    payload = {
        'kyc_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'kyc_type': instance.kyc_type if hasattr(instance, 'kyc_type') else 'standard',
        'status': instance.status if hasattr(instance, 'status') else 'submitted',
        'submitted_at': instance.created_at.isoformat(),
        'reference': instance.reference or '',
        'description': instance.description or '',
        'priority': getattr(instance, 'priority', 'normal'),
        'documents_count': getattr(instance, 'documents_count', 0),
        'required_documents': getattr(instance, 'required_documents', []),
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for KYC events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='kyc.submitted',
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
                event_type='kyc.submitted',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending KYC submitted webhook: {e}")


def on_kyc_verified(sender, instance, **kwargs):
    """
    Signal handler for KYC verification.
    Emits 'kyc.verified' webhook event.
    """
    if instance.status != 'verified':
        return
    
    # Prepare webhook payload
    payload = {
        'kyc_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'kyc_type': instance.kyc_type if hasattr(instance, 'kyc_type') else 'standard',
        'status': instance.status,
        'verified_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'verified_by': getattr(instance, 'verified_by', {}).get('username') if hasattr(instance, 'verified_by') else None,
        'verification_level': getattr(instance, 'verification_level', 'standard'),
        'expiry_date': instance.expiry_date.isoformat() if hasattr(instance, 'expiry_date') and instance.expiry_date else None,
        'reference': instance.reference or '',
        'description': instance.description or '',
        'documents_count': getattr(instance, 'documents_count', 0),
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for KYC events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='kyc.verified',
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
                event_type='kyc.verified',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending KYC verified webhook: {e}")


def on_kyc_rejected(sender, instance, **kwargs):
    """
    Signal handler for KYC rejection.
    Emits 'kyc.rejected' webhook event.
    """
    if instance.status != 'rejected':
        return
    
    # Prepare webhook payload
    payload = {
        'kyc_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'kyc_type': instance.kyc_type if hasattr(instance, 'kyc_type') else 'standard',
        'status': instance.status,
        'rejected_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'rejected_by': getattr(instance, 'rejected_by', {}).get('username') if hasattr(instance, 'rejected_by') else None,
        'rejection_reason': getattr(instance, 'rejection_reason', ''),
        'rejection_code': getattr(instance, 'rejection_code', ''),
        'reference': instance.reference or '',
        'description': instance.description or '',
        'documents_count': getattr(instance, 'documents_count', 0),
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for KYC events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='kyc.rejected',
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
                event_type='kyc.rejected',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending KYC rejected webhook: {e}")


def on_kyc_status_changed(sender, instance, **kwargs):
    """
    Signal handler for KYC status changes.
    Emits 'kyc.status.changed' webhook event.
    """
    # Get previous state if available
    try:
        old_instance = sender.objects.get(pk=instance.pk)
        
        if old_instance.status == instance.status:
            return  # No status change
        
        status_change = {
            'old_status': old_instance.status,
            'new_status': instance.status,
            'changed_at': timezone.now().isoformat()
        }
        
    except sender.DoesNotExist:
        # KYC is being created, not updated
        return
    
    # Prepare webhook payload
    payload = {
        'kyc_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'kyc_type': instance.kyc_type if hasattr(instance, 'kyc_type') else 'standard',
        'status_change': status_change,
        'current_status': instance.status,
        'reference': instance.reference or '',
        'description': instance.description or '',
        'documents_count': getattr(instance, 'documents_count', 0),
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for KYC events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='kyc.status.changed',
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
                event_type='kyc.status.changed',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending KYC status changed webhook: {e}")


def on_kyc_document_uploaded(sender, instance, created, **kwargs):
    """
    Signal handler for KYC document upload.
    Emits 'kyc.document.uploaded' webhook event.
    """
    if not created:
        return
    
    # Prepare webhook payload
    payload = {
        'document_id': str(instance.id),
        'kyc_id': str(instance.kyc.id) if hasattr(instance, 'kyc') else None,
        'user_id': instance.kyc.user.id if hasattr(instance, 'kyc') and instance.kyc.user else None,
        'document_type': instance.document_type if hasattr(instance, 'document_type') else 'unknown',
        'document_name': instance.document_name if hasattr(instance, 'document_name') else '',
        'file_size': instance.file_size if hasattr(instance, 'file_size') else 0,
        'mime_type': instance.mime_type if hasattr(instance, 'mime_type') else '',
        'uploaded_at': instance.created_at.isoformat(),
        'status': instance.status if hasattr(instance, 'status') else 'uploaded',
        'reference': instance.reference or '',
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for KYC events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='kyc.document.uploaded',
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
                event_type='kyc.document.uploaded',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending KYC document uploaded webhook: {e}")


def on_kyc_review_started(sender, instance, **kwargs):
    """
    Signal handler for KYC review start.
    Emits 'kyc.review.started' webhook event.
    """
    if instance.status != 'under_review':
        return
    
    # Prepare webhook payload
    payload = {
        'kyc_id': str(instance.id),
        'user_id': instance.user.id if instance.user else None,
        'kyc_type': instance.kyc_type if hasattr(instance, 'kyc_type') else 'standard',
        'status': instance.status,
        'review_started_at': instance.updated_at.isoformat() if instance.updated_at else None,
        'reviewer': getattr(instance, 'reviewer', {}).get('username') if hasattr(instance, 'reviewer') else None,
        'review_priority': getattr(instance, 'review_priority', 'normal'),
        'estimated_completion': getattr(instance, 'estimated_completion', ''),
        'reference': instance.reference or '',
        'description': instance.description or '',
        'documents_count': getattr(instance, 'documents_count', 0),
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for KYC events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='kyc.review.started',
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
                event_type='kyc.review.started',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending KYC review started webhook: {e}")


# Connect signal handlers
def connect_kyc_signals():
    """Connect KYC-related signals to their handlers."""
    from apps.kyc.models import KYCApplication, KYCDocument
    
    try:
        post_save.connect(on_kyc_submitted, sender=KYCApplication)
        post_save.connect(on_kyc_verified, sender=KYCApplication)
        post_save.connect(on_kyc_rejected, sender=KYCApplication)
        post_save.connect(on_kyc_status_changed, sender=KYCApplication)
        post_save.connect(on_kyc_review_started, sender=KYCApplication)
        post_save.connect(on_kyc_document_uploaded, sender=KYCDocument)
        
        print("KYC signals connected successfully")
    except ImportError:
        # KYC app not available
        print("KYC app not available, skipping signal connections")
    except Exception as e:
        print(f"Error connecting KYC signals: {e}")


def disconnect_kyc_signals():
    """Disconnect KYC-related signals."""
    from apps.kyc.models import KYCApplication, KYCDocument
    
    try:
        post_save.disconnect(on_kyc_submitted, sender=KYCApplication)
        post_save.disconnect(on_kyc_verified, sender=KYCApplication)
        post_save.disconnect(on_kyc_rejected, sender=KYCApplication)
        post_save.disconnect(on_kyc_status_changed, sender=KYCApplication)
        post_save.disconnect(on_kyc_review_started, sender=KYCApplication)
        post_save.disconnect(on_kyc_document_uploaded, sender=KYCDocument)
        
        print("KYC signals disconnected successfully")
    except ImportError:
        # KYC app not available
        print("KYC app not available, skipping signal disconnection")
    except Exception as e:
        print(f"Error disconnecting KYC signals: {e}")
