"""
api/ad_networks/selectors.py
Selectors for ad networks module - Clean Architecture Pattern
SaaS-ready with tenant support
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
from django.db.models import Q, Count, Sum, Avg, F, ExpressionWrapper, FloatField, Prefetch
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache

from .models import (
    AdNetwork, Offer, OfferCategory, UserOfferEngagement,
    OfferConversion, OfferReward, UserWallet, OfferClick,
    OfferTag, OfferTagging, NetworkHealthCheck, OfferDailyLimit
)
from .choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus, DeviceType, Difficulty
)
from .constants import FRAUD_SCORE_THRESHOLD, CACHE_TIMEOUTS
from .helpers import get_cache_key

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== BASE SELECTOR ====================

class BaseSelector:
    """Base selector with common functionality"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.cache_timeout = CACHE_TIMEOUTS.get('default', 300)
    
    def _get_cache_key(self, *args, **kwargs) -> str:
        """Generate cache key"""
        return get_cache_key(self.__class__.__name__, self.tenant_id, *args, **kwargs)
    
    def _get_from_cache(self, key: str) -> Any:
        """Get data from cache"""
        return cache.get(key)
    
    def _set_cache(self, key: str, data: Any, timeout: int = None) -> None:
        """Set data in cache"""
        timeout = timeout or self.cache_timeout
        cache.set(key, data, timeout)
    
    def _invalidate_cache(self, pattern: str = None) -> None:
        """Invalidate cache"""
        if pattern:
            # This would use cache.delete_pattern in production
            pass
        else:
            # Clear all cache for this selector
            pass


# ==================== OFFER SELECTORS ====================

class OfferSelector(BaseSelector):
    """Selector for Offer operations"""
    
    def get_by_id(self, offer_id: int) -> Optional[Offer]:
        """Get offer by ID"""
        cache_key = self._get_cache_key('offer', offer_id)
        offer = self._get_from_cache(cache_key)
        
        if offer is None:
            try:
                offer = Offer.objects.get(id=offer_id, tenant_id=self.tenant_id)
                self._set_cache(cache_key, offer)
            except Offer.DoesNotExist:
                return None
        
        return offer
    
    def get_active_offers(self, category_id: int = None, platform: str = None,
                          device_type: str = None, limit: int = None) -> List[Offer]:
        """Get active offers with optional filters"""
        cache_key = self._get_cache_key('active_offers', category_id, platform, device_type, limit)
        offers = self._get_from_cache(cache_key)
        
        if offers is None:
            queryset = Offer.objects.filter(
                tenant_id=self.tenant_id,
                status=OfferStatus.ACTIVE
            )
            
            if category_id:
                queryset = queryset.filter(category_id=category_id)
            
            if platform:
                queryset = queryset.filter(platforms__contains=[platform])
            
            if device_type:
                queryset = queryset.filter(device_type=device_type)
            
            if limit:
                queryset = queryset[:limit]
            
            offers = list(queryset.select_related('category').prefetch_related('tags'))
            self._set_cache(cache_key, offers)
        
        return offers
    
    def get_featured_offers(self, limit: int = 10) -> List[Offer]:
        """Get featured offers"""
        cache_key = self._get_cache_key('featured_offers', limit)
        offers = self._get_from_cache(cache_key)
        
        if offers is None:
            offers = list(
                Offer.objects.filter(
                    tenant_id=self.tenant_id,
                    status=OfferStatus.ACTIVE,
                    is_featured=True
                ).select_related('category')[:limit]
            )
            self._set_cache(cache_key, offers)
        
        return offers
    
    def get_hot_offers(self, limit: int = 10) -> List[Offer]:
        """Get hot offers (high conversion rate)"""
        cache_key = self._get_cache_key('hot_offers', limit)
        offers = self._get_from_cache(cache_key)
        
        if offers is None:
            offers = list(
                Offer.objects.filter(
                    tenant_id=self.tenant_id,
                    status=OfferStatus.ACTIVE,
                    is_hot=True
                ).select_related('category')[:limit]
            )
            self._set_cache(cache_key, offers)
        
        return offers
    
    def get_new_offers(self, days: int = 7, limit: int = 10) -> List[Offer]:
        """Get new offers"""
        cache_key = self._get_cache_key('new_offers', days, limit)
        offers = self._get_from_cache(cache_key)
        
        if offers is None:
            start_date = timezone.now() - timedelta(days=days)
            offers = list(
                Offer.objects.filter(
                    tenant_id=self.tenant_id,
                    status=OfferStatus.ACTIVE,
                    is_new=True,
                    created_at__gte=start_date
                ).select_related('category')[:limit]
            )
            self._set_cache(cache_key, offers)
        
        return offers
    
    def get_offers_by_network(self, network_id: int, status: str = OfferStatus.ACTIVE) -> List[Offer]:
        """Get offers by network"""
        cache_key = self._get_cache_key('offers_by_network', network_id, status)
        offers = self._get_from_cache(cache_key)
        
        if offers is None:
            offers = list(
                Offer.objects.filter(
                    tenant_id=self.tenant_id,
                    ad_network_id=network_id,
                    status=status
                ).select_related('category', 'ad_network')
            )
            self._set_cache(cache_key, offers)
        
        return offers
    
    def search_offers(self, query: str, category_id: int = None, limit: int = 20) -> List[Offer]:
        """Search offers by text"""
        cache_key = self._get_cache_key('search_offers', query, category_id, limit)
        offers = self._get_from_cache(cache_key)
        
        if offers is None:
            queryset = Offer.objects.filter(
                tenant_id=self.tenant_id,
                status=OfferStatus.ACTIVE
            )
            
            if query:
                queryset = queryset.filter(
                    Q(title__icontains=query) |
                    Q(description__icontains=query)
                )
            
            if category_id:
                queryset = queryset.filter(category_id=category_id)
            
            offers = list(queryset.select_related('category')[:limit])
            self._set_cache(cache_key, offers)
        
        return offers
    
    def get_user_available_offers(self, user_id: int, limit: int = 20) -> List[Offer]:
        """Get offers available to user (excluding completed)"""
        cache_key = self._get_cache_key('user_available_offers', user_id, limit)
        offers = self._get_from_cache(cache_key)
        
        if offers is None:
            # Get offers user hasn't completed
            completed_offer_ids = UserOfferEngagement.objects.filter(
                tenant_id=self.tenant_id,
                user_id=user_id,
                status=EngagementStatus.COMPLETED
            ).values_list('offer_id', flat=True)
            
            offers = list(
                Offer.objects.filter(
                    tenant_id=self.tenant_id,
                    status=OfferStatus.ACTIVE
                ).exclude(
                    id__in=completed_offer_ids
                ).select_related('category')[:limit]
            )
            self._set_cache(cache_key, offers)
        
        return offers


