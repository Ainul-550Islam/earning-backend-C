"""
api/ad_networks/repositories.py
Repositories for ad networks module - Clean Architecture Pattern
SaaS-ready with tenant support
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
from django.db.models import Q, Count, Sum, Avg, F, ExpressionWrapper, FloatField, Prefetch
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
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


# ==================== BASE REPOSITORY ====================

class BaseRepository:
    """Base repository with common functionality"""
    
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
            # Clear all cache for this repository
            pass


# ==================== OFFER REPOSITORY ====================

class OfferRepository(BaseRepository):
    """Repository for Offer model operations"""
    
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
    
    def create(self, data: Dict[str, Any]) -> Offer:
        """Create new offer"""
        with transaction.atomic():
            # Set tenant_id
            data['tenant_id'] = self.tenant_id
            
            offer = Offer.objects.create(**data)
            
            # Invalidate cache
            self._invalidate_cache()
            
            return offer
    
    def update(self, offer_id: int, data: Dict[str, Any]) -> Optional[Offer]:
        """Update offer"""
        with transaction.atomic():
            try:
                offer = Offer.objects.get(id=offer_id, tenant_id=self.tenant_id)
                
                # Update fields
                for key, value in data.items():
                    if hasattr(offer, key):
                        setattr(offer, key, value)
                
                offer.save()
                
                # Invalidate cache
                self._invalidate_cache()
                
                return offer
                
            except Offer.DoesNotExist:
                return None
    
    def delete(self, offer_id: int) -> bool:
        """Delete offer"""
        with transaction.atomic():
            try:
                offer = Offer.objects.get(id=offer_id, tenant_id=self.tenant_id)
                offer.delete()
                
                # Invalidate cache
                self._invalidate_cache()
                
                return True
                
            except Offer.DoesNotExist:
                return False
    
    def list(self, filters: Dict = None, order_by: str = '-created_at', 
             limit: int = None, offset: int = None) -> List[Offer]:
        """List offers with filters"""
        cache_key = self._get_cache_key('list', filters, order_by, limit, offset)
        offers = self._get_from_cache(cache_key)
        
        if offers is None:
            queryset = Offer.objects.filter(tenant_id=self.tenant_id)
            
            # Apply filters
            if filters:
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                if 'category_id' in filters:
                    queryset = queryset.filter(category_id=filters['category_id'])
                if 'is_featured' in filters:
                    queryset = queryset.filter(is_featured=filters['is_featured'])
                if 'is_hot' in filters:
                    queryset = queryset.filter(is_hot=filters['is_hot'])
                if 'is_new' in filters:
                    queryset = queryset.filter(is_new=filters['is_new'])
                if 'platforms' in filters:
                    queryset = queryset.filter(platforms__contains=filters['platforms'])
                if 'device_type' in filters:
                    queryset = queryset.filter(device_type=filters['device_type'])
                if 'difficulty' in filters:
                    queryset = queryset.filter(difficulty=filters['difficulty'])
                if 'min_reward' in filters:
                    queryset = queryset.filter(reward_amount__gte=filters['min_reward'])
                if 'max_reward' in filters:
                    queryset = queryset.filter(reward_amount__lte=filters['max_reward'])
                if 'search' in filters:
                    search = filters['search']
                    queryset = queryset.filter(
                        Q(title__icontains=search) |
                        Q(description__icontains=search)
                    )
            
            # Apply ordering
            queryset = queryset.order_by(order_by)
            
            # Apply pagination
            if offset:
                queryset = queryset[offset:]
            if limit:
                queryset = queryset[:limit]
            
            offers = list(queryset.select_related('category').prefetch_related('tags'))
            self._set_cache(cache_key, offers)
        
        return offers
    
    def count(self, filters: Dict = None) -> int:
        """Count offers with filters"""
        cache_key = self._get_cache_key('count', filters)
        count = self._get_from_cache(cache_key)
        
        if count is None:
            queryset = Offer.objects.filter(tenant_id=self.tenant_id)
            
            # Apply filters
            if filters:
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                if 'category_id' in filters:
                    queryset = queryset.filter(category_id=filters['category_id'])
                if 'search' in filters:
                    search = filters['search']
                    queryset = queryset.filter(
                        Q(title__icontains=search) |
                        Q(description__icontains=search)
                    )
            
            count = queryset.count()
            self._set_cache(cache_key, count)
        
        return count
    
    def get_active_offers(self, category_id: int = None, limit: int = None) -> List[Offer]:
        """Get active offers"""
        filters = {'status': OfferStatus.ACTIVE}
        if category_id:
            filters['category_id'] = category_id
        
        return self.list(filters=filters, limit=limit)
    
    def get_featured_offers(self, limit: int = 10) -> List[Offer]:
        """Get featured offers"""
        filters = {
            'status': OfferStatus.ACTIVE,
            'is_featured': True
        }
        return self.list(filters=filters, limit=limit)
    
    def get_hot_offers(self, limit: int = 10) -> List[Offer]:
        """Get hot offers"""
        filters = {
            'status': OfferStatus.ACTIVE,
            'is_hot': True
        }
        return self.list(filters=filters, limit=limit)
    
    def get_new_offers(self, days: int = 7, limit: int = 10) -> List[Offer]:
        """Get new offers"""
        start_date = timezone.now() - timedelta(days=days)
        queryset = Offer.objects.filter(
            tenant_id=self.tenant_id,
            status=OfferStatus.ACTIVE,
            is_new=True,
            created_at__gte=start_date
        )
        
        if limit:
            queryset = queryset[:limit]
        
        return list(queryset.select_related('category'))
    
    def search(self, query: str, category_id: int = None, limit: int = 20) -> List[Offer]:
        """Search offers"""
        filters = {'search': query}
        if category_id:
            filters['category_id'] = category_id
        
        return self.list(filters=filters, limit=limit)


# ==================== USER ENGAGEMENT REPOSITORY ====================

class UserEngagementRepository(BaseRepository):
    """Repository for UserOfferEngagement model operations"""
    
    def get_by_id(self, engagement_id: int) -> Optional[UserOfferEngagement]:
        """Get engagement by ID"""
        try:
            return UserOfferEngagement.objects.get(id=engagement_id, tenant_id=self.tenant_id)
        except UserOfferEngagement.DoesNotExist:
            return None
    
    def create(self, data: Dict[str, Any]) -> UserOfferEngagement:
        """Create new engagement"""
        with transaction.atomic():
            # Set tenant_id
            data['tenant_id'] = self.tenant_id
            
            engagement = UserOfferEngagement.objects.create(**data)
            
            # Invalidate cache
            self._invalidate_cache()
            
            return engagement
    
    def update(self, engagement_id: int, data: Dict[str, Any]) -> Optional[UserOfferEngagement]:
        """Update engagement"""
        with transaction.atomic():
            try:
                engagement = UserOfferEngagement.objects.get(id=engagement_id, tenant_id=self.tenant_id)
                
                # Update fields
                for key, value in data.items():
                    if hasattr(engagement, key):
                        setattr(engagement, key, value)
                
                engagement.save()
                
                # Invalidate cache
                self._invalidate_cache()
                
                return engagement
                
            except UserOfferEngagement.DoesNotExist:
                return None
    
    def get_user_engagements(self, user_id: int, status: str = None, 
                           limit: int = None) -> List[UserOfferEngagement]:
        """Get user's engagements"""
        queryset = UserOfferEngagement.objects.filter(
            tenant_id=self.tenant_id,
            user_id=user_id
        )
        
        if status:
            queryset = queryset.filter(status=status)
        
        if limit:
            queryset = queryset[:limit]
        
        return list(queryset.select_related('offer', 'offer__category'))
    
    def get_engagement_by_offer(self, user_id: int, offer_id: int) -> Optional[UserOfferEngagement]:
        """Get user's engagement for specific offer"""
        try:
            return UserOfferEngagement.objects.get(
                tenant_id=self.tenant_id,
                user_id=user_id,
                offer_id=offer_id
            )
        except UserOfferEngagement.DoesNotExist:
            return None
    
    def get_user_completed_engagements(self, user_id: int, days: int = 30) -> List[UserOfferEngagement]:
        """Get user's completed engagements"""
        start_date = timezone.now() - timedelta(days=days)
        
        return list(
            UserOfferEngagement.objects.filter(
                tenant_id=self.tenant_id,
                user_id=user_id,
                status=EngagementStatus.COMPLETED,
                completed_at__gte=start_date
            ).select_related('offer', 'offer__category')
        )
    
    def get_pending_engagements(self, user_id: int) -> List[UserOfferEngagement]:
        """Get user's pending engagements"""
        return list(
            UserOfferEngagement.objects.filter(
                tenant_id=self.tenant_id,
                user_id=user_id,
                status=EngagementStatus.IN_PROGRESS
            ).select_related('offer', 'offer__category')
        )


