"""
api/ad_networks/context_processors.py
Context processors for ad networks module
SaaS-ready with tenant support
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any

from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model

from .models import (
    AdNetwork, Offer, OfferCategory, UserWallet,
    UserOfferEngagement, OfferConversion, OfferReward
)
from .choices import OfferStatus, NetworkStatus
from .constants import CACHE_TIMEOUTS

logger = logging.getLogger(__name__)
User = get_user_model()


def ad_networks_context(request):
    """
    Add ad networks context to all templates
    """
    context = {}
    
    try:
        # Get tenant ID
        tenant_id = getattr(request, 'tenant_id', 'default')
        context['tenant_id'] = tenant_id
        
        # Add featured offers
        context['featured_offers'] = get_featured_offers(tenant_id, limit=5)
        
        # Add hot offers
        context['hot_offers'] = get_hot_offers(tenant_id, limit=5)
        
        # Add new offers
        context['new_offers'] = get_new_offers(tenant_id, limit=5)
        
        # Add offer categories
        context['offer_categories'] = get_offer_categories(tenant_id)
        
        # Add active networks
        context['active_networks'] = get_active_networks(tenant_id, limit=10)
        
        # Add user-specific context if authenticated
        if request.user.is_authenticated:
            user_context = get_user_context(request.user, tenant_id)
            context.update(user_context)
        
        # Add statistics
        context['ad_networks_stats'] = get_general_stats(tenant_id)
        
        # Add configuration
        context['ad_networks_config'] = get_config()
        
    except Exception as e:
        logger.error(f"Error in ad_networks_context: {str(e)}")
    
    return context


def user_dashboard_context(request):
    """
    Add user dashboard context
    """
    context = {}
    
    if not request.user.is_authenticated:
        return context
    
    try:
        tenant_id = getattr(request, 'tenant_id', 'default')
        
        # User wallet
        context['user_wallet'] = get_user_wallet(request.user, tenant_id)
        
        # Recent activity
        context['recent_activity'] = get_user_recent_activity(request.user, tenant_id)
        
        # User stats
        context['user_stats'] = get_user_stats(request.user, tenant_id)
        
        # Recommended offers
        context['recommended_offers'] = get_recommended_offers(request.user, tenant_id)
        
        # Pending rewards
        context['pending_rewards'] = get_pending_rewards(request.user, tenant_id)
        
        # Daily progress
        context['daily_progress'] = get_daily_progress(request.user, tenant_id)
        
    except Exception as e:
        logger.error(f"Error in user_dashboard_context: {str(e)}")
    
    return context


def admin_dashboard_context(request):
    """
    Add admin dashboard context
    """
    context = {}
    
    if not request.user.is_staff:
        return context
    
    try:
        tenant_id = getattr(request, 'tenant_id', 'default')
        
        # Admin stats
        context['admin_stats'] = get_admin_stats(tenant_id)
        
        # Network health
        context['network_health'] = get_network_health_summary(tenant_id)
        
        # Recent conversions
        context['recent_conversions'] = get_recent_conversions(tenant_id)
        
        # Fraud alerts
        context['fraud_alerts'] = get_fraud_alerts(tenant_id)
        
        # System status
        context['system_status'] = get_system_status(tenant_id)
        
    except Exception as e:
        logger.error(f"Error in admin_dashboard_context: {str(e)}")
    
    return context


# Helper functions
def get_featured_offers(tenant_id: str, limit: int = 5):
    """Get featured offers"""
    try:
        return Offer.objects.filter(
            tenant_id=tenant_id,
            status=OfferStatus.ACTIVE,
            is_featured=True
        ).select_related('ad_network', 'category')[:limit]
    except Exception as e:
        logger.error(f"Error getting featured offers: {str(e)}")
        return []


def get_hot_offers(tenant_id: str, limit: int = 5):
    """Get hot offers"""
    try:
        return Offer.objects.filter(
            tenant_id=tenant_id,
            status=OfferStatus.ACTIVE,
            is_hot=True
        ).select_related('ad_network', 'category')[:limit]
    except Exception as e:
        logger.error(f"Error getting hot offers: {str(e)}")
        return []


def get_new_offers(tenant_id: str, limit: int = 5):
    """Get new offers"""
    try:
        cutoff_date = timezone.now() - timedelta(days=7)
        return Offer.objects.filter(
            tenant_id=tenant_id,
            status=OfferStatus.ACTIVE,
            is_new=True,
            created_at__gte=cutoff_date
        ).select_related('ad_network', 'category')[:limit]
    except Exception as e:
        logger.error(f"Error getting new offers: {str(e)}")
        return []


def get_offer_categories(tenant_id: str):
    """Get offer categories with counts"""
    try:
        from django.db.models import Count
        
        categories = OfferCategory.objects.filter(
            is_active=True
        ).annotate(
            offer_count=Count(
                'offer',
                filter=Q(
                    offer__tenant_id=tenant_id,
                    offer__status=OfferStatus.ACTIVE
                )
            )
        ).filter(offer_count__gt=0)
        
        return categories
    except Exception as e:
        logger.error(f"Error getting offer categories: {str(e)}")
        return []


def get_active_networks(tenant_id: str, limit: int = 10):
    """Get active networks"""
    try:
        return AdNetwork.objects.filter(
            tenant_id=tenant_id,
            is_active=True,
            status=NetworkStatus.ACTIVE
        )[:limit]
    except Exception as e:
        logger.error(f"Error getting active networks: {str(e)}")
        return []


def get_user_context(user: User, tenant_id: str) -> Dict[str, Any]:
    """Get user-specific context"""
    context = {}
    
    try:
        # User wallet
        context['user_wallet'] = get_user_wallet(user, tenant_id)
        
        # Engagement count
        context['engagement_count'] = UserOfferEngagement.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).count()
        
        # Conversion count
        context['conversion_count'] = OfferConversion.objects.filter(
            engagement__user=user,
            tenant_id=tenant_id
        ).count()
        
        # Reward count
        context['reward_count'] = OfferReward.objects.filter(
            user=user,
            tenant_id=tenant_id
        ).count()
        
    except Exception as e:
        logger.error(f"Error getting user context: {str(e)}")
    
    return context


def get_user_wallet(user: User, tenant_id: str):
    """Get user wallet"""
    try:
        wallet, created = UserWallet.objects.get_or_create(
            user=user,
            defaults={
                'balance': Decimal('0.00'),
                'total_earned': Decimal('0.00'),
                'currency': 'USD',
                'tenant_id': tenant_id
            }
        )
        return wallet
    except Exception as e:
        logger.error(f"Error getting user wallet: {str(e)}")
        return None


def get_user_recent_activity(user: User, tenant_id: str, limit: int = 5):
    """Get user's recent activity"""
    try:
        # Get recent conversions
        conversions = OfferConversion.objects.filter(
            engagement__user=user,
            tenant_id=tenant_id
        ).select_related('engagement__offer').order_by('-created_at')[:limit]
        
        activity = []
        for conversion in conversions:
            activity.append({
                'type': 'conversion',
                'title': f"Completed {conversion.engagement.offer.title}",
                'amount': float(conversion.payout),
                'status': conversion.conversion_status,
                'timestamp': conversion.created_at
            })
        
        return activity
    except Exception as e:
        logger.error(f"Error getting user recent activity: {str(e)}")
        return []