# ==================== USER ENGAGEMENT SELECTORS ====================

class UserEngagementSelector(BaseSelector):
    """Selector for UserOfferEngagement operations"""
    
    def get_user_engagements(self, user_id: int, status: str = None, 
                             limit: int = None) -> List[UserOfferEngagement]:
        """Get user's engagements"""
        cache_key = self._get_cache_key('user_engagements', user_id, status, limit)
        engagements = self._get_from_cache(cache_key)
        
        if engagements is None:
            queryset = UserOfferEngagement.objects.filter(
                tenant_id=self.tenant_id,
                user_id=user_id
            )
            
            if status:
                queryset = queryset.filter(status=status)
            
            if limit:
                queryset = queryset[:limit]
            
            engagements = list(queryset.select_related('offer', 'offer__category'))
            self._set_cache(cache_key, engagements)
        
        return engagements
    
    def get_user_completed_engagements(self, user_id: int, days: int = 30) -> List[UserOfferEngagement]:
        """Get user's completed engagements"""
        cache_key = self._get_cache_key('user_completed_engagements', user_id, days)
        engagements = self._get_from_cache(cache_key)
        
        if engagements is None:
            start_date = timezone.now() - timedelta(days=days)
            engagements = list(
                UserOfferEngagement.objects.filter(
                    tenant_id=self.tenant_id,
                    user_id=user_id,
                    status=EngagementStatus.COMPLETED,
                    completed_at__gte=start_date
                ).select_related('offer', 'offer__category')
            )
            self._set_cache(cache_key, engagements)
        
        return engagements
    
    def get_engagement_by_offer(self, user_id: int, offer_id: int) -> Optional[UserOfferEngagement]:
        """Get user's engagement for specific offer"""
        cache_key = self._get_cache_key('engagement_by_offer', user_id, offer_id)
        engagement = self._get_from_cache(cache_key)
        
        if engagement is None:
            try:
                engagement = UserOfferEngagement.objects.get(
                    tenant_id=self.tenant_id,
                    user_id=user_id,
                    offer_id=offer_id
                )
                self._set_cache(cache_key, engagement)
            except UserOfferEngagement.DoesNotExist:
                return None
        
        return engagement
    
    def get_pending_engagements(self, user_id: int) -> List[UserOfferEngagement]:
        """Get user's pending engagements"""
        cache_key = self._get_cache_key('pending_engagements', user_id)
        engagements = self._get_from_cache(cache_key)
        
        if engagements is None:
            engagements = list(
                UserOfferEngagement.objects.filter(
                    tenant_id=self.tenant_id,
                    user_id=user_id,
                    status=EngagementStatus.IN_PROGRESS
                ).select_related('offer', 'offer__category')
            )
            self._set_cache(cache_key, engagements)
        
        return engagements