# ==================== CONVERSION REPOSITORY ====================

class ConversionRepository(BaseRepository):
    """Repository for OfferConversion model operations"""
    
    def get_by_id(self, conversion_id: int) -> Optional[OfferConversion]:
        """Get conversion by ID"""
        try:
            return OfferConversion.objects.get(id=conversion_id, tenant_id=self.tenant_id)
        except OfferConversion.DoesNotExist:
            return None
    
    def create(self, data: Dict[str, Any]) -> OfferConversion:
        """Create new conversion"""
        with transaction.atomic():
            # Set tenant_id
            data['tenant_id'] = self.tenant_id
            
            conversion = OfferConversion.objects.create(**data)
            
            # Invalidate cache
            self._invalidate_cache()
            
            return conversion
    
    def update(self, conversion_id: int, data: Dict[str, Any]) -> Optional[OfferConversion]:
        """Update conversion"""
        with transaction.atomic():
            try:
                conversion = OfferConversion.objects.get(id=conversion_id, tenant_id=self.tenant_id)
                
                # Update fields
                for key, value in data.items():
                    if hasattr(conversion, key):
                        setattr(conversion, key, value)
                
                conversion.save()
                
                # Invalidate cache
                self._invalidate_cache()
                
                return conversion
                
            except OfferConversion.DoesNotExist:
                return None
    
    def get_user_conversions(self, user_id: int, status: str = None,
                           days: int = None) -> List[OfferConversion]:
        """Get user's conversions"""
        queryset = OfferConversion.objects.filter(
            tenant_id=self.tenant_id,
            engagement__user_id=user_id
        )
        
        if status:
            queryset = queryset.filter(status=status)
        
        if days:
            start_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(created_at__gte=start_date)
        
        return list(
            queryset.select_related('engagement', 'engagement__offer')
            .order_by('-created_at')
        )
    
    def get_pending_conversions(self, limit: int = 100) -> List[OfferConversion]:
        """Get pending conversions"""
        return list(
            OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                status=ConversionStatus.PENDING
            ).select_related('engagement', 'engagement__offer', 'engagement__user')[:limit]
        )
    
    def get_fraudulent_conversions(self, days: int = 7) -> List[OfferConversion]:
        """Get potentially fraudulent conversions"""
        start_date = timezone.now() - timedelta(days=days)
        
        return list(
            OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                fraud_score__gte=FRAUD_SCORE_THRESHOLD,
                created_at__gte=start_date
            ).select_related('engagement', 'engagement__offer', 'engagement__user')
        )
    
    def approve_conversion(self, conversion_id: int, approved_by: int = None) -> Optional[OfferConversion]:
        """Approve conversion"""
        return self.update(conversion_id, {
            'status': ConversionStatus.APPROVED,
            'approved_at': timezone.now(),
            'approved_by_id': approved_by
        })
    
    def reject_conversion(self, conversion_id: int, reason: str = None, rejected_by: int = None) -> Optional[OfferConversion]:
        """Reject conversion"""
        return self.update(conversion_id, {
            'status': ConversionStatus.REJECTED,
            'rejection_reason': reason,
            'rejected_by_id': rejected_by
        })


