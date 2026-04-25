from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
import logging

from .models import OfferConversion
from api.users.models import User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=OfferConversion)
def credit_user_on_approval(sender, instance, created, **kwargs):
    """Credit user balance when conversion is approved"""
    try:
        with transaction.atomic():
            if instance.is_verified and instance.engagement.status != 'approved':
                engagement = instance.engagement
                user = engagement.user
                
                # Update engagement
                engagement.status = 'approved'
                engagement.reward_earned = instance.payout
                engagement.rewarded_at = timezone.now()
                engagement.save(update_fields=['status', 'reward_earned', 'rewarded_at'])
                
                # Credit user with proper validation
                if instance.payout and instance.payout > 0:
                    user.balance += instance.payout
                    user.save(update_fields=['balance'])
                    logger.info(f"Credited {instance.payout} to user {user.username} for conversion {instance.id}")
                else:
                    logger.warning(f"Invalid payout amount {instance.payout} for conversion {instance.id}")
                    
    except Exception as e:
        logger.error(f"Error processing conversion approval for conversion {instance.id}: {str(e)}")
        # Don't re-raise to avoid breaking the save operation


@receiver(post_save, sender=OfferConversion)
def update_network_statistics(sender, instance, created, **kwargs):
    """Update network statistics when conversion status changes"""
    try:
        if not created and hasattr(instance, '_original_status'):
            # Only update if status changed
            if instance._original_status != instance.conversion_status:
                from .services.NetworkHealthService import NetworkHealthService
                service = NetworkHealthService()
                service.update_network_stats(instance.engagement.offer.ad_network)
                logger.info(f"Updated network stats for {instance.engagement.offer.ad_network.name}")
    except Exception as e:
        logger.error(f"Error updating network statistics: {str(e)}")


@receiver(post_save, sender=OfferConversion)
def handle_fraud_detection(sender, instance, created, **kwargs):
    """Trigger fraud detection for new conversions"""
    try:
        if created:
            from .services.FraudDetectionService import FraudDetectionService
            fraud_service = FraudDetectionService()
            risk_score = fraud_service.analyze_conversion(instance)
            
            if risk_score > 70:  # High risk threshold
                logger.warning(f"High risk conversion detected: {instance.id} with score {risk_score}")
                # Could trigger additional verification steps here
                
    except Exception as e:
        logger.error(f"Error in fraud detection for conversion {instance.id}: {str(e)}")