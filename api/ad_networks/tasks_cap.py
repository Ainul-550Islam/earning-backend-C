"""
api/ad_networks/tasks_cap.py
Capitalized task definitions for ad networks module
SaaS-ready with tenant support
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from decimal import Decimal
from datetime import datetime, timedelta

from .models import (
    AdNetwork, Offer, UserOfferEngagement, OfferConversion,
    OfferReward, NetworkHealthCheck, UserWallet
)
from .choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus
)
from .constants import FRAUD_SCORE_THRESHOLD

logger = logging.getLogger(__name__)


# Offer-related capitalized tasks
@shared_task(name='ad_networks.SyncOffersFromNetworks')
def SyncOffersFromNetworks():
    """Sync offers from all active networks"""
    try:
        from .services.OfferSyncService import OfferSyncService
        
        networks = AdNetwork.objects.filter(
            is_active=True,
            status=NetworkStatus.ACTIVE
        )
        
        results = []
        for network in networks:
            try:
                service = OfferSyncService(tenant_id=network.tenant_id)
                result = service.sync_network_offers(network.id)
                results.append(result)
            except Exception as e:
                logger.error(f"Error syncing offers from {network.name}: {str(e)}")
                results.append({'success': False, 'error': str(e)})
        
        return {
            'success': True,
            'total_networks': len(networks),
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Error in SyncOffersFromNetworks: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.ProcessSingleOffer')
def ProcessSingleOffer(offer_id, tenant_id):
    """Process a single offer"""
    try:
        from .services.OfferSyncService import OfferSyncService
        
        service = OfferSyncService(tenant_id=tenant_id)
        result = service.process_offer_data(offer_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing offer {offer_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.ActivateOffer')
def ActivateOffer(offer_id, tenant_id):
    """Activate an offer"""
    try:
        offer = Offer.objects.get(id=offer_id, tenant_id=tenant_id)
        offer.status = OfferStatus.ACTIVE
        offer.save()
        
        # Clear cache
        cache.delete(f"offer_{offer_id}_{tenant_id}")
        
        # Send notification
        from .signals_cap import OfferActivated
        OfferActivated.send(sender=Offer, offer_id=offer_id, tenant_id=tenant_id)
        
        return {'success': True, 'offer_id': offer_id}
        
    except Offer.DoesNotExist:
        return {'success': False, 'error': 'Offer not found'}
    except Exception as e:
        logger.error(f"Error activating offer {offer_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.ExpireOffer')
def ExpireOffer(offer_id, tenant_id):
    """Expire an offer"""
    try:
        offer = Offer.objects.get(id=offer_id, tenant_id=tenant_id)
        offer.status = OfferStatus.EXPIRED
        offer.save()
        
        # Clear cache
        cache.delete(f"offer_{offer_id}_{tenant_id}")
        
        # Send notification
        from .signals_cap import OfferExpired
        OfferExpired.send(sender=Offer, offer_id=offer_id, tenant_id=tenant_id)
        
        return {'success': True, 'offer_id': offer_id}
        
    except Offer.DoesNotExist:
        return {'success': False, 'error': 'Offer not found'}
    except Exception as e:
        logger.error(f"Error expiring offer {offer_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


# Conversion-related capitalized tasks
@shared_task(name='ad_networks.ProcessConversion')
def ProcessConversion(conversion_id, tenant_id):
    """Process a conversion"""
    try:
        from .services.ConversionService import ConversionService
        
        service = ConversionService(tenant_id=tenant_id)
        result = service.process_conversion(conversion_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing conversion {conversion_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.ApproveConversion')
def ApproveConversion(conversion_id, tenant_id, notes=None):
    """Approve a conversion"""
    try:
        conversion = OfferConversion.objects.get(id=conversion_id, tenant_id=tenant_id)
        
        # Update conversion
        conversion.conversion_status = ConversionStatus.APPROVED
        conversion.approved_at = timezone.now()
        if notes:
            conversion.verification_notes = notes
        conversion.save()
        
        # Create reward
        from .services.RewardService import RewardService
        reward_service = RewardService(tenant_id=tenant_id)
        reward_result = reward_service.credit_reward(
            conversion.engagement,
            conversion.payout,
            'USD',
            'Conversion approved'
        )
        
        # Send notification
        from .signals_cap import ConversionApproved
        ConversionApproved.send(
            sender=OfferConversion,
            conversion_id=conversion_id,
            tenant_id=tenant_id
        )
        
        return {
            'success': True,
            'conversion_id': conversion_id,
            'reward_id': reward_result.get('reward_id')
        }
        
    except OfferConversion.DoesNotExist:
        return {'success': False, 'error': 'Conversion not found'}
    except Exception as e:
        logger.error(f"Error approving conversion {conversion_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.RejectConversion')
def RejectConversion(conversion_id, tenant_id, reason=None):
    """Reject a conversion"""
    try:
        conversion = OfferConversion.objects.get(id=conversion_id, tenant_id=tenant_id)
        
        # Update conversion
        conversion.conversion_status = ConversionStatus.REJECTED
        conversion.rejected_at = timezone.now()
        if reason:
            conversion.rejection_reason = reason
        conversion.save()
        
        # Send notification
        from .signals_cap import ConversionRejected
        ConversionRejected.send(
            sender=OfferConversion,
            conversion_id=conversion_id,
            tenant_id=tenant_id
        )
        
        return {'success': True, 'conversion_id': conversion_id}
        
    except OfferConversion.DoesNotExist:
        return {'success': False, 'error': 'Conversion not found'}
    except Exception as e:
        logger.error(f"Error rejecting conversion {conversion_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.FlagConversionAsFraud')
def FlagConversionAsFraud(conversion_id, tenant_id, fraud_score=100.0):
    """Flag a conversion as fraudulent"""
    try:
        conversion = OfferConversion.objects.get(id=conversion_id, tenant_id=tenant_id)
        
        # Update conversion
        conversion.fraud_score = fraud_score
        conversion.conversion_status = ConversionStatus.REJECTED
        conversion.rejected_at = timezone.now()
        conversion.rejection_reason = 'Flagged as fraudulent'
        conversion.save()
        
        # Send notification
        from .signals_cap import ConversionFlaggedAsFraud
        ConversionFlaggedAsFraud.send(
            sender=OfferConversion,
            conversion_id=conversion_id,
            tenant_id=tenant_id,
            fraud_score=fraud_score
        )
        
        return {'success': True, 'conversion_id': conversion_id}
        
    except OfferConversion.DoesNotExist:
        return {'success': False, 'error': 'Conversion not found'}
    except Exception as e:
        logger.error(f"Error flagging conversion {conversion_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.ProcessChargeback')
def ProcessChargeback(conversion_id, tenant_id):
    """Process a chargeback"""
    try:
        conversion = OfferConversion.objects.get(id=conversion_id, tenant_id=tenant_id)
        
        # Update conversion
        conversion.conversion_status = ConversionStatus.CHARGEBACK
        conversion.chargeback_at = timezone.now()
        conversion.save()
        
        # Reverse reward if exists
        try:
            reward = OfferReward.objects.get(
                engagement=conversion.engagement,
                tenant_id=tenant_id
            )
            
            from .services.RewardService import RewardService
            reward_service = RewardService(tenant_id=tenant_id)
            reward_service.reverse_reward(
                reward.id,
                'Chargeback processed'
            )
        except OfferReward.DoesNotExist:
            pass
        
        # Send notification
        from .signals_cap import ConversionChargeback
        ConversionChargeback.send(
            sender=OfferConversion,
            conversion_id=conversion_id,
            tenant_id=tenant_id
        )
        
        return {'success': True, 'conversion_id': conversion_id}
        
    except OfferConversion.DoesNotExist:
        return {'success': False, 'error': 'Conversion not found'}
    except Exception as e:
        logger.error(f"Error processing chargeback {conversion_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


# Reward-related capitalized tasks
@shared_task(name='ad_networks.ProcessReward')
def ProcessReward(reward_id, tenant_id):
    """Process a reward"""
    try:
        from .services.RewardService import RewardService
        
        service = RewardService(tenant_id=tenant_id)
        result = service.process_reward(reward_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing reward {reward_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.ApproveReward')
def ApproveReward(reward_id, tenant_id):
    """Approve a reward"""
    try:
        reward = OfferReward.objects.get(id=reward_id, tenant_id=tenant_id)
        
        # Update reward
        reward.status = RewardStatus.APPROVED
        reward.approved_at = timezone.now()
        reward.save()
        
        # Update wallet
        try:
            wallet = UserWallet.objects.get(user=reward.user, tenant_id=tenant_id)
            wallet.balance += reward.amount
            wallet.total_earned += reward.amount
            wallet.save()
        except UserWallet.DoesNotExist:
            # Create wallet if doesn't exist
            UserWallet.objects.create(
                user=reward.user,
                balance=reward.amount,
                total_earned=reward.amount,
                currency=reward.currency,
                tenant_id=tenant_id
            )
        
        # Send notification
        from .signals_cap import RewardApproved
        RewardApproved.send(
            sender=OfferReward,
            reward_id=reward_id,
            tenant_id=tenant_id
        )
        
        return {'success': True, 'reward_id': reward_id}
        
    except OfferReward.DoesNotExist:
        return {'success': False, 'error': 'Reward not found'}
    except Exception as e:
        logger.error(f"Error approving reward {reward_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.PayReward')
def PayReward(reward_id, tenant_id, payment_reference=None):
    """Mark a reward as paid"""
    try:
        reward = OfferReward.objects.get(id=reward_id, tenant_id=tenant_id)
        
        # Update reward
        reward.status = RewardStatus.PAID
        reward.paid_at = timezone.now()
        if payment_reference:
            reward.payment_reference = payment_reference
        reward.save()
        
        # Send notification
        from .signals_cap import RewardPaid
        RewardPaid.send(
            sender=OfferReward,
            reward_id=reward_id,
            tenant_id=tenant_id
        )
        
        return {'success': True, 'reward_id': reward_id}
        
    except OfferReward.DoesNotExist:
        return {'success': False, 'error': 'Reward not found'}
    except Exception as e:
        logger.error(f"Error paying reward {reward_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.CancelReward')
def CancelReward(reward_id, tenant_id, reason=None):
    """Cancel a reward"""
    try:
        reward = OfferReward.objects.get(id=reward_id, tenant_id=tenant_id)
        
        # Update reward
        reward.status = RewardStatus.CANCELLED
        reward.cancelled_at = timezone.now()
        if reason:
            reward.cancellation_reason = reason
        reward.save()
        
        # Update wallet (subtract if already added)
        try:
            wallet = UserWallet.objects.get(user=reward.user, tenant_id=tenant_id)
            wallet.balance -= reward.amount
            wallet.save()
        except UserWallet.DoesNotExist:
            pass
        
        # Send notification
        from .signals_cap import RewardCancelled
        RewardCancelled.send(
            sender=OfferReward,
            reward_id=reward_id,
            tenant_id=tenant_id
        )
        
        return {'success': True, 'reward_id': reward_id}
        
    except OfferReward.DoesNotExist:
        return {'success': False, 'error': 'Reward not found'}
    except Exception as e:
        logger.error(f"Error cancelling reward {reward_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


# Network-related capitalized tasks
@shared_task(name='ad_networks.CheckNetworkHealth')
def CheckNetworkHealth(network_id, tenant_id):
    """Check network health"""
    try:
        from .services.NetworkHealthService import NetworkHealthService
        
        service = NetworkHealthService(tenant_id=tenant_id)
        result = service.check_single_network(network_id)
        
        # Send notification
        from .signals_cap import NetworkHealthCheck
        NetworkHealthCheck.send(
            sender=AdNetwork,
            network_id=network_id,
            tenant_id=tenant_id,
            health_data=result
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error checking network health {network_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.SyncNetwork')
def SyncNetwork(network_id, tenant_id):
    """Sync a specific network"""
    try:
        from .services.OfferSyncService import OfferSyncService
        
        service = OfferSyncService(tenant_id=tenant_id)
        result = service.sync_network_offers(network_id)
        
        # Send notification
        if result['success']:
            from .signals_cap import NetworkSyncCompleted
            NetworkSyncCompleted.send(
                sender=AdNetwork,
                network_id=network_id,
                tenant_id=tenant_id,
                result=result
            )
        else:
            from .signals_cap import NetworkSyncFailed
            NetworkSyncFailed.send(
                sender=AdNetwork,
                network_id=network_id,
                tenant_id=tenant_id,
                error=result.get('error')
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Error syncing network {network_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


# Fraud-related capitalized tasks
@shared_task(name='ad_networks.DetectFraud')
def DetectFraud(conversion_id, tenant_id):
    """Detect fraud for a conversion"""
    try:
        from .services.FraudDetectionService import FraudDetectionService
        
        service = FraudDetectionService(tenant_id=tenant_id)
        result = service.analyze_conversion({'conversion_id': conversion_id}, None)
        
        if result['success']:
            fraud_score = result['analysis']['fraud_score']
            
            # Update conversion fraud score
            conversion = OfferConversion.objects.get(id=conversion_id, tenant_id=tenant_id)
            conversion.fraud_score = fraud_score
            conversion.save()
            
            # Send notification
            from .signals_cap import FraudScoreUpdated
            FraudScoreUpdated.send(
                sender=OfferConversion,
                conversion_id=conversion_id,
                tenant_id=tenant_id,
                fraud_score=fraud_score
            )
            
            # Flag as fraud if high score
            if fraud_score >= FRAUD_SCORE_THRESHOLD:
                from .signals_cap import FraudDetected
                FraudDetected.send(
                    sender=OfferConversion,
                    conversion_id=conversion_id,
                    tenant_id=tenant_id,
                    fraud_score=fraud_score
                )
        
        return result
        
    except OfferConversion.DoesNotExist:
        return {'success': False, 'error': 'Conversion not found'}
    except Exception as e:
        logger.error(f"Error detecting fraud for conversion {conversion_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.ProcessPendingRewards')
def ProcessPendingRewards(tenant_id):
    """Process all pending rewards"""
    try:
        from .services.RewardService import RewardService
        
        service = RewardService(tenant_id=tenant_id)
        result = service.process_pending_rewards()
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing pending rewards: {str(e)}")
        return {'success': False, 'error': str(e)}


# Analytics capitalized tasks
@shared_task(name='ad_networks.TrackOfferClick')
def TrackOfferClick(click_data):
    """Track offer click"""
    try:
        from .models import OfferClick
        
        click = OfferClick.objects.create(**click_data)
        
        # Send notification
        from .signals_cap import OfferClicked
        OfferClicked.send(
            sender=OfferClick,
            click_id=click.id,
            click_data=click_data
        )
        
        return {'success': True, 'click_id': click.id}
        
    except Exception as e:
        logger.error(f"Error tracking offer click: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.TrackEngagement')
def TrackEngagement(engagement_id, tenant_id):
    """Track user engagement"""
    try:
        engagement = UserOfferEngagement.objects.get(id=engagement_id, tenant_id=tenant_id)
        
        # Send notification
        from .signals_cap import EngagementTracked
        EngagementTracked.send(
            sender=UserOfferEngagement,
            engagement_id=engagement_id,
            tenant_id=tenant_id
        )
        
        return {'success': True, 'engagement_id': engagement_id}
        
    except UserOfferEngagement.DoesNotExist:
        return {'success': False, 'error': 'Engagement not found'}
    except Exception as e:
        logger.error(f"Error tracking engagement {engagement_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.TrackConversion')
def TrackConversion(conversion_id, tenant_id):
    """Track conversion"""
    try:
        conversion = OfferConversion.objects.get(id=conversion_id, tenant_id=tenant_id)
        
        # Send notification
        from .signals_cap import ConversionTracked
        ConversionTracked.send(
            sender=OfferConversion,
            conversion_id=conversion_id,
            tenant_id=tenant_id
        )
        
        return {'success': True, 'conversion_id': conversion_id}
        
    except OfferConversion.DoesNotExist:
        return {'success': False, 'error': 'Conversion not found'}
    except Exception as e:
        logger.error(f"Error tracking conversion {conversion_id}: {str(e)}")
        return {'success': False, 'error': str(e)}


# Maintenance capitalized tasks
@shared_task(name='ad_networks.CleanupExpiredCache')
def CleanupExpiredCache():
    """Clean up expired cache entries"""
    try:
        # This would integrate with your cache system
        # For now, just log
        logger.info("Cleaning up expired cache entries")
        
        # Send notification
        from .signals_cap import CacheCleared
        CacheCleared.send(sender=None, cache_type='expired')
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Error cleaning up expired cache: {str(e)}")
        return {'success': False, 'error': str(e)}


@shared_task(name='ad_networks.CleanupOldLogs')
def CleanupOldLogs(days=30):
    """Clean up old logs"""
    try:
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Clean up old network API logs
        from .models import NetworkAPILog
        deleted_count = NetworkAPILog.objects.filter(
            created_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old API logs")
        
        return {'success': True, 'deleted_count': deleted_count}
        
    except Exception as e:
        logger.error(f"Error cleaning up old logs: {str(e)}")
        return {'success': False, 'error': str(e)}


# Export all capitalized tasks
__all__ = [
    # Offer tasks
    'SyncOffersFromNetworks',
    'ProcessSingleOffer',
    'ActivateOffer',
    'ExpireOffer',
    
    # Conversion tasks
    'ProcessConversion',
    'ApproveConversion',
    'RejectConversion',
    'FlagConversionAsFraud',
    'ProcessChargeback',
    
    # Reward tasks
    'ProcessReward',
    'ApproveReward',
    'PayReward',
    'CancelReward',
    
    # Network tasks
    'CheckNetworkHealth',
    'SyncNetwork',
    
    # Fraud tasks
    'DetectFraud',
    'ProcessPendingRewards',
    
    # Analytics tasks
    'TrackOfferClick',
    'TrackEngagement',
    'TrackConversion',
    
    # Maintenance tasks
    'CleanupExpiredCache',
    'CleanupOldLogs'
]