def get_user_stats(user: User, tenant_id: str) -> Dict[str, Any]:
    """Get user statistics"""
    try:
        from django.db.models import Sum, Count
        
        # Last 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # Engagement stats
        total_engagements = UserOfferEngagement.objects.filter(
            user=user,
            tenant_id=tenant_id,
            created_at__gte=cutoff_date
        ).count()
        
        # Conversion stats
        conversions = OfferConversion.objects.filter(
            engagement__user=user,
            tenant_id=tenant_id,
            created_at__gte=cutoff_date
        )
        
        total_conversions = conversions.count()
        approved_conversions = conversions.filter(
            conversion_status='approved'
        ).count()
        
        # Reward stats
        total_earned = OfferReward.objects.filter(
            user=user,
            tenant_id=tenant_id,
            status='approved',
            created_at__gte=cutoff_date
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        return {
            'total_engagements': total_engagements,
            'total_conversions': total_conversions,
            'approved_conversions': approved_conversions,
            'total_earned': float(total_earned)
        }
        
    except Exception as e:
        logger.error(f"Error getting user stats: {str(e)}")
        return {}


def get_recommended_offers(user: User, tenant_id: str, limit: int = 5):
    """Get recommended offers for user"""
    try:
        # This would integrate with recommendation service
        # For now, just get random active offers
        return Offer.objects.filter(
            tenant_id=tenant_id,
            status=OfferStatus.ACTIVE
        ).select_related('ad_network', 'category').order_by('?')[:limit]
    except Exception as e:
        logger.error(f"Error getting recommended offers: {str(e)}")
        return []


def get_pending_rewards(user: User, tenant_id: str):
    """Get user's pending rewards"""
    try:
        return OfferReward.objects.filter(
            user=user,
            tenant_id=tenant_id,
            status='pending'
        ).select_related('offer').order_by('-created_at')
    except Exception as e:
        logger.error(f"Error getting pending rewards: {str(e)}")
        return []


def get_daily_progress(user: User, tenant_id: str) -> Dict[str, Any]:
    """Get user's daily progress"""
    try:
        from django.db.models import Count
        
        today = timezone.now().date()
        
        # Today's engagements
        today_engagements = UserOfferEngagement.objects.filter(
            user=user,
            tenant_id=tenant_id,
            created_at__date=today
        ).count()
        
        # Today's conversions
        today_conversions = OfferConversion.objects.filter(
            engagement__user=user,
            tenant_id=tenant_id,
            created_at__date=today
        ).count()
        
        # Today's earnings
        today_earnings = OfferReward.objects.filter(
            user=user,
            tenant_id=tenant_id,
            status='approved',
            created_at__date=today
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        return {
            'engagements': today_engagements,
            'conversions': today_conversions,
            'earnings': float(today_earnings)
        }
        
    except Exception as e:
        logger.error(f"Error getting daily progress: {str(e)}")
        return {}


def get_general_stats(tenant_id: str) -> Dict[str, Any]:
    """Get general statistics"""
    try:
        from django.db.models import Count, Sum
        
        # Total offers
        total_offers = Offer.objects.filter(
            tenant_id=tenant_id,
            status=OfferStatus.ACTIVE
        ).count()
        
        # Total networks
        total_networks = AdNetwork.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).count()
        
        # Last 30 days conversions
        cutoff_date = timezone.now() - timedelta(days=30)
        total_conversions = OfferConversion.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=cutoff_date
        ).count()
        
        return {
            'total_offers': total_offers,
            'total_networks': total_networks,
            'total_conversions': total_conversions
        }
        
    except Exception as e:
        logger.error(f"Error getting general stats: {str(e)}")
        return {}