# ==================== REWARD REPOSITORY ====================

class RewardRepository(BaseRepository):
    """Repository for OfferReward model operations"""
    
    def get_by_id(self, reward_id: int) -> Optional[OfferReward]:
        """Get reward by ID"""
        try:
            return OfferReward.objects.get(id=reward_id, tenant_id=self.tenant_id)
        except OfferReward.DoesNotExist:
            return None
    
    def create(self, data: Dict[str, Any]) -> OfferReward:
        """Create new reward"""
        with transaction.atomic():
            # Set tenant_id
            data['tenant_id'] = self.tenant_id
            
            reward = OfferReward.objects.create(**data)
            
            # Invalidate cache
            self._invalidate_cache()
            
            return reward
    
    def update(self, reward_id: int, data: Dict[str, Any]) -> Optional[OfferReward]:
        """Update reward"""
        with transaction.atomic():
            try:
                reward = OfferReward.objects.get(id=reward_id, tenant_id=self.tenant_id)
                
                # Update fields
                for key, value in data.items():
                    if hasattr(reward, key):
                        setattr(reward, key, value)
                
                reward.save()
                
                # Invalidate cache
                self._invalidate_cache()
                
                return reward
                
            except OfferReward.DoesNotExist:
                return None
    
    def get_user_rewards(self, user_id: int, status: str = None,
                       days: int = None) -> List[OfferReward]:
        """Get user's rewards"""
        queryset = OfferReward.objects.filter(
            tenant_id=self.tenant_id,
            user_id=user_id
        )
        
        if status:
            queryset = queryset.filter(status=status)
        
        if days:
            start_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(created_at__gte=start_date)
        
        return list(
            queryset.select_related('offer', 'offer__category')
            .order_by('-created_at')
        )
    
    def get_pending_rewards(self, limit: int = 100) -> List[OfferReward]:
        """Get pending rewards"""
        return list(
            OfferReward.objects.filter(
                tenant_id=self.tenant_id,
                status=RewardStatus.PENDING
            ).select_related('user', 'offer')[:limit]
        )
    
    def approve_reward(self, reward_id: int) -> Optional[OfferReward]:
        """Approve reward"""
        return self.update(reward_id, {
            'status': RewardStatus.APPROVED,
            'approved_at': timezone.now()
        })
    
    def process_payment(self, reward_id: int, payment_method: str = None, 
                       payment_reference: str = None) -> Optional[OfferReward]:
        """Process reward payment"""
        return self.update(reward_id, {
            'status': RewardStatus.PAID,
            'paid_at': timezone.now(),
            'payment_method': payment_method,
            'payment_reference': payment_reference
        })


