"""
api/ad_networks/receivers.py
Signal receivers for ad networks module
SaaS-ready with tenant support
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models.signals import (
    pre_save, post_save, pre_delete, post_delete,
    m2m_changed, pre_init, post_init
)
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone
from django.contrib.auth.signals import user_logged_in, user_logged_out

from api.ad_networks.models import (
    AdNetwork, Offer, UserOfferEngagement, OfferConversion,
    OfferReward, NetworkHealthCheck, OfferCategory,
    UserWallet, OfferClick, KnownBadIP
)
from api.ad_networks.choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus
)
from api.ad_networks.constants import CACHE_KEY_PATTERNS

logger = logging.getLogger(__name__)


# AdNetwork signals
@receiver(pre_save, sender=AdNetwork)
def adnetwork_pre_save(sender, instance, **kwargs):
    """Handle AdNetwork pre-save signal"""
    # Validate network configuration
    if instance.is_active and not instance.api_key:
        logger.warning(f"Activating network {instance.name} without API key")
    
    # Set default values
    if not instance.priority:
        instance.priority = 50
    
    if not instance.trust_score:
        instance.trust_score = 50


@receiver(post_save, sender=AdNetwork)
def adnetwork_post_save(sender, instance, created, **kwargs):
    """Handle AdNetwork post-save signal"""
    # Clear relevant caches
    cache.delete_many([
        f"networks_list_{instance.tenant_id}",
        f"network_{instance.id}_{instance.tenant_id}",
        f"active_networks_{instance.tenant_id}"
    ])
    
    if created:
        logger.info(f"Created new network: {instance.name} (ID: {instance.id})")
        
        # Send notification
        from api.ad_networks.tasks import send_network_created_notification
        send_network_created_notification.delay(instance.id, instance.tenant_id)
    else:
        logger.info(f"Updated network: {instance.name} (ID: {instance.id})")
        
        # Check if status changed
        try:
            old_instance = sender.objects.get(id=instance.id)
            if old_instance.status != instance.status:
                from api.ad_networks.tasks import send_network_status_change_notification
                send_network_status_change_notification.delay(
                    instance.id, old_instance.status, instance.status, instance.tenant_id
                )
        except sender.DoesNotExist:
            pass


@receiver(pre_delete, sender=AdNetwork)
def adnetwork_pre_delete(sender, instance, **kwargs):
    """Handle AdNetwork pre-delete signal"""
    logger.info(f"Deleting network: {instance.name} (ID: {instance.id})")
    
    # Archive network data before deletion
    from api.ad_networks.tasks import archive_network_data
    archive_network_data.delay(instance.id, instance.tenant_id)


# Offer signals
@receiver(pre_save, sender=Offer)
def offer_pre_save(sender, instance, **kwargs):
    """Handle Offer pre-save signal"""
    # Validate offer data
    if instance.reward_amount <= 0:
        raise ValueError("Reward amount must be positive")
    
    # Set default values
    if not instance.status:
        instance.status = OfferStatus.PENDING_REVIEW
    
    if not instance.priority:
        instance.priority = 50
    
    # Set expiration if not set
    if not instance.expires_at and instance.status == OfferStatus.ACTIVE:
        instance.expires_at = timezone.now() + timedelta(days=30)


@receiver(post_save, sender=Offer)
def offer_post_save(sender, instance, created, **kwargs):
    """Handle Offer post-save signal"""
    # Clear relevant caches
    cache.delete_many([
        f"offers_list_{instance.tenant_id}",
        f"offer_{instance.id}_{instance.tenant_id}",
        f"offers_network_{instance.ad_network_id}_{instance.tenant_id}",
        f"offers_category_{instance.category_id}_{instance.tenant_id}" if instance.category_id else None
    ])
    
    if created:
        logger.info(f"Created new offer: {instance.title} (ID: {instance.id})")
        
        # Send notification
        from api.ad_networks.tasks import send_offer_created_notification
        send_offer_created_notification.delay(instance.id, instance.tenant_id)
    else:
        logger.info(f"Updated offer: {instance.title} (ID: {instance.id})")
        
        # Check if status changed to active
        try:
            old_instance = sender.objects.get(id=instance.id)
            if (old_instance.status != OfferStatus.ACTIVE and 
                instance.status == OfferStatus.ACTIVE):
                from api.ad_networks.tasks import send_offer_activated_notification
                send_offer_activated_notification.delay(instance.id, instance.tenant_id)
        except sender.DoesNotExist:
            pass


@receiver(pre_delete, sender=Offer)
def offer_pre_delete(sender, instance, **kwargs):
    """Handle Offer pre-delete signal"""
    logger.info(f"Deleting offer: {instance.title} (ID: {instance.id})")
    
    # Archive offer data before deletion
    from api.ad_networks.tasks import archive_offer_data
    archive_offer_data.delay(instance.id, instance.tenant_id)


# UserOfferEngagement signals
@receiver(pre_save, sender=UserOfferEngagement)
def engagement_pre_save(sender, instance, **kwargs):
    """Handle UserOfferEngagement pre-save signal"""
    # Set default values
    if not instance.status:
        instance.status = EngagementStatus.STARTED
    
    if not instance.started_at and instance.status == EngagementStatus.STARTED:
        instance.started_at = timezone.now()
    
    # Update completion time
    if (instance.status in [EngagementStatus.COMPLETED, EngagementStatus.APPROVED] and 
        not instance.completed_at):
        instance.completed_at = timezone.now()


@receiver(post_save, sender=UserOfferEngagement)
def engagement_post_save(sender, instance, created, **kwargs):
    """Handle UserOfferEngagement post-save signal"""
    # Clear user caches
    cache.delete_many([
        f"user_engagements_{instance.user_id}_{instance.tenant_id}",
        f"user_stats_{instance.user_id}_{instance.tenant_id}",
        f"offer_engagements_{instance.offer_id}_{instance.tenant_id}"
    ])
    
    if created:
        logger.info(f"Created new engagement: User {instance.user_id}, Offer {instance.offer_id}")
        
        # Track offer click if this is a click
        if instance.status == EngagementStatus.STARTED:
            from api.ad_networks.tasks import track_offer_engagement
            track_offer_engagement.delay(instance.id, instance.tenant_id)
    else:
        logger.info(f"Updated engagement: User {instance.user_id}, Offer {instance.offer_id}")
        
        # Check if completed
        if instance.status in [EngagementStatus.COMPLETED, EngagementStatus.APPROVED]:
            from api.ad_networks.tasks import process_engagement_completion
            process_engagement_completion.delay(instance.id, instance.tenant_id)


@receiver(pre_delete, sender=UserOfferEngagement)
def engagement_pre_delete(sender, instance, **kwargs):
    """Handle UserOfferEngagement pre-delete signal"""
    logger.info(f"Deleting engagement: User {instance.user_id}, Offer {instance.offer_id}")
    
    # Archive engagement data before deletion
    from api.ad_networks.tasks import archive_engagement_data
    archive_engagement_data.delay(instance.id, instance.tenant_id)


# OfferConversion signals
@receiver(pre_save, sender=OfferConversion)
def conversion_pre_save(sender, instance, **kwargs):
    """Handle OfferConversion pre-save signal"""
    # Set default values
    if not instance.conversion_status:
        instance.conversion_status = ConversionStatus.PENDING
    
    # Calculate fraud score if not set
    if instance.fraud_score is None:
        instance.fraud_score = calculate_initial_fraud_score(instance)
    
    # Set approval/rejection timestamps
    if instance.conversion_status == ConversionStatus.APPROVED and not instance.approved_at:
        instance.approved_at = timezone.now()
    elif instance.conversion_status == ConversionStatus.REJECTED and not instance.rejected_at:
        instance.rejected_at = timezone.now()
    elif instance.conversion_status == ConversionStatus.CHARGEBACK and not instance.chargeback_at:
        instance.chargeback_at = timezone.now()


@receiver(post_save, sender=OfferConversion)
def conversion_post_save(sender, instance, created, **kwargs):
    """Handle OfferConversion post-save signal"""
    # Clear conversion caches
    cache.delete_many([
        f"user_conversions_{instance.engagement.user_id}_{instance.tenant_id}",
        f"offer_conversions_{instance.engagement.offer_id}_{instance.tenant_id}",
        f"conversion_stats_{instance.tenant_id}"
    ])
    
    if created:
        logger.info(f"Created new conversion: User {instance.engagement.user_id}, Offer {instance.engagement.offer_id}")
        
        # Process conversion
        from api.ad_networks.tasks import process_new_conversion
        process_new_conversion.delay(instance.id, instance.tenant_id)
    else:
        logger.info(f"Updated conversion: User {instance.engagement.user_id}, Offer {instance.engagement.offer_id}")
        
        # Check status changes
        try:
            old_instance = sender.objects.get(id=instance.id)
            if old_instance.conversion_status != instance.conversion_status:
                from api.ad_networks.tasks import handle_conversion_status_change
                handle_conversion_status_change.delay(
                    instance.id, old_instance.conversion_status, 
                    instance.conversion_status, instance.tenant_id
                )
        except sender.DoesNotExist:
            pass


@receiver(pre_delete, sender=OfferConversion)
def conversion_pre_delete(sender, instance, **kwargs):
    """Handle OfferConversion pre-delete signal"""
    logger.info(f"Deleting conversion: User {instance.engagement.user_id}, Offer {instance.engagement.offer_id}")
    
    # Archive conversion data before deletion
    from api.ad_networks.tasks import archive_conversion_data
    archive_conversion_data.delay(instance.id, instance.tenant_id)


# OfferReward signals
@receiver(pre_save, sender=OfferReward)
def reward_pre_save(sender, instance, **kwargs):
    """Handle OfferReward pre-save signal"""
    # Set default values
    if not instance.status:
        instance.status = RewardStatus.PENDING
    
    # Set approval timestamp
    if instance.status == RewardStatus.APPROVED and not instance.approved_at:
        instance.approved_at = timezone.now()
    
    # Set payment timestamp
    if instance.status == RewardStatus.PAID and not instance.paid_at:
        instance.paid_at = timezone.now()
    
    # Set cancellation timestamp
    if instance.status == RewardStatus.CANCELLED and not instance.cancelled_at:
        instance.cancelled_at = timezone.now()


@receiver(post_save, sender=OfferReward)
def reward_post_save(sender, instance, created, **kwargs):
    """Handle OfferReward post-save signal"""
    # Clear reward caches
    cache.delete_many([
        f"user_rewards_{instance.user_id}_{instance.tenant_id}",
        f"user_wallet_{instance.user_id}_{instance.tenant_id}",
        f"reward_stats_{instance.tenant_id}"
    ])
    
    if created:
        logger.info(f"Created new reward: User {instance.user_id}, Amount {instance.amount}")
        
        # Process reward
        from api.ad_networks.tasks import process_new_reward
        process_new_reward.delay(instance.id, instance.tenant_id)
    else:
        logger.info(f"Updated reward: User {instance.user_id}, Amount {instance.amount}")
        
        # Check status changes
        try:
            old_instance = sender.objects.get(id=instance.id)
            if old_instance.status != instance.status:
                from api.ad_networks.tasks import handle_reward_status_change
                handle_reward_status_change.delay(
                    instance.id, old_instance.status, 
                    instance.status, instance.tenant_id
                )
        except sender.DoesNotExist:
            pass


@receiver(pre_delete, sender=OfferReward)
def reward_pre_delete(sender, instance, **kwargs):
    """Handle OfferReward pre-delete signal"""
    logger.info(f"Deleting reward: User {instance.user_id}, Amount {instance.amount}")
    
    # Archive reward data before deletion
    from api.ad_networks.tasks import archive_reward_data
    archive_reward_data.delay(instance.id, instance.tenant_id)


# UserWallet signals
@receiver(post_save, sender=UserWallet)
def wallet_post_save(sender, instance, created, **kwargs):
    """Handle UserWallet post-save signal"""
    # Clear wallet cache
    cache.delete(f"user_wallet_{instance.user_id}_{instance.tenant_id}")
    
    if created:
        logger.info(f"Created new wallet: User {instance.user_id}")
    else:
        logger.info(f"Updated wallet: User {instance.user_id}, Balance {instance.balance}")


# NetworkHealthCheck signals
@receiver(post_save, sender=NetworkHealthCheck)
def health_check_post_save(sender, instance, created, **kwargs):
    """Handle NetworkHealthCheck post-save signal"""
    # Clear health cache
    cache.delete_many([
        f"network_health_{instance.network_id}_{instance.tenant_id}",
        f"health_summary_{instance.tenant_id}"
    ])
    
    if created:
        logger.info(f"Created new health check: Network {instance.network_id}, Healthy: {instance.is_healthy}")
        
        # Check for health issues
        if not instance.is_healthy:
            from api.ad_networks.tasks import handle_network_health_issue
            handle_network_health_issue.delay(instance.id, instance.tenant_id)


# OfferClick signals
@receiver(post_save, sender=OfferClick)
def offer_click_post_save(sender, instance, created, **kwargs):
    """Handle OfferClick post-save signal"""
    if created:
        logger.info(f"New offer click: User {instance.user_id}, Offer {instance.offer_id}")
        
        # Track click analytics
        from api.ad_networks.tasks import track_click_analytics
        track_click_analytics.delay(instance.id, instance.tenant_id)


# KnownBadIP signals
@receiver(post_save, sender=KnownBadIP)
def known_bad_ip_post_save(sender, instance, created, **kwargs):
    """Handle KnownBadIP post-save signal"""
    if created:
        logger.info(f"Added new bad IP: {instance.ip_address}, Threat: {instance.threat_type}")
        
        # Update security systems
        from api.ad_networks.tasks import update_security_systems
        update_security_systems.delay(instance.ip_address, instance.tenant_id)


# User authentication signals
@receiver(user_logged_in)
def user_logged_in_handler(sender, request, user, **kwargs):
    """Handle user login"""
    logger.info(f"User logged in: {user.username} (ID: {user.id})")
    
    # Update last login
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])
    
    # Track login analytics
    from api.ad_networks.tasks import track_user_login
    track_user_login.delay(user.id, getattr(request, 'tenant_id', 'default'))


@receiver(user_logged_out)
def user_logged_out_handler(sender, request, user, **kwargs):
    """Handle user logout"""
    if user:
        logger.info(f"User logged out: {user.username} (ID: {user.id})")
        
        # Track logout analytics
        from api.ad_networks.tasks import track_user_logout
        track_user_logout.delay(user.id, getattr(request, 'tenant_id', 'default'))


# M2M changed signals
@receiver(m2m_changed, sender=Offer.countries.through)
def offer_countries_changed(sender, instance, action, pk_set, **kwargs):
    """Handle offer countries M2M change"""
    if action in ['post_add', 'post_remove', 'post_clear']:
        # Clear offer cache
        cache.delete(f"offer_{instance.id}_{instance.tenant_id}")
        
        logger.info(f"Offer countries changed: {instance.title} (ID: {instance.id})")


@receiver(m2m_changed, sender=Offer.platforms.through)
def offer_platforms_changed(sender, instance, action, pk_set, **kwargs):
    """Handle offer platforms M2M change"""
    if action in ['post_add', 'post_remove', 'post_clear']:
        # Clear offer cache
        cache.delete(f"offer_{instance.id}_{instance.tenant_id}")
        
        logger.info(f"Offer platforms changed: {instance.title} (ID: {instance.id})")


# Helper functions
def calculate_initial_fraud_score(conversion) -> float:
    """Calculate initial fraud score for conversion"""
    score = 0.0
    
    # Check engagement completion time
    if conversion.engagement and conversion.engagement.started_at:
        completion_time = conversion.created_at - conversion.engagement.started_at
        if completion_time.total_seconds() < 60:  # Less than 1 minute
            score += 30
        elif completion_time.total_seconds() < 300:  # Less than 5 minutes
            score += 15
    
    # Check payout amount
    if conversion.payout and conversion.payout > 100:
        score += 25
    elif conversion.payout and conversion.payout > 50:
        score += 10
    
    # Check IP address
    if conversion.engagement and conversion.engagement.ip_address:
        try:
            if KnownBadIP.objects.filter(
                ip_address=conversion.engagement.ip_address,
                is_active=True
            ).exists():
                score += 50
        except:
            pass
    
    return min(100.0, score)


# Cache cleanup signals
@receiver(pre_delete, sender=AdNetwork)
def cleanup_network_cache(sender, instance, **kwargs):
    """Clean up network-related caches"""
    cache.delete_many([
        f"network_{instance.id}_{instance.tenant_id}",
        f"network_offers_{instance.id}_{instance.tenant_id}",
        f"network_stats_{instance.id}_{instance.tenant_id}"
    ])


@receiver(pre_delete, sender=Offer)
def cleanup_offer_cache(sender, instance, **kwargs):
    """Clean up offer-related caches"""
    cache.delete_many([
        f"offer_{instance.id}_{instance.tenant_id}",
        f"offer_engagements_{instance.id}_{instance.tenant_id}",
        f"offer_conversions_{instance.id}_{instance.tenant_id}"
    ])


@receiver(pre_delete, sender=UserOfferEngagement)
def cleanup_engagement_cache(sender, instance, **kwargs):
    """Clean up engagement-related caches"""
    cache.delete_many([
        f"engagement_{instance.id}_{instance.tenant_id}",
        f"user_engagements_{instance.user_id}_{instance.tenant_id}",
        f"offer_engagements_{instance.offer_id}_{instance.tenant_id}"
    ])


# Periodic task signals
@receiver(pre_save, sender=Offer)
def schedule_offer_sync(sender, instance, **kwargs):
    """Schedule offer sync if needed"""
    if (instance.status == OfferStatus.ACTIVE and 
        instance.ad_network and 
        instance.ad_network.is_active):
        
        from api.ad_networks.tasks import sync_single_offer
        sync_single_offer.delay(instance.id, instance.tenant_id)


@receiver(post_save, sender=OfferConversion)
def update_network_statistics(sender, instance, **kwargs):
    """Update network statistics after conversion"""
    if instance.engagement and instance.engagement.offer:
        from api.ad_networks.tasks import update_network_stats
        update_network_stats.delay(
            instance.engagement.offer.ad_network_id, 
            instance.tenant_id
        )


# Error handling signals
@receiver(pre_save, sender=AdNetwork)
def validate_network_data(sender, instance, **kwargs):
    """Validate network data before save"""
    errors = []
    
    if not instance.name:
        errors.append("Network name is required")
    
    if not instance.network_type:
        errors.append("Network type is required")
    
    if instance.api_key and len(instance.api_key) < 10:
        errors.append("API key must be at least 10 characters")
    
    if errors:
        from django.core.exceptions import ValidationError
        raise ValidationError(errors)


@receiver(pre_save, sender=Offer)
def validate_offer_data(sender, instance, **kwargs):
    """Validate offer data before save"""
    errors = []
    
    if not instance.title:
        errors.append("Offer title is required")
    
    if not instance.reward_amount or instance.reward_amount <= 0:
        errors.append("Reward amount must be positive")
    
    if instance.expires_at and instance.expires_at < timezone.now():
        errors.append("Expiration date cannot be in the past")
    
    if errors:
        from django.core.exceptions import ValidationError
        raise ValidationError(errors)


# Analytics signals
@receiver(post_save, sender=UserOfferEngagement)
def track_engagement_analytics(sender, instance, created, **kwargs):
    """Track engagement analytics"""
    if created:
        from api.ad_networks.tasks import track_engagement_event
        track_engagement_event.delay(
            'engagement_created',
            {
                'user_id': instance.user_id,
                'offer_id': instance.offer_id,
                'status': instance.status,
                'tenant_id': instance.tenant_id
            }
        )


@receiver(post_save, sender=OfferConversion)
def track_conversion_analytics(sender, instance, created, **kwargs):
    """Track conversion analytics"""
    if created:
        from api.ad_networks.tasks import track_conversion_event
        track_conversion_event.delay(
            'conversion_created',
            {
                'user_id': instance.engagement.user_id,
                'offer_id': instance.engagement.offer_id,
                'amount': float(instance.payout),
                'status': instance.conversion_status,
                'fraud_score': instance.fraud_score,
                'tenant_id': instance.tenant_id
            }
        )


@receiver(post_save, sender=OfferReward)
def track_reward_analytics(sender, instance, created, **kwargs):
    """Track reward analytics"""
    if created:
        from api.ad_networks.tasks import track_reward_event
        track_reward_event.delay(
            'reward_created',
            {
                'user_id': instance.user_id,
                'offer_id': instance.offer_id,
                'amount': float(instance.amount),
                'status': instance.status,
                'tenant_id': instance.tenant_id
            }
        )


# Notification signals
@receiver(post_save, sender=OfferConversion)
def send_conversion_notifications(sender, instance, created, **kwargs):
    """Send conversion notifications"""
    if created and instance.conversion_status == ConversionStatus.APPROVED:
        from api.ad_networks.tasks import send_conversion_approved_notification
        send_conversion_approved_notification.delay(
            instance.engagement.user_id, 
            instance.id, 
            instance.tenant_id
        )


@receiver(post_save, sender=OfferReward)
def send_reward_notifications(sender, instance, created, **kwargs):
    """Send reward notifications"""
    if created and instance.status == RewardStatus.APPROVED:
        from api.ad_networks.tasks import send_reward_approved_notification
        send_reward_approved_notification.delay(
            instance.user_id, 
            instance.id, 
            instance.tenant_id
        )