def get_config() -> Dict[str, Any]:
    """Get ad networks configuration"""
    try:
        return {
            'currency': getattr(settings, 'AD_NETWORKS_CURRENCY', 'USD'),
            'currency_symbol': getattr(settings, 'AD_NETWORKS_CURRENCY_SYMBOL', '$'),
            'min_payout': getattr(settings, 'AD_NETWORKS_MIN_PAYOUT', Decimal('1.00')),
            'max_daily_offers': getattr(settings, 'AD_NETWORKS_MAX_DAILY_OFFERS', 50),
            'enable_fraud_detection': getattr(settings, 'AD_NETWORKS_ENABLE_FRAUD_DETECTION', True),
            'enable_analytics': getattr(settings, 'AD_NETWORKS_ENABLE_ANALYTICS', True),
            'cache_timeout': getattr(settings, 'AD_NETWORKS_CACHE_TIMEOUT', 300),
        }
    except Exception as e:
        logger.error(f"Error getting config: {str(e)}")
        return {}


def get_admin_stats(tenant_id: str) -> Dict[str, Any]:
    """Get admin statistics"""
    try:
        from django.db.models import Count, Sum, Q
        
        # Last 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        
        # User stats
        total_users = User.objects.filter(
            userofferengagement__tenant_id=tenant_id
        ).distinct().count()
        
        active_users = User.objects.filter(
            userofferengagement__tenant_id=tenant_id,
            userofferengagement__created_at__gte=cutoff_date
        ).distinct().count()
        
        # Conversion stats
        total_conversions = OfferConversion.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=cutoff_date
        ).count()
        
        pending_conversions = OfferConversion.objects.filter(
            tenant_id=tenant_id,
            conversion_status='pending'
        ).count()
        
        # Revenue stats
        total_revenue = OfferConversion.objects.filter(
            tenant_id=tenant_id,
            conversion_status='approved',
            created_at__gte=cutoff_date
        ).aggregate(
            total=Sum('payout')
        )['total'] or Decimal('0.00')
        
        # Fraud stats
        fraud_conversions = OfferConversion.objects.filter(
            tenant_id=tenant_id,
            fraud_score__gte=70,
            created_at__gte=cutoff_date
        ).count()
        
        return {
            'users': {
                'total': total_users,
                'active': active_users
            },
            'conversions': {
                'total': total_conversions,
                'pending': pending_conversions,
                'fraudulent': fraud_conversions
            },
            'revenue': {
                'total': float(total_revenue)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting admin stats: {str(e)}")
        return {}


def get_network_health_summary(tenant_id: str) -> Dict[str, Any]:
    """Get network health summary"""
    try:
        from django.db.models import Count
        
        networks = AdNetwork.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        )
        
        total_networks = networks.count()
        healthy_networks = 0
        unhealthy_networks = 0
        
        for network in networks:
            # Check if network has recent successful health check
            from .models import NetworkHealthCheck
            
            latest_check = NetworkHealthCheck.objects.filter(
                network=network,
                tenant_id=tenant_id
            ).order_by('-checked_at').first()
            
            if latest_check and latest_check.is_healthy:
                healthy_networks += 1
            else:
                unhealthy_networks += 1
        
        return {
            'total_networks': total_networks,
            'healthy_networks': healthy_networks,
            'unhealthy_networks': unhealthy_networks,
            'health_percentage': (healthy_networks / total_networks * 100) if total_networks > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting network health summary: {str(e)}")
        return {}


def get_recent_conversions(tenant_id: str, limit: int = 10):
    """Get recent conversions"""
    try:
        return OfferConversion.objects.filter(
            tenant_id=tenant_id
        ).select_related(
            'engagement__user', 'engagement__offer', 'engagement__offer__ad_network'
        ).order_by('-created_at')[:limit]
    except Exception as e:
        logger.error(f"Error getting recent conversions: {str(e)}")
        return []


def get_fraud_alerts(tenant_id: str, limit: int = 5):
    """Get fraud alerts"""
    try:
        return OfferConversion.objects.filter(
            tenant_id=tenant_id,
            fraud_score__gte=70,
            conversion_status='pending'
        ).select_related(
            'engagement__user', 'engagement__offer'
        ).order_by('-fraud_score')[:limit]
    except Exception as e:
        logger.error(f"Error getting fraud alerts: {str(e)}")
        return []


def get_system_status(tenant_id: str) -> Dict[str, Any]:
    """Get system status"""
    try:
        from django.core.cache import cache
        
        # Check cache status
        cache_status = 'healthy'
        try:
            cache.set('health_check', 'ok', 60)
            cache.get('health_check')
        except:
            cache_status = 'unhealthy'
        
        # Check database status
        db_status = 'healthy'
        try:
            User.objects.count()
        except:
            db_status = 'unhealthy'
        
        # Get last sync time
        last_sync_time = cache.get(f'last_sync_{tenant_id}')
        
        return {
            'cache_status': cache_status,
            'database_status': db_status,
            'last_sync': last_sync_time,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting system status: {str(e)}")
        return {}


# Export all context processors
__all__ = [
    'ad_networks_context',
    'user_dashboard_context',
    'admin_dashboard_context'
]