# ==================== WALLET REPOSITORY ====================

class WalletRepository(BaseRepository):
    """Repository for UserWallet model operations"""
    
    def get_by_id(self, wallet_id: int) -> Optional[UserWallet]:
        """Get wallet by ID"""
        try:
            return UserWallet.objects.get(id=wallet_id, tenant_id=self.tenant_id)
        except UserWallet.DoesNotExist:
            return None
    
    def get_user_wallet(self, user_id: int) -> Optional[UserWallet]:
        """Get user's wallet"""
        try:
            return UserWallet.objects.get(user_id=user_id, tenant_id=self.tenant_id)
        except UserWallet.DoesNotExist:
            return None
    
    def create_user_wallet(self, user_id: int) -> UserWallet:
        """Create user wallet"""
        with transaction.atomic():
            wallet = UserWallet.objects.create(
                tenant_id=self.tenant_id,
                user_id=user_id
            )
            
            # Invalidate cache
            self._invalidate_cache()
            
            return wallet
    
    def get_or_create_user_wallet(self, user_id: int) -> UserWallet:
        """Get or create user wallet"""
        wallet = self.get_user_wallet(user_id)
        
        if wallet is None:
            wallet = self.create_user_wallet(user_id)
        
        return wallet
    
    def update_balance(self, user_id: int, current_balance: Decimal = None,
                     pending_balance: Decimal = None, total_earned: Decimal = None,
                     total_withdrawn: Decimal = None) -> Optional[UserWallet]:
        """Update wallet balance"""
        with transaction.atomic():
            wallet = self.get_or_create_user_wallet(user_id)
            
            if current_balance is not None:
                wallet.current_balance = current_balance
            if pending_balance is not None:
                wallet.pending_balance = pending_balance
            if total_earned is not None:
                wallet.total_earned = total_earned
            if total_withdrawn is not None:
                wallet.total_withdrawn = total_withdrawn
            
            wallet.save()
            
            # Invalidate cache
            self._invalidate_cache()
            
            return wallet
    
    def freeze_wallet(self, user_id: int, reason: str = None) -> Optional[UserWallet]:
        """Freeze user wallet"""
        with transaction.atomic():
            wallet = self.get_or_create_user_wallet(user_id)
            
            wallet.is_frozen = True
            wallet.freeze_reason = reason
            wallet.frozen_at = timezone.now()
            wallet.save()
            
            # Invalidate cache
            self._invalidate_cache()
            
            return wallet
    
    def unfreeze_wallet(self, user_id: int) -> Optional[UserWallet]:
        """Unfreeze user wallet"""
        with transaction.atomic():
            wallet = self.get_or_create_user_wallet(user_id)
            
            wallet.is_frozen = False
            wallet.freeze_reason = None
            wallet.frozen_at = None
            wallet.save()
            
            # Invalidate cache
            self._invalidate_cache()
            
            return wallet


# ==================== NETWORK REPOSITORY ====================

class NetworkRepository(BaseRepository):
    """Repository for AdNetwork model operations"""
    
    def get_by_id(self, network_id: int) -> Optional[AdNetwork]:
        """Get network by ID"""
        try:
            return AdNetwork.objects.get(id=network_id, tenant_id=self.tenant_id)
        except AdNetwork.DoesNotExist:
            return None
    
    def create(self, data: Dict[str, Any]) -> AdNetwork:
        """Create new network"""
        with transaction.atomic():
            # Set tenant_id
            data['tenant_id'] = self.tenant_id
            
            network = AdNetwork.objects.create(**data)
            
            # Invalidate cache
            self._invalidate_cache()
            
            return network
    
    def update(self, network_id: int, data: Dict[str, Any]) -> Optional[AdNetwork]:
        """Update network"""
        with transaction.atomic():
            try:
                network = AdNetwork.objects.get(id=network_id, tenant_id=self.tenant_id)
                
                # Update fields
                for key, value in data.items():
                    if hasattr(network, key):
                        setattr(network, key, value)
                
                network.save()
                
                # Invalidate cache
                self._invalidate_cache()
                
                return network
                
            except AdNetwork.DoesNotExist:
                return None
    
    def get_active_networks(self) -> List[AdNetwork]:
        """Get active networks"""
        return list(
            AdNetwork.objects.filter(
                tenant_id=self.tenant_id,
                is_active=True,
                status=NetworkStatus.ACTIVE
            )
        )
    
    def get_network_by_type(self, network_type: str) -> Optional[AdNetwork]:
        """Get network by type"""
        try:
            return AdNetwork.objects.get(
                tenant_id=self.tenant_id,
                network_type=network_type
            )
        except AdNetwork.DoesNotExist:
            return None
    
    def update_sync_status(self, network_id: int, last_sync: datetime = None,
                          total_offers: int = None, sync_status: str = None) -> Optional[AdNetwork]:
        """Update network sync status"""
        update_data = {}
        
        if last_sync:
            update_data['last_sync'] = last_sync
        if total_offers is not None:
            update_data['total_offers'] = total_offers
        if sync_status:
            update_data['sync_status'] = sync_status
        
        return self.update(network_id, update_data)


# ==================== CATEGORY REPOSITORY ====================

