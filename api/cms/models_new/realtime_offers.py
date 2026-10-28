# api/cms/models_new/realtime_offers.py
"""
Real-time Offer Updates System
Provides WebSocket-based real-time offer updates for users
"""
import uuid
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import models
from django.db.models import Q, F, Count, Avg
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.cache import cache
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)
User = get_user_model()


class RealTimeOfferUpdate(models.Model):
    """
    Track real-time offer updates and changes
    """
    UPDATE_TYPES = [
        ('new_offer', _('New Offer')),
        ('offer_updated', _('Offer Updated')),
        ('offer_expired', _('Offer Expired')),
        ('payout_changed', _('Payout Changed')),
        ('targeting_changed', _('Targeting Changed')),
        ('status_changed', _('Status Changed')),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    offer_id = models.CharField(_("Offer ID"), max_length=100, db_index=True)
    update_type = models.CharField(_("Update Type"), max_length=20, choices=UPDATE_TYPES)
    old_data = models.JSONField(_("Old Data"), default=dict, blank=True)
    new_data = models.JSONField(_("New Data"), default=dict, blank=True)
    
    # Targeting information
    countries = models.JSONField(_("Target Countries"), default=list, blank=True)
    devices = models.JSONField(_("Target Devices"), default=list, blank=True)
    min_age = models.PositiveIntegerField(_("Min Age"), null=True, blank=True)
    max_age = models.PositiveIntegerField(_("Max Age"), null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(_("Active"), default=True)
    priority = models.PositiveIntegerField(_("Priority"), default=0)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Real-time Offer Update")
        verbose_name_plural = _("Real-time Offer Updates")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['offer_id', 'created_at']),
            models.Index(fields=['update_type', 'is_active']),
            models.Index(fields=['countries']),
            models.Index(fields=['devices']),
            models.Index(fields=['priority', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_update_type_display()}: {self.offer_id}"
    
    def save(self, *args, **kwargs):
        # Auto-set expiry for certain update types
        if self.update_type in ['new_offer', 'offer_updated'] and not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)
    
    def is_relevant_for_user(self, user) -> bool:
        """Check if this update is relevant for a specific user"""
        if not self.is_active:
            return False
        
        # Check expiry
        if self.expires_at and self.expires_at < timezone.now():
            return False
        
        # Check country targeting
        if self.countries:
            user_country = getattr(user.profile, 'country', '') if hasattr(user, 'profile') else ''
            if not user_country or user_country not in self.countries:
                return False
        
        # Check device targeting
        if self.devices:
            # This would be determined from user's last session/device
            # For now, assume all devices are compatible
            pass
        
        # Check age targeting
        if self.min_age or self.max_age:
            if not hasattr(user, 'profile') or not user.profile.age:
                return False
            user_age = user.profile.age
            if self.min_age and user_age < self.min_age:
                return False
            if self.max_age and user_age > self.max_age:
                return False
        
        return True
    
    def get_notification_payload(self) -> dict:
        """Get payload for WebSocket notification"""
        return {
            'type': 'offer_update',
            'id': str(self.uuid),
            'offer_id': self.offer_id,
            'update_type': self.update_type,
            'old_data': self.old_data,
            'new_data': self.new_data,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }


class UserOfferSubscription(models.Model):
    """
    Track user subscriptions to real-time offer updates
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='offer_subscription')
    is_active = models.BooleanField(_("Active"), default=True)
    
    # Subscription preferences
    subscribe_new_offers = models.BooleanField(_("New Offers"), default=True)
    subscribe_updated_offers = models.BooleanField(_("Updated Offers"), default=True)
    subscribe_expired_offers = models.BooleanField(_("Expired Offers"), default=True)
    subscribe_payout_changes = models.BooleanField(_("Payout Changes"), default=True)
    
    # Filtering preferences
    min_payout = models.DecimalField(_("Min Payout"), max_digits=10, decimal_places=2, default=0)
    max_payout = models.DecimalField(_("Max Payout"), max_digits=10, decimal_places=2, default=999)
    preferred_countries = models.JSONField(_("Preferred Countries"), default=list, blank=True)
    preferred_categories = models.JSONField(_("Preferred Categories"), default=list, blank=True)
    
    # Notification settings
    notification_sound = models.BooleanField(_("Sound"), default=True)
    notification_desktop = models.BooleanField(_("Desktop"), default=True)
    notification_email = models.BooleanField(_("Email"), default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("User Offer Subscription")
        verbose_name_plural = _("User Offer Subscriptions")
    
    def is_subscribed_to_update_type(self, update_type: str) -> bool:
        """Check if user is subscribed to a specific update type"""
        mapping = {
            'new_offer': self.subscribe_new_offers,
            'offer_updated': self.subscribe_updated_offers,
            'offer_expired': self.subscribe_expired_offers,
            'payout_changed': self.subscribe_payout_changes,
        }
        return mapping.get(update_type, False)
    
    def should_receive_update(self, update: RealTimeOfferUpdate) -> bool:
        """Check if user should receive a specific update"""
        if not self.is_active:
            return False
        
        if not self.is_subscribed_to_update_type(update.update_type):
            return False
        
        # Check payout range
        if 'payout' in update.new_data:
            payout = Decimal(str(update.new_data.get('payout', 0)))
            if payout < self.min_payout or payout > self.max_payout:
                return False
        
        # Check country preferences
        if self.preferred_countries and update.countries:
            if not any(country in self.preferred_countries for country in update.countries):
                return False
        
        return True


class OfferUpdateQueue(models.Model):
    """
    Queue for processing offer updates in bulk
    """
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    batch_data = models.JSONField(_("Batch Data"))
    status = models.CharField(_("Status"), max_length=20, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(_("Error Message"), blank=True)
    
    class Meta:
        app_label = "cms"
        verbose_name = _("Offer Update Queue")
        verbose_name_plural = _("Offer Update Queues")
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Queue {self.uuid} - {self.status}"


# Service class for real-time updates
class RealTimeOfferService:
    """
    Service for managing real-time offer updates
    """
    
    @staticmethod
    def create_offer_update(offer_id: str, update_type: str, old_data: dict = None, 
                          new_data: dict = None, targeting: dict = None, 
                          priority: int = 0) -> RealTimeOfferUpdate:
        """Create a new real-time offer update"""
        update = RealTimeOfferUpdate.objects.create(
            offer_id=offer_id,
            update_type=update_type,
            old_data=old_data or {},
            new_data=new_data or {},
            countries=targeting.get('countries', []) if targeting else [],
            devices=targeting.get('devices', []) if targeting else [],
            min_age=targeting.get('min_age') if targeting else None,
            max_age=targeting.get('max_age') if targeting else None,
            priority=priority
        )
        
        # Queue for processing
        RealTimeOfferService._queue_update_processing(update)
        return update
    
    @staticmethod
    def _queue_update_processing(update: RealTimeOfferUpdate):
        """Queue update for processing"""
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'offer_updates',
            {
                'type': 'offer_update_created',
                'update_id': str(update.uuid)
            }
        )
    
    @staticmethod
    def send_update_to_user(user, update: RealTimeOfferUpdate):
        """Send real-time update to specific user"""
        if not update.is_relevant_for_user(user):
            return
        
        # Check user subscription
        try:
            subscription = user.offer_subscription
            if not subscription.should_receive_update(update):
                return
        except UserOfferSubscription.DoesNotExist:
            # Create default subscription
            subscription = UserOfferSubscription.objects.create(user=user)
        
        # Send WebSocket notification
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{user.id}_offers',
            {
                'type': 'offer_update',
                'data': update.get_notification_payload()
            }
        )
        
        # Mark as processed for this user
        update.processed_at = timezone.now()
        update.save(update_fields=['processed_at'])
    
    @staticmethod
    def broadcast_update(update: RealTimeOfferUpdate):
        """Broadcast update to all relevant users"""
        # Get all active users with subscriptions
        users = User.objects.filter(
            offer_subscription__is_active=True,
            is_active=True
        ).select_related('offer_subscription')
        
        for user in users:
            RealTimeOfferService.send_update_to_user(user, update)
    
    @staticmethod
    def get_user_updates(user, limit: int = 50) -> list:
        """Get recent updates for a user"""
        updates = RealTimeOfferUpdate.objects.filter(
            is_active=True
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).order_by('-priority', '-created_at')[:limit]
        
        # Filter for user relevance
        relevant_updates = []
        for update in updates:
            if update.is_relevant_for_user(user):
                relevant_updates.append(update.get_notification_payload())
        
        return relevant_updates
    
    @staticmethod
    def cleanup_expired_updates():
        """Clean up expired updates"""
        expired_count = RealTimeOfferUpdate.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()[0]
        
        logger.info(f"Cleaned up {expired_count} expired offer updates")
        return expired_count