# ==================== CONVERSION SELECTORS ====================

class ConversionSelector(BaseSelector):
    """Selector for OfferConversion operations"""
    
    def get_user_conversions(self, user_id: int, status: str = None,
                           days: int = None) -> List[OfferConversion]:
        """Get user's conversions"""
        cache_key = self._get_cache_key('user_conversions', user_id, status, days)
        conversions = self._get_from_cache(cache_key)
        
        if conversions is None:
            queryset = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                engagement__user_id=user_id
            )
            
            if status:
                queryset = queryset.filter(status=status)
            
            if days:
                start_date = timezone.now() - timedelta(days=days)
                queryset = queryset.filter(created_at__gte=start_date)
            
            conversions = list(
                queryset.select_related('engagement', 'engagement__offer')
                .order_by('-created_at')
            )
            self._set_cache(cache_key, conversions)
        
        return conversions
    
    def get_pending_conversions(self, limit: int = 100) -> List[OfferConversion]:
        """Get pending conversions"""
        cache_key = self._get_cache_key('pending_conversions', limit)
        conversions = self._get_from_cache(cache_key)
        
        if conversions is None:
            conversions = list(
                OfferConversion.objects.filter(
                    tenant_id=self.tenant_id,
                    status=ConversionStatus.PENDING
                ).select_related('engagement', 'engagement__offer', 'engagement__user')[:limit]
            )
            self._set_cache(cache_key, conversions)
        
        return conversions
    
    def get_fraudulent_conversions(self, days: int = 7) -> List[OfferConversion]:
        """Get potentially fraudulent conversions"""
        cache_key = self._get_cache_key('fraudulent_conversions', days)
        conversions = self._get_from_cache(cache_key)
        
        if conversions is None:
            start_date = timezone.now() - timedelta(days=days)
            conversions = list(
                OfferConversion.objects.filter(
                    tenant_id=self.tenant_id,
                    fraud_score__gte=FRAUD_SCORE_THRESHOLD,
                    created_at__gte=start_date
                ).select_related('engagement', 'engagement__offer', 'engagement__user')
            )
            self._set_cache(cache_key, conversions)
        
        return conversions
    
    def get_conversion_statistics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get conversion statistics for date range"""
        cache_key = self._get_cache_key('conversion_stats', start_date, end_date)
        stats = self._get_from_cache(cache_key)
        
        if stats is None:
            conversions = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                created_at__range=[start_date, end_date]
            )
            
            stats = {
                'total_conversions': conversions.count(),
                'pending_conversions': conversions.filter(status=ConversionStatus.PENDING).count(),
                'approved_conversions': conversions.filter(status=ConversionStatus.APPROVED).count(),
                'rejected_conversions': conversions.filter(status=ConversionStatus.REJECTED).count(),
                'total_payout': conversions.filter(status=ConversionStatus.APPROVED).aggregate(
                    total=Sum('payout')
                )['total'] or 0,
                'avg_payout': conversions.filter(status=ConversionStatus.APPROVED).aggregate(
                    avg=Avg('payout')
                )['avg'] or 0,
            }
            
            self._set_cache(cache_key, stats, timeout=600)  # Cache for 10 minutes
        
        return stats


# ==================== REWARD SELECTORS ====================

class RewardSelector(BaseSelector):
    """Selector for OfferReward operations"""
    
    def get_user_rewards(self, user_id: int, status: str = None,
                       days: int = None) -> List[OfferReward]:
        """Get user's rewards"""
        cache_key = self._get_cache_key('user_rewards', user_id, status, days)
        rewards = self._get_from_cache(cache_key)
        
        if rewards is None:
            queryset = OfferReward.objects.filter(
                tenant_id=self.tenant_id,
                user_id=user_id
            )
            
            if status:
                queryset = queryset.filter(status=status)
            
            if days:
                start_date = timezone.now() - timedelta(days=days)
                queryset = queryset.filter(created_at__gte=start_date)
            
            rewards = list(
                queryset.select_related('offer', 'offer__category')
                .order_by('-created_at')
            )
            self._set_cache(cache_key, rewards)
        
        return rewards
    
    def get_pending_rewards(self, limit: int = 100) -> List[OfferReward]:
        """Get pending rewards"""
        cache_key = self._get_cache_key('pending_rewards', limit)
        rewards = self._get_from_cache(cache_key)
        
        if rewards is None:
            rewards = list(
                OfferReward.objects.filter(
                    tenant_id=self.tenant_id,
                    status=RewardStatus.PENDING
                ).select_related('user', 'offer')[:limit]
            )
            self._set_cache(cache_key, rewards)
        
        return rewards
    
    def get_user_earnings(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get user's earnings summary"""
        cache_key = self._get_cache_key('user_earnings', user_id, days)
        earnings = self._get_from_cache(cache_key)
        
        if earnings is None:
            start_date = timezone.now() - timedelta(days=days)
            rewards = OfferReward.objects.filter(
                tenant_id=self.tenant_id,
                user_id=user_id,
                created_at__gte=start_date
            )
            
            earnings = {
                'total_earned': rewards.filter(status=RewardStatus.APPROVED).aggregate(
                    total=Sum('amount')
                )['total'] or 0,
                'pending_amount': rewards.filter(status=RewardStatus.PENDING).aggregate(
                    total=Sum('amount')
                )['total'] or 0,
                'paid_amount': rewards.filter(status=RewardStatus.PAID).aggregate(
                    total=Sum('amount')
                )['total'] or 0,
                'total_rewards': rewards.count(),
                'approved_rewards': rewards.filter(status=RewardStatus.APPROVED).count(),
                'pending_rewards': rewards.filter(status=RewardStatus.PENDING).count(),
                'paid_rewards': rewards.filter(status=RewardStatus.PAID).count(),
            }
            
            self._set_cache(cache_key, earnings, timeout=600)
        
        return earnings


# ==================== WALLET SELECTORS ====================

class WalletSelector(BaseSelector):
    """Selector for UserWallet operations"""
    
    def get_user_wallet(self, user_id: int) -> Optional[UserWallet]:
        """Get user's wallet"""
        cache_key = self._get_cache_key('user_wallet', user_id)
        wallet = self._get_from_cache(cache_key)
        
        if wallet is None:
            try:
                wallet = UserWallet.objects.get(
                    tenant_id=self.tenant_id,
                    user_id=user_id
                )
                self._set_cache(cache_key, wallet)
            except UserWallet.DoesNotExist:
                return None
        
        return wallet
    
    def get_or_create_user_wallet(self, user_id: int) -> UserWallet:
        """Get or create user's wallet"""
        wallet = self.get_user_wallet(user_id)
        
        if wallet is None:
            wallet = UserWallet.objects.create(
                tenant_id=self.tenant_id,
                user_id=user_id
            )
            
            # Cache the new wallet
            cache_key = self._get_cache_key('user_wallet', user_id)
            self._set_cache(cache_key, wallet)
        
        return wallet
    
    def get_wallet_balance(self, user_id: int) -> Dict[str, Any]:
        """Get user's wallet balance breakdown"""
        cache_key = self._get_cache_key('wallet_balance', user_id)
        balance = self._get_from_cache(cache_key)
        
        if balance is None:
            wallet = self.get_or_create_user_wallet(user_id)
            
            balance = {
                'current_balance': float(wallet.current_balance),
                'available_balance': float(wallet.available_balance),
                'pending_balance': float(wallet.pending_balance),
                'total_earned': float(wallet.total_earned),
                'total_withdrawn': float(wallet.total_withdrawn),
                'currency': wallet.currency,
                'is_active': wallet.is_active,
                'is_frozen': wallet.is_frozen,
                'freeze_reason': wallet.freeze_reason,
            }
            
            self._set_cache(cache_key, balance, timeout=300)
        
        return balance


# ==================== NETWORK SELECTORS ====================

class NetworkSelector(BaseSelector):
    """Selector for AdNetwork operations"""
    
    def get_active_networks(self) -> List[AdNetwork]:
        """Get active networks"""
        cache_key = self._get_cache_key('active_networks')
        networks = self._get_from_cache(cache_key)
        
        if networks is None:
            networks = list(
                AdNetwork.objects.filter(
                    tenant_id=self.tenant_id,
                    is_active=True,
                    status=NetworkStatus.ACTIVE
                )
            )
            self._set_cache(cache_key, networks)
        
        return networks
    
    def get_network_by_type(self, network_type: str) -> Optional[AdNetwork]:
        """Get network by type"""
        cache_key = self._get_cache_key('network_by_type', network_type)
        network = self._get_from_cache(cache_key)
        
        if network is None:
            try:
                network = AdNetwork.objects.get(
                    tenant_id=self.tenant_id,
                    network_type=network_type
                )
                self._set_cache(cache_key, network)
            except AdNetwork.DoesNotExist:
                return None
        
        return network
    
    def get_network_statistics(self, network_id: int) -> Dict[str, Any]:
        """Get network statistics"""
        cache_key = self._get_cache_key('network_stats', network_id)
        stats = self._get_from_cache(cache_key)
        
        if stats is None:
            try:
                network = AdNetwork.objects.get(id=network_id, tenant_id=self.tenant_id)
                
                stats = {
                    'total_offers': Offer.objects.filter(
                        tenant_id=self.tenant_id,
                        ad_network=network
                    ).count(),
                    'active_offers': Offer.objects.filter(
                        tenant_id=self.tenant_id,
                        ad_network=network,
                        status=OfferStatus.ACTIVE
                    ).count(),
                    'total_conversions': OfferConversion.objects.filter(
                        tenant_id=self.tenant_id,
                        engagement__offer__ad_network=network
                    ).count(),
                    'success_rate': network.success_rate,
                    'avg_payout': float(network.avg_payout) if network.avg_payout else 0,
                    'last_sync': network.last_sync.isoformat() if network.last_sync else None,
                    'is_healthy': network.is_healthy,
                }
                
                self._set_cache(cache_key, stats, timeout=600)
                
            except AdNetwork.DoesNotExist:
                return {}
        
        return stats


# ==================== CATEGORY SELECTORS ====================

class CategorySelector(BaseSelector):
    """Selector for OfferCategory operations"""
    
    def get_all_categories(self) -> List[OfferCategory]:
        """Get all categories"""
        cache_key = self._get_cache_key('all_categories')
        categories = self._get_from_cache(cache_key)
        
        if categories is None:
            categories = list(
                OfferCategory.objects.annotate(
                    offer_count=Count('offer', filter=Q(offer__status=OfferStatus.ACTIVE))
                ).filter(offer_count__gt=0)
            )
            self._set_cache(cache_key, categories)
        
        return categories
    
    def get_category_by_slug(self, slug: str) -> Optional[OfferCategory]:
        """Get category by slug"""
        cache_key = self._get_cache_key('category_by_slug', slug)
        category = self._get_from_cache(cache_key)
        
        if category is None:
            try:
                category = OfferCategory.objects.get(slug=slug)
                self._set_cache(cache_key, category)
            except OfferCategory.DoesNotExist:
                return None
        
        return category
    
    def get_popular_categories(self, limit: int = 10) -> List[OfferCategory]:
        """Get popular categories (with most offers)"""
        cache_key = self._get_cache_key('popular_categories', limit)
        categories = self._get_from_cache(cache_key)
        
        if categories is None:
            categories = list(
                OfferCategory.objects.annotate(
                    offer_count=Count('offer', filter=Q(offer__status=OfferStatus.ACTIVE))
                ).filter(offer_count__gt=0).order_by('-offer_count')[:limit]
            )
            self._set_cache(cache_key, categories)
        
        return categories


# ==================== TAG SELECTORS ====================

class TagSelector(BaseSelector):
    """Selector for OfferTag operations"""
    
    def get_all_tags(self) -> List[OfferTag]:
        """Get all active tags"""
        cache_key = self._get_cache_key('all_tags')
        tags = self._get_from_cache(cache_key)
        
        if tags is None:
            tags = list(
                OfferTag.objects.filter(
                    is_active=True
                ).annotate(
                    usage_count=Count('offertagging')
                ).order_by('-usage_count')
            )
            self._set_cache(cache_key, tags)
        
        return tags
    
    def get_popular_tags(self, limit: int = 20) -> List[OfferTag]:
        """Get popular tags"""
        cache_key = self._get_cache_key('popular_tags', limit)
        tags = self._get_from_cache(cache_key)
        
        if tags is None:
            tags = list(
                OfferTag.objects.filter(
                    is_active=True
                ).annotate(
                    usage_count=Count('offertagging')
                ).order_by('-usage_count')[:limit]
            )
            self._set_cache(cache_key, tags)
        
        return tags
    
    def get_tags_by_offer(self, offer_id: int) -> List[OfferTag]:
        """Get tags for specific offer"""
        cache_key = self._get_cache_key('offer_tags', offer_id)
        tags = self._get_from_cache(cache_key)
        
        if tags is None:
            tags = list(
                OfferTag.objects.filter(
                    offertagging__offer_id=offer_id,
                    is_active=True
                )
            )
            self._set_cache(cache_key, tags)
        
        return tags


# ==================== HEALTH CHECK SELECTORS ====================

class HealthCheckSelector(BaseSelector):
    """Selector for NetworkHealthCheck operations"""
    
    def get_recent_health_checks(self, network_id: int, hours: int = 24) -> List[NetworkHealthCheck]:
        """Get recent health checks for network"""
        cache_key = self._get_cache_key('recent_health_checks', network_id, hours)
        checks = self._get_from_cache(cache_key)
        
        if checks is None:
            start_time = timezone.now() - timedelta(hours=hours)
            checks = list(
                NetworkHealthCheck.objects.filter(
                    tenant_id=self.tenant_id,
                    network_id=network_id,
                    checked_at__gte=start_time
                ).order_by('-checked_at')
            )
            self._set_cache(cache_key, checks)
        
        return checks
    
    def get_network_health_status(self, network_id: int) -> Dict[str, Any]:
        """Get network health status"""
        cache_key = self._get_cache_key('network_health_status', network_id)
        status = self._get_from_cache(cache_key)
        
        if status is None:
            latest_check = NetworkHealthCheck.objects.filter(
                tenant_id=self.tenant_id,
                network_id=network_id
            ).order_by('-checked_at').first()
            
            if latest_check:
                status = {
                    'is_healthy': latest_check.is_healthy,
                    'response_time_ms': latest_check.response_time_ms,
                    'status_code': latest_check.status_code,
                    'error': latest_check.error,
                    'checked_at': latest_check.checked_at.isoformat(),
                    'is_recent': latest_check.is_recent,
                }
            else:
                status = {
                    'is_healthy': None,
                    'response_time_ms': None,
                    'status_code': None,
                    'error': 'No health checks performed',
                    'checked_at': None,
                    'is_recent': False,
                }
            
            self._set_cache(cache_key, status, timeout=300)
        
        return status


# ==================== SELECTOR FACTORY ====================

class SelectorFactory:
    """Factory for creating selectors"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
    
    def offer(self) -> OfferSelector:
        """Create offer selector"""
        return OfferSelector(self.tenant_id)
    
    def user_engagement(self) -> UserEngagementSelector:
        """Create user engagement selector"""
        return UserEngagementSelector(self.tenant_id)
    
    def conversion(self) -> ConversionSelector:
        """Create conversion selector"""
        return ConversionSelector(self.tenant_id)
    
    def reward(self) -> RewardSelector:
        """Create reward selector"""
        return RewardSelector(self.tenant_id)
    
    def wallet(self) -> WalletSelector:
        """Create wallet selector"""
        return WalletSelector(self.tenant_id)
    
    def network(self) -> NetworkSelector:
        """Create network selector"""
        return NetworkSelector(self.tenant_id)
    
    def category(self) -> CategorySelector:
        """Create category selector"""
        return CategorySelector(self.tenant_id)
    
    def tag(self) -> TagSelector:
        """Create tag selector"""
        return TagSelector(self.tenant_id)
    
    def health_check(self) -> HealthCheckSelector:
        """Create health check selector"""
        return HealthCheckSelector(self.tenant_id)


# ==================== EXPORTS ====================

__all__ = [
    # Base selector
    'BaseSelector',
    
    # Selectors
    'OfferSelector',
    'UserEngagementSelector',
    'ConversionSelector',
    'RewardSelector',
    'WalletSelector',
    'NetworkSelector',
    'CategorySelector',
    'TagSelector',
    'HealthCheckSelector',
    
    # Factory
    'SelectorFactory',
]