class CategoryRepository(BaseRepository):
    """Repository for OfferCategory model operations"""
    
    def get_by_id(self, category_id: int) -> Optional[OfferCategory]:
        """Get category by ID"""
        try:
            return OfferCategory.objects.get(id=category_id)
        except OfferCategory.DoesNotExist:
            return None
    
    def create(self, data: Dict[str, Any]) -> OfferCategory:
        """Create new category"""
        with transaction.atomic():
            category = OfferCategory.objects.create(**data)
            
            # Invalidate cache
            self._invalidate_cache()
            
            return category
    
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
    
    def get_popular_categories(self, limit: int = 10) -> List[OfferCategory]:
        """Get popular categories"""
        return list(
            OfferCategory.objects.annotate(
                offer_count=Count('offer', filter=Q(offer__status=OfferStatus.ACTIVE))
            ).filter(offer_count__gt=0).order_by('-offer_count')[:limit]
        )


# ==================== TAG REPOSITORY ====================

class TagRepository(BaseRepository):
    """Repository for OfferTag model operations"""
    
    def get_by_id(self, tag_id: int) -> Optional[OfferTag]:
        """Get tag by ID"""
        try:
            return OfferTag.objects.get(id=tag_id, tenant_id=self.tenant_id)
        except OfferTag.DoesNotExist:
            return None
    
    def create(self, data: Dict[str, Any]) -> OfferTag:
        """Create new tag"""
        with transaction.atomic():
            # Set tenant_id
            data['tenant_id'] = self.tenant_id
            
            tag = OfferTag.objects.create(**data)
            
            # Invalidate cache
            self._invalidate_cache()
            
            return tag
    
    def get_all_tags(self) -> List[OfferTag]:
        """Get all active tags"""
        cache_key = self._get_cache_key('all_tags')
        tags = self._get_from_cache(cache_key)
        
        if tags is None:
            tags = list(
                OfferTag.objects.filter(
                    tenant_id=self.tenant_id,
                    is_active=True
                ).annotate(
                    usage_count=Count('offertagging')
                ).order_by('-usage_count')
            )
            self._set_cache(cache_key, tags)
        
        return tags
    
    def get_popular_tags(self, limit: int = 20) -> List[OfferTag]:
        """Get popular tags"""
        return list(
            OfferTag.objects.filter(
                tenant_id=self.tenant_id,
                is_active=True
            ).annotate(
                usage_count=Count('offertagging')
            ).order_by('-usage_count')[:limit]
        )
    
    def get_tags_by_offer(self, offer_id: int) -> List[OfferTag]:
        """Get tags for specific offer"""
        return list(
            OfferTag.objects.filter(
                tenant_id=self.tenant_id,
                offertagging__offer_id=offer_id,
                is_active=True
            )
        )


# ==================== REPOSITORY FACTORY ====================

class RepositoryFactory:
    """Factory for creating repositories"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
    
    def offer(self) -> OfferRepository:
        """Create offer repository"""
        return OfferRepository(self.tenant_id)
    
    def user_engagement(self) -> UserEngagementRepository:
        """Create user engagement repository"""
        return UserEngagementRepository(self.tenant_id)
    
    def conversion(self) -> ConversionRepository:
        """Create conversion repository"""
        return ConversionRepository(self.tenant_id)
    
    def reward(self) -> RewardRepository:
        """Create reward repository"""
        return RewardRepository(self.tenant_id)
    
    def wallet(self) -> WalletRepository:
        """Create wallet repository"""
        return WalletRepository(self.tenant_id)
    
    def network(self) -> NetworkRepository:
        """Create network repository"""
        return NetworkRepository(self.tenant_id)
    
    def category(self) -> CategoryRepository:
        """Create category repository"""
        return CategoryRepository()
    
    def tag(self) -> TagRepository:
        """Create tag repository"""
        return TagRepository(self.tenant_id)


# ==================== EXPORTS ====================

__all__ = [
    # Base repository
    'BaseRepository',
    
    # Repositories
    'OfferRepository',
    'UserEngagementRepository',
    'ConversionRepository',
    'RewardRepository',
    'WalletRepository',
    'NetworkRepository',
    'CategoryRepository',
    'TagRepository',
    
    # Factory
    'RepositoryFactory',
]
