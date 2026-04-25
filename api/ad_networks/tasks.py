"""
api/ad_networks/tasks.py
Scheduled tasks for ad networks module
SaaS-ready with Celery support
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction, connection
from django.db.models import Q, Count, Sum, Avg, F
from django.core.cache import cache
from datetime import timedelta, datetime
import logging
import json

from api.ad_networks.models import (
    AdNetwork, Offer, UserOfferEngagement, OfferConversion, 
    NetworkAPILog, NetworkHealthCheck, KnownBadIP, OfferClick
)
from api.ad_networks.services.AdNetworkFactory import AdNetworkFactory
from api.ad_networks.choices import OfferStatus, ConversionStatus, NetworkStatus
from api.ad_networks.constants import (
    OFFER_SYNC_INTERVAL,
    NETWORK_HEALTH_CHECK_INTERVAL,
    FRAUD_DETECTION_SCAN_INTERVAL,
    STATS_CALCULATION_INTERVAL,
    LOG_CLEANUP_INTERVAL,
    LOG_RETENTION_DAYS,
    FRAUD_SCORE_THRESHOLD,
    OFFER_CACHE_TTL,
    CACHE_KEY_PATTERNS
)

logger = logging.getLogger(__name__)


# ==================== OFFER SYNC TASKS ====================

@shared_task(bind=True, name='ad_networks.sync_offers_from_networks')
def sync_offers_from_networks(self, network_types=None, tenant_id=None):
    """
    Hourly offer sync from all active networks
    """
    logger.info(f"Starting offer sync for networks: {network_types or 'all'}")
    
    try:
        # Get networks to sync
        networks = AdNetwork.objects.filter(
            is_active=True,
            supports_offers=True
        )
        
        if network_types:
            networks = networks.filter(network_type__in=network_types)
        
        if tenant_id:
            networks = networks.filter(tenant_id=tenant_id)
        
        # Only sync networks that need it
        recent_sync = timezone.now() - timedelta(minutes=55)  # Sync every hour
        networks = networks.filter(
            Q(last_sync__isnull=True) | Q(last_sync__lt=recent_sync)
        )
        
        total_offers_synced = 0
        total_errors = 0
        
        for network in networks:
            try:
                offers_synced = _sync_single_network(network)
                total_offers_synced += offers_synced
                
                # Update network sync status
                network.last_sync = timezone.now()
                network.next_sync = timezone.now() + timedelta(hours=1)
                network.save(update_fields=['last_sync', 'next_sync'])
                
            except Exception as e:
                logger.error(f"Failed to sync {network.name}: {str(e)}")
                total_errors += 1
                
                # Log API error
                NetworkAPILog.objects.create(
                    network=network,
                    endpoint='sync',
                    method='TASK',
                    request_data={},
                    response_data={'error': str(e)},
                    status_code=500,
                    is_success=False,
                    error_message=str(e),
                    error_type='SYNC_ERROR'
                )
                continue
        
        # Clear offer caches
        cache.delete_pattern('offer_*')
        cache.delete_pattern('category_*')
        
        logger.info(f"Offer sync completed: {total_offers_synced} offers, {total_errors} errors")
        
        return {
            'total_offers_synced': total_offers_synced,
            'total_errors': total_errors,
            'networks_processed': networks.count()
        }
        
    except Exception as e:
        logger.error(f"Offer sync task failed: {str(e)}")
        raise self.retry(exc=e, countdown=300, max_retries=3)


def _sync_single_network(network):
    """Sync offers from a single network"""
    try:
        # Get network service
        service = AdNetworkFactory.get_service(network.network_type)
        if not service:
            return 0
        
        # Check network health first
        if not _check_network_health(network, service):
            return 0
        
        # Get offers from network
        offers_data = service.get_offers()
        if not offers_data:
            return 0
        
        # Process offers
        offers_synced = 0
        with transaction.atomic():
            for offer_data in offers_data:
                try:
                    _create_or_update_offer(network, offer_data)
                    offers_synced += 1
                except Exception as e:
                    logger.warning(f"Failed to process offer for {network.name}: {str(e)}")
                    continue
        
        # Log successful sync
        NetworkAPILog.objects.create(
            network=network,
            endpoint='offers',
            method='SYNC_TASK',
            request_data={},
            response_data={'offers_count': len(offers_data)},
            status_code=200,
            is_success=True,
            latency_ms=getattr(service, 'last_response_time', 0)
        )
        
        return offers_synced
        
    except Exception as e:
        # Log API error
        NetworkAPILog.objects.create(
            network=network,
            endpoint='offers',
            method='SYNC_TASK',
            request_data={},
            response_data={'error': str(e)},
            status_code=500,
            is_success=False,
            error_message=str(e),
            error_type='SYNC_TASK_ERROR'
        )
        raise e


def _create_or_update_offer(network, offer_data):
    """Create or update an offer from network data"""
    external_id = offer_data.get('external_id')
    if not external_id:
        return
    
    # Find existing offer
    offer = Offer.objects.filter(
        ad_network=network,
        external_id=external_id
    ).first()
    
    # Prepare offer data
    offer_fields = {
        'title': offer_data.get('title', '')[:255],
        'description': offer_data.get('description', ''),
        'reward_amount': offer_data.get('reward_amount', 0),
        'network_payout': offer_data.get('payout', 0),
        'click_url': offer_data.get('click_url', ''),
        'thumbnail': offer_data.get('thumbnail', ''),
        'countries': offer_data.get('countries', []),
        'platforms': offer_data.get('platforms', ['android', 'ios', 'web']),
        'device_type': offer_data.get('device_type', 'any'),
        'difficulty': offer_data.get('difficulty', 'easy'),
        'estimated_time': offer_data.get('estimated_time', 5),
        'max_conversions': offer_data.get('max_conversions'),
        'expires_at': offer_data.get('expires_at'),
        'status': 'active' if offer_data.get('is_available', True) else 'paused',
        'metadata': offer_data.get('metadata', {}),
    }
    
    if offer:
        # Update existing offer
        for field, value in offer_fields.items():
            setattr(offer, field, value)
        offer.save()
    else:
        # Create new offer
        offer_fields.update({
            'ad_network': network,
            'external_id': external_id,
        })
        offer = Offer.objects.create(**offer_fields)


# ==================== NETWORK STATS TASKS ====================

@shared_task(bind=True, name='ad_networks.calculate_network_stats')
def calculate_network_stats(self, tenant_id=None):
    """
    Daily statistics calculation for networks and offers
    """
    logger.info("Starting daily network stats calculation")
    
    try:
        # Get date range (last 24 hours)
        end_time = timezone.now()
        start_time = end_time - timedelta(days=1)
        
        # Calculate offer stats
        offers = Offer.objects.all()
        if tenant_id:
            offers = offers.filter(tenant_id=tenant_id)
        
        total_offers_updated = 0
        
        with transaction.atomic():
            for offer in offers:
                try:
                    # Calculate engagement stats
                    engagement_stats = UserOfferEngagement.objects.filter(
                        offer=offer,
                        created_at__gte=start_time,
                        created_at__lte=end_time
                    ).aggregate(
                        daily_conversions=Count(
                            'id',
                            filter=Q(status__in=['completed', 'approved'])
                        ),
                        daily_clicks=Count('id'),
                        avg_completion_time=Avg(
                            'completed_at',
                            filter=Q(status__in=['completed', 'approved'])
                        )
                    )
                    
                    # Calculate conversion stats
                    conversion_stats = OfferConversion.objects.filter(
                        engagement__offer=offer,
                        created_at__gte=start_time,
                        created_at__lte=end_time
                    ).aggregate(
                        daily_payout=Sum('payout'),
                        approved_conversions=Count(
                            'id',
                            filter=Q(conversion_status='approved')
                        ),
                        fraud_conversions=Count(
                            'id',
                            filter=Q(conversion_status='rejected')
                        )
                    )
                    
                    # Update offer with new stats
                    offer.daily_conversions = engagement_stats['daily_conversions'] or 0
                    offer.daily_clicks = engagement_stats['daily_clicks'] or 0
                    offer.daily_payout = conversion_stats['daily_payout'] or 0
                    offer.save(update_fields=['daily_conversions', 'daily_clicks', 'daily_payout'])
                    
                    total_offers_updated += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to calculate stats for offer {offer.id}: {str(e)}")
                    continue
        
        # Calculate network stats
        networks = AdNetwork.objects.all()
        if tenant_id:
            networks = networks.filter(tenant_id=tenant_id)
        
        total_networks_updated = 0
        
        with transaction.atomic():
            for network in networks:
                try:
                    # Aggregate stats from offers
                    network_stats = Offer.objects.filter(
                        ad_network=network,
                        created_at__gte=start_time,
                        created_at__lte=end_time
                    ).aggregate(
                        total_daily_conversions=Sum('daily_conversions'),
                        total_daily_clicks=Sum('daily_clicks'),
                        total_daily_payout=Sum('daily_payout')
                    )
                    
                    # Update network stats
                    network.daily_conversions = network_stats['total_daily_conversions'] or 0
                    network.daily_clicks = network_stats['total_daily_clicks'] or 0
                    network.daily_payout = network_stats['total_daily_payout'] or 0
                    network.save(update_fields=['daily_conversions', 'daily_clicks', 'daily_payout'])
                    
                    total_networks_updated += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to calculate stats for network {network.id}: {str(e)}")
                    continue
        
        logger.info(f"Stats calculation completed: {total_offers_updated} offers, {total_networks_updated} networks")
        
        return {
            'offers_updated': total_offers_updated,
            'networks_updated': total_networks_updated,
            'period': '24 hours'
        }
        
    except Exception as e:
        logger.error(f"Stats calculation failed: {str(e)}")
        raise self.retry(exc=e, countdown=300, max_retries=3)


# ==================== FRAUD DETECTION TASKS ====================

@shared_task(bind=True, name='ad_networks.detect_fraud_conversions')
def detect_fraud_conversions(self, tenant_id=None):
    """
    Scan pending conversions for fraud
    """
    logger.info("Starting fraud detection scan")
    
    try:
        # Get pending conversions from last hour
        end_time = timezone.now()
        start_time = end_time - timedelta(hours=1)
        
        conversions = OfferConversion.objects.filter(
            created_at__gte=start_time,
            created_at__lte=end_time,
            conversion_status=ConversionStatus.PENDING
        ).select_related('engagement__user', 'engagement__offer')
        
        if tenant_id:
            conversions = conversions.filter(tenant_id=tenant_id)
        
        total_conversions = conversions.count()
        fraud_detected = 0
        
        with transaction.atomic():
            for conversion in conversions:
                try:
                    fraud_score = _calculate_fraud_score(conversion)
                    
                    if fraud_score >= FRAUD_SCORE_THRESHOLD:
                        # Flag as fraudulent
                        conversion.fraud_score = fraud_score
                        conversion.conversion_status = ConversionStatus.REJECTED
                        conversion.risk_level = 'high' if fraud_score >= 80 else 'medium'
                        conversion.save(update_fields=['fraud_score', 'conversion_status', 'risk_level'])
                        fraud_detected += 1
                        
                        # Log fraud detection
                        logger.warning(
                            f"Fraud detected: Conversion {conversion.id} "
                            f"with score {fraud_score} for user {conversion.engagement.user_id}"
                        )
                    else:
                        # Update fraud score but keep pending
                        conversion.fraud_score = fraud_score
                        conversion.risk_level = 'low' if fraud_score < 30 else 'medium'
                        conversion.save(update_fields=['fraud_score', 'risk_level'])
                        
                except Exception as e:
                    logger.warning(f"Failed to analyze conversion {conversion.id}: {str(e)}")
                    continue
        
        logger.info(f"Fraud detection completed: {fraud_detected}/{total_conversions} flagged")
        
        return {
            'total_conversions': total_conversions,
            'fraud_detected': fraud_detected,
            'detection_rate': (fraud_detected / total_conversions * 100) if total_conversions > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Fraud detection failed: {str(e)}")
        raise self.retry(exc=e, countdown=300, max_retries=3)


def _calculate_fraud_score(conversion):
    """Calculate fraud score for a conversion"""
    score = 0
    engagement = conversion.engagement
    
    # Time-based fraud check
    if engagement.started_at and engagement.completed_at:
        completion_time = (engagement.completed_at - engagement.started_at).total_seconds()
        if completion_time < 30:  # Less than 30 seconds
            score += 30
    
    # IP-based fraud check
    recent_conversions_same_ip = OfferConversion.objects.filter(
        engagement__ip_address=engagement.ip_address,
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).count()
    
    if recent_conversions_same_ip > 5:
        score += 40
    
    # User velocity check
    recent_conversions_same_user = OfferConversion.objects.filter(
        engagement__user=engagement.user,
        created_at__gte=timezone.now() - timedelta(hours=1)
    ).count()
    
    if recent_conversions_same_user > 10:
        score += 50
    
    # Known bad IP check
    if KnownBadIP.objects.filter(
        ip_address=engagement.ip_address,
        is_active=True
    ).exists():
        score += 80
    
    return min(100, score)


# ==================== OFFER PERFORMANCE TASKS ====================

@shared_task(bind=True, name='ad_networks.update_offer_performance')
def update_offer_performance(self, tenant_id=None):
    """
    Update EPC, CR, and other performance metrics
    """
    logger.info("Starting offer performance update")
    
    try:
        # Get date range (last 7 days)
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)
        
        offers = Offer.objects.all()
        if tenant_id:
            offers = offers.filter(tenant_id=tenant_id)
        
        total_offers_updated = 0
        
        with transaction.atomic():
            for offer in offers:
                try:
                    # Calculate performance metrics
                    performance_stats = UserOfferEngagement.objects.filter(
                        offer=offer,
                        created_at__gte=start_time,
                        created_at__lte=end_time
                    ).aggregate(
                        total_clicks=Count('id'),
                        total_conversions=Count(
                            'id',
                            filter=Q(status__in=['completed', 'approved'])
                        ),
                        total_revenue=Sum(
                            'reward_earned',
                            filter=Q(status='approved')
                        ),
                        avg_completion_time=Avg(
                            'completed_at',
                            filter=Q(status__in=['completed', 'approved'])
                        )
                    )
                    
                    total_clicks = performance_stats['total_clicks'] or 0
                    total_conversions = performance_stats['total_conversions'] or 0
                    total_revenue = performance_stats['total_revenue'] or 0
                    
                    # Calculate metrics
                    conversion_rate = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
                    epc = (total_revenue / total_clicks) if total_clicks > 0 else 0
                    
                    # Update offer
                    offer.conversion_rate = conversion_rate
                    offer.epc = epc
                    offer.avg_completion_time = performance_stats['avg_completion_time'] or 0
                    offer.quality_score = min(10, conversion_rate / 10)  # Simple quality score
                    offer.save(update_fields=['conversion_rate', 'epc', 'avg_completion_time', 'quality_score'])
                    
                    total_offers_updated += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to update performance for offer {offer.id}: {str(e)}")
                    continue
        
        # Clear performance caches
        cache.delete_pattern('offer_*_performance')
        
        logger.info(f"Performance update completed: {total_offers_updated} offers updated")
        
        return {
            'offers_updated': total_offers_updated,
            'period': '7 days'
        }
        
    except Exception as e:
        logger.error(f"Performance update failed: {str(e)}")
        raise self.retry(exc=e, countdown=300, max_retries=3)


# ==================== OFFER EXPIRATION TASKS ====================

@shared_task(bind=True, name='ad_networks.expire_old_offers')
def expire_old_offers(self, tenant_id=None):
    """
    Auto-expire inactive or expired offers
    """
    logger.info("Starting offer expiration task")
    
    try:
        now = timezone.now()
        total_expired = 0
        
        # Expire offers with explicit expiry date
        expired_offers = Offer.objects.filter(
            expires_at__lt=now,
            status=OfferStatus.ACTIVE
        )
        
        if tenant_id:
            expired_offers = expired_offers.filter(tenant_id=tenant_id)
        
        with transaction.atomic():
            for offer in expired_offers:
                offer.status = OfferStatus.EXPIRED
                offer.save(update_fields=['status'])
                total_expired += 1
                
                logger.info(f"Expired offer {offer.id}: {offer.title}")
        
        # Deactivate offers with no recent activity (30 days)
        inactive_threshold = now - timedelta(days=30)
        inactive_offers = Offer.objects.filter(
            status=OfferStatus.ACTIVE,
            updated_at__lt=inactive_threshold,
            total_conversions__lt=5  # Less than 5 conversions
        )
        
        if tenant_id:
            inactive_offers = inactive_offers.filter(tenant_id=tenant_id)
        
        with transaction.atomic():
            for offer in inactive_offers:
                offer.status = OfferStatus.PAUSED
                offer.save(update_fields=['status'])
                total_expired += 1
                
                logger.info(f"Paused inactive offer {offer.id}: {offer.title}")
        
        # Clear offer caches
        cache.delete_pattern('offer_*')
        cache.delete_pattern('category_*')
        
        logger.info(f"Offer expiration completed: {total_expired} offers processed")
        
        return {
            'total_expired': total_expired,
            'explicitly_expired': expired_offers.count(),
            'inactive_paused': inactive_offers.count()
        }
        
    except Exception as e:
        logger.error(f"Offer expiration failed: {str(e)}")
        raise self.retry(exc=e, countdown=300, max_retries=3)


# ==================== IP BLACKLIST SYNC TASKS ====================

@shared_task(bind=True, name='ad_networks.sync_blacklisted_ips')
def sync_blacklisted_ips(self, tenant_id=None):
    """
    Update IP blacklist from external sources
    """
    logger.info("Starting IP blacklist sync")
    
    try:
        total_ips_added = 0
        total_ips_updated = 0
        
        # This would integrate with external IP blacklist services
        # For demo, we'll just clean up expired entries
        
        # Deactivate expired blacklist entries
        expired_entries = KnownBadIP.objects.filter(
            expires_at__lt=timezone.now(),
            is_active=True
        )
        
        if tenant_id:
            expired_entries = expired_entries.filter(tenant_id=tenant_id)
        
        with transaction.atomic():
            for entry in expired_entries:
                entry.is_active = False
                entry.save(update_fields=['is_active'])
                total_ips_updated += 1
        
        # Clean up old inactive entries (older than 90 days)
        cleanup_threshold = timezone.now() - timedelta(days=90)
        old_entries = KnownBadIP.objects.filter(
            is_active=False,
            updated_at__lt=cleanup_threshold
        )
        
        if tenant_id:
            old_entries = old_entries.filter(tenant_id=tenant_id)
        
        deleted_count = old_entries.count()
        old_entries.delete()
        
        logger.info(f"IP blacklist sync completed: {total_ips_added} added, {total_ips_updated} updated, {deleted_count} deleted")
        
        return {
            'ips_added': total_ips_added,
            'ips_updated': total_ips_updated,
            'ips_deleted': deleted_count
        }
        
    except Exception as e:
        logger.error(f"IP blacklist sync failed: {str(e)}")
        raise self.retry(exc=e, countdown=300, max_retries=3)


# ==================== LOG CLEANUP TASKS ====================

@shared_task(bind=True, name='ad_networks.cleanup_old_webhook_logs')
def cleanup_old_webhook_logs(self, tenant_id=None):
    """
    Delete old webhook and API logs
    """
    logger.info("Starting log cleanup task")
    
    try:
        # Calculate cleanup threshold
        cleanup_threshold = timezone.now() - timedelta(days=LOG_RETENTION_DAYS)
        total_deleted = 0
        
        # Clean up API logs
        api_logs = NetworkAPILog.objects.filter(
            request_timestamp__lt=cleanup_threshold
        )
        
        if tenant_id:
            api_logs = api_logs.filter(tenant_id=tenant_id)
        
        api_logs_count = api_logs.count()
        api_logs.delete()
        total_deleted += api_logs_count
        
        # Clean up health check logs
        health_logs = NetworkHealthCheck.objects.filter(
            checked_at__lt=cleanup_threshold
        )
        
        if tenant_id:
            health_logs = health_logs.filter(tenant_id=tenant_id)
        
        health_logs_count = health_logs.count()
        health_logs.delete()
        total_deleted += health_logs_count
        
        logger.info(f"Log cleanup completed: {total_deleted} entries deleted")
        
        return {
            'total_deleted': total_deleted,
            'api_logs_deleted': api_logs_count,
            'health_logs_deleted': health_logs_count,
            'retention_days': LOG_RETENTION_DAYS
        }
        
    except Exception as e:
        logger.error(f"Log cleanup failed: {str(e)}")
        raise self.retry(exc=e, countdown=300, max_retries=3)


# ==================== HELPER FUNCTIONS ====================

def _check_network_health(network, service):
    """Check if network is healthy"""
    try:
        is_healthy = service.health_check()
        
        # Create health check record
        NetworkHealthCheck.objects.create(
            network=network,
            is_healthy=is_healthy,
            check_type='api_call',
            endpoint_checked=getattr(service, 'base_url', ''),
            response_time_ms=getattr(service, 'last_response_time', 0)
        )
        
        return is_healthy
        
    except Exception as e:
        logger.warning(f"Health check failed for {network.name}: {str(e)}")
        
        # Create failed health check record
        NetworkHealthCheck.objects.create(
            network=network,
            is_healthy=False,
            check_type='api_call',
            endpoint_checked=getattr(service, 'base_url', ''),
            error=str(e),
            error_type='HEALTH_CHECK_ERROR'
        )
        
        return False


# ==================== TASK SCHEDULE CONFIGURATION ====================

# Celery beat schedule configuration
CELERYBEAT_SCHEDULE = {
    'sync-offers-hourly': {
        'task': 'ad_networks.sync_offers_from_networks',
        'schedule': timedelta(hours=1),
        'options': {'queue': 'ad_networks'}
    },
    'calculate-stats-daily': {
        'task': 'ad_networks.calculate_network_stats',
        'schedule': timedelta(hours=1),
        'options': {'queue': 'ad_networks'}
    },
    'detect-fraud-every-10-minutes': {
        'task': 'ad_networks.detect_fraud_conversions',
        'schedule': timedelta(minutes=10),
        'options': {'queue': 'ad_networks'}
    },
    'update-performance-daily': {
        'task': 'ad_networks.update_offer_performance',
        'schedule': timedelta(hours=6),
        'options': {'queue': 'ad_networks'}
    },
    'expire-offers-daily': {
        'task': 'ad_networks.expire_old_offers',
        'schedule': timedelta(hours=24),
        'options': {'queue': 'ad_networks'}
    },
    'sync-blacklist-daily': {
        'task': 'ad_networks.sync_blacklisted_ips',
        'schedule': timedelta(hours=12),
        'options': {'queue': 'ad_networks'}
    },
    'cleanup-logs-weekly': {
        'task': 'ad_networks.cleanup_old_webhook_logs',
        'schedule': timedelta(days=7),
        'options': {'queue': 'ad_networks'}
    },
}
