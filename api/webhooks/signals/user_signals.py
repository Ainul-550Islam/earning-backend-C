"""User Signals

This module contains signals related to user account events.
These signals are triggered when user-related events occur and can be used
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
user_created = Signal()
user_updated = Signal()
user_profile_updated = Signal()
user_status_changed = Signal()
user_login = Signal()
user_logout = Signal()


def on_user_created(sender, instance, created, **kwargs):
    """
    Signal handler for user creation.
    Emits 'user.created' webhook event.
    """
    if not created:
        return
    
    # Prepare webhook payload
    payload = {
        'user_id': instance.id,
        'username': instance.username,
        'email': instance.email,
        'first_name': instance.first_name or '',
        'last_name': instance.last_name or '',
        'is_active': instance.is_active,
        'is_staff': instance.is_staff,
        'is_superuser': instance.is_superuser,
        'date_joined': instance.date_joined.isoformat(),
        'last_login': instance.last_login.isoformat() if instance.last_login else None,
        'created_at': instance.created_at.isoformat() if hasattr(instance, 'created_at') else instance.date_joined.isoformat(),
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for user events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='user.created',
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
                event_type='user.created',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending user created webhook: {e}")


def on_user_updated(sender, instance, **kwargs):
    """
    Signal handler for user updates.
    Emits 'user.updated' webhook event.
    """
    # Get previous state if available
    try:
        old_instance = sender.objects.get(pk=instance.pk)
        changes = {}
        
        # Check for changes in key fields
        if old_instance.username != instance.username:
            changes['username'] = {'old': old_instance.username, 'new': instance.username}
        
        if old_instance.email != instance.email:
            changes['email'] = {'old': old_instance.email, 'new': instance.email}
        
        if old_instance.first_name != instance.first_name:
            changes['first_name'] = {'old': old_instance.first_name, 'new': instance.first_name}
        
        if old_instance.last_name != instance.last_name:
            changes['last_name'] = {'old': old_instance.last_name, 'new': instance.last_name}
        
        if old_instance.is_active != instance.is_active:
            changes['is_active'] = {'old': old_instance.is_active, 'new': instance.is_active}
        
        if not changes:
            return  # No significant changes
        
    except sender.DoesNotExist:
        # User is being created, not updated
        return
    
    # Prepare webhook payload
    payload = {
        'user_id': instance.id,
        'username': instance.username,
        'email': instance.email,
        'first_name': instance.first_name or '',
        'last_name': instance.last_name or '',
        'is_active': instance.is_active,
        'is_staff': instance.is_staff,
        'is_superuser': instance.is_superuser,
        'changes': changes,
        'updated_at': timezone.now().isoformat(),
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for user events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='user.updated',
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
                event_type='user.updated',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending user updated webhook: {e}")


def on_user_profile_updated(sender, instance, **kwargs):
    """
    Signal handler for user profile updates.
    Emits 'user.profile.updated' webhook event.
    """
    # This would typically be connected to a UserProfile model
    # For now, we'll check if user has profile-related fields
    
    profile_fields = ['phone', 'address', 'date_of_birth', 'gender', 'avatar']
    
    # Check if any profile fields exist and have changed
    changes = {}
    for field in profile_fields:
        if hasattr(instance, field):
            changes[field] = getattr(instance, field)
    
    if not changes:
        return
    
    # Prepare webhook payload
    payload = {
        'user_id': instance.id,
        'username': instance.username,
        'email': instance.email,
        'profile_changes': changes,
        'updated_at': timezone.now().isoformat(),
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for user events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='user.profile.updated',
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
                event_type='user.profile.updated',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending user profile updated webhook: {e}")


def on_user_status_changed(sender, instance, **kwargs):
    """
    Signal handler for user status changes.
    Emits 'user.status.changed' webhook event.
    """
    # Get previous state if available
    try:
        old_instance = sender.objects.get(pk=instance.pk)
        
        if old_instance.is_active == instance.is_active:
            return  # No status change
        
        status_change = {
            'old_status': old_instance.is_active,
            'new_status': instance.is_active,
            'changed_at': timezone.now().isoformat()
        }
        
    except sender.DoesNotExist:
        # User is being created, not updated
        return
    
    # Prepare webhook payload
    payload = {
        'user_id': instance.id,
        'username': instance.username,
        'email': instance.email,
        'status_change': status_change,
        'is_active': instance.is_active,
        'metadata': getattr(instance, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for user events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='user.status.changed',
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
                event_type='user.status.changed',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending user status changed webhook: {e}")


def on_user_login(sender, request, user, **kwargs):
    """
    Signal handler for user login.
    Emits 'user.login' webhook event.
    """
    if not user or not user.is_authenticated:
        return
    
    # Prepare webhook payload
    payload = {
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'login_at': timezone.now().isoformat(),
        'ip_address': request.META.get('REMOTE_ADDR', ''),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'session_id': request.session.session_key,
        'metadata': getattr(user, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for user events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='user.login',
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
                event_type='user.login',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending user login webhook: {e}")


def on_user_logout(sender, request, user, **kwargs):
    """
    Signal handler for user logout.
    Emits 'user.logout' webhook event.
    """
    if not user or not user.is_authenticated:
        return
    
    # Prepare webhook payload
    payload = {
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'logout_at': timezone.now().isoformat(),
        'session_duration': None,  # Would need to track login time
        'ip_address': request.META.get('REMOTE_ADDR', ''),
        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
        'session_id': request.session.session_key,
        'metadata': getattr(user, 'metadata', {})
    }
    
    # Send webhook notifications
    dispatch_service = DispatchService()
    
    # Get active subscriptions for user events
    subscriptions = WebhookSubscription.objects.filter(
        event_type='user.logout',
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
                event_type='user.logout',
                payload=payload
            )
            
        except Exception as e:
            # Log error but continue with other subscriptions
            print(f"Error sending user logout webhook: {e}")


# Connect signal handlers
def connect_user_signals():
    """Connect user-related signals to their handlers."""
    try:
        from django.contrib.auth.signals import user_logged_in, user_logged_out
        
        post_save.connect(on_user_created, sender=User)
        post_save.connect(on_user_updated, sender=User)
        user_logged_in.connect(on_user_login)
        user_logged_out.connect(on_user_logout)
        
        print("User signals connected successfully")
    except Exception as e:
        print(f"Error connecting user signals: {e}")


def disconnect_user_signals():
    """Disconnect user-related signals."""
    try:
        from django.contrib.auth.signals import user_logged_in, user_logged_out
        
        post_save.disconnect(on_user_created, sender=User)
        post_save.disconnect(on_user_updated, sender=User)
        user_logged_in.disconnect(on_user_login)
        user_logged_out.disconnect(on_user_logout)
        
        print("User signals disconnected successfully")
    except Exception as e:
        print(f"Error disconnecting user signals: {e}")
