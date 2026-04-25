"""
api/ad_networks/use_cases.py
Use cases for ad networks module - Clean Architecture Pattern
SaaS-ready with tenant support
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
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
from .selectors import SelectorFactory
from .helpers import get_cache_key, generate_tracking_id

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== BASE USE CASE ====================

class BaseUseCase:
    """Base use case with common functionality"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.selectors = SelectorFactory(tenant_id)
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


# ==================== OFFER USE CASES ====================

class GetOfferUseCase(BaseUseCase):
    """Get offer by ID"""
    
    def execute(self, offer_id: int) -> Optional[Dict[str, Any]]:
        """Execute use case"""
        offer = self.selectors.offer().get_by_id(offer_id)
        
        if not offer:
            return None
        
        return self._serialize_offer(offer)
    
    def _serialize_offer(self, offer: Offer) -> Dict[str, Any]:
        """Serialize offer data"""
        return {
            'id': offer.id,
            'title': offer.title,
            'description': offer.description,
            'reward_amount': float(offer.reward_amount),
            'reward_currency': offer.reward_currency,
            'category': {
                'id': offer.category.id,
                'name': offer.category.name
            } if offer.category else None,
            'platforms': offer.platforms,
            'device_type': offer.device_type,
            'difficulty': offer.difficulty,
            'estimated_time': offer.estimated_time,
            'steps_required': offer.steps_required,
            'countries': offer.countries,
            'min_age': offer.min_age,
            'max_age': offer.max_age,
            'is_featured': offer.is_featured,
            'is_hot': offer.is_hot,
            'is_new': offer.is_new,
            'tags': [{'id': tag.id, 'name': tag.name, 'color': tag.color} for tag in offer.tags.all()],
            'requirements': offer.requirements,
            'terms_url': offer.terms_url,
            'privacy_url': offer.privacy_url,
            'click_url': offer.click_url,
            'preview_url': offer.preview_url,
            'status': offer.status,
            'created_at': offer.created_at.isoformat(),
            'updated_at': offer.updated_at.isoformat(),
            'expires_at': offer.expires_at.isoformat() if offer.expires_at else None,
            'performance_score': offer.performance_score,
            'total_conversions': offer.total_conversions,
            'conversion_rate': offer.conversion_rate,
            'remaining_conversions': offer.remaining_conversions,
        }


class ListOffersUseCase(BaseUseCase):
    """List offers with filters"""
    
    def execute(self, filters: Dict = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Execute use case"""
        filters = filters or {}
        
        # Get offers based on filters
        if filters.get('featured'):
            offers = self.selectors.offer().get_featured_offers(limit=page_size)
        elif filters.get('hot'):
            offers = self.selectors.offer().get_hot_offers(limit=page_size)
        elif filters.get('new'):
            offers = self.selectors.offer().get_new_offers(days=filters.get('days', 7), limit=page_size)
        elif filters.get('category_id'):
            offers = self.selectors.offer().get_active_offers(
                category_id=filters['category_id'],
                platform=filters.get('platform'),
                device_type=filters.get('device_type'),
                limit=page_size
            )
        elif filters.get('search'):
            offers = self.selectors.offer().search_offers(
                query=filters['search'],
                category_id=filters.get('category_id'),
                limit=page_size
            )
        else:
            offers = self.selectors.offer().get_active_offers(
                platform=filters.get('platform'),
                device_type=filters.get('device_type'),
                limit=page_size
            )
        
        # Serialize offers
        get_offer_use_case = GetOfferUseCase(self.tenant_id)
        serialized_offers = []
        
        for offer in offers:
            serialized_offer = get_offer_use_case._serialize_offer(offer)
            serialized_offers.append(serialized_offer)
        
        return {
            'results': serialized_offers,
            'page': page,
            'page_size': page_size,
            'total_count': len(serialized_offers),
            'filters': filters,
        }


class StartOfferUseCase(BaseUseCase):
    """Start offer engagement"""
    
    def execute(self, user_id: int, offer_id: int, device_info: Dict = None) -> Dict[str, Any]:
        """Execute use case"""
        with transaction.atomic():
            # Get offer
            offer = self.selectors.offer().get_by_id(offer_id)
            if not offer:
                raise ValueError("Offer not found")
            
            if offer.status != OfferStatus.ACTIVE:
                raise ValueError("Offer is not active")
            
            # Check if user already has engagement
            existing_engagement = self.selectors.user_engagement().get_engagement_by_offer(user_id, offer_id)
            if existing_engagement:
                if existing_engagement.status == EngagementStatus.COMPLETED:
                    raise ValueError("Offer already completed")
                elif existing_engagement.status == EngagementStatus.IN_PROGRESS:
                    raise ValueError("Offer already in progress")
            
            # Check daily limit
            self._check_daily_limit(user_id, offer_id)
            
            # Create engagement
            engagement = UserOfferEngagement.objects.create(
                tenant_id=self.tenant_id,
                user_id=user_id,
                offer_id=offer_id,
                status=EngagementStatus.IN_PROGRESS,
                started_at=timezone.now(),
                device_info=device_info or {},
            )
            
            # Create click tracking
            tracking_id = generate_tracking_id()
            OfferClick.objects.create(
                tenant_id=self.tenant_id,
                user_id=user_id,
                offer_id=offer_id,
                tracking_id=tracking_id,
                clicked_at=timezone.now(),
                device_info=device_info or {},
            )
            
            # Update daily limit
            self._increment_daily_limit(user_id, offer_id)
            
            return {
                'engagement_id': engagement.id,
                'tracking_id': tracking_id,
                'status': engagement.status,
                'started_at': engagement.started_at.isoformat(),
                'offer': GetOfferUseCase(self.tenant_id)._serialize_offer(offer),
            }
    
    def _check_daily_limit(self, user_id: int, offer_id: int):
        """Check daily limit for offer"""
        daily_limit = OfferDailyLimit.objects.filter(
            tenant_id=self.tenant_id,
            user_id=user_id,
            offer_id=offer_id
        ).first()
        
        if daily_limit and daily_limit.is_limit_reached:
            raise ValueError("Daily limit reached for this offer")
    
    def _increment_daily_limit(self, user_id: int, offer_id: int):
        """Increment daily limit counter"""
        daily_limit, created = OfferDailyLimit.objects.get_or_create(
            tenant_id=self.tenant_id,
            user_id=user_id,
            offer_id=offer_id,
            defaults={'daily_limit': 1}
        )
        
        if not created:
            daily_limit.increment_count()


class CompleteOfferUseCase(BaseUseCase):
    """Complete offer engagement"""
    
    def execute(self, user_id: int, engagement_id: int, completion_data: Dict = None) -> Dict[str, Any]:
        """Execute use case"""
        with transaction.atomic():
            # Get engagement
            engagement = self.selectors.user_engagement().get_engagement_by_offer(user_id, engagement_id)
            if not engagement:
                raise ValueError("Engagement not found")
            
            if engagement.status != EngagementStatus.IN_PROGRESS:
                raise ValueError("Engagement is not in progress")
            
            # Update engagement
            engagement.status = EngagementStatus.COMPLETED
            engagement.completed_at = timezone.now()
            engagement.completion_data = completion_data or {}
            engagement.save()
            
            # Create conversion
            conversion = OfferConversion.objects.create(
                tenant_id=self.tenant_id,
                engagement_id=engagement.id,
                status=ConversionStatus.PENDING,
                payout=engagement.offer.reward_amount,
                currency=engagement.offer.reward_currency,
                created_at=timezone.now(),
            )
            
            # Update offer stats
            offer = engagement.offer
            offer.total_conversions += 1
            offer.save(update_fields=['total_conversions'])
            
            return {
                'engagement_id': engagement.id,
                'conversion_id': conversion.id,
                'status': engagement.status,
                'completed_at': engagement.completed_at.isoformat(),
                'conversion_status': conversion.status,
                'payout': float(conversion.payout),
                'currency': conversion.currency,
            }


# ==================== USER ENGAGEMENT USE CASES ====================

class GetUserEngagementsUseCase(BaseUseCase):
    """Get user's offer engagements"""
    
    def execute(self, user_id: int, status: str = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Execute use case"""
        engagements = self.selectors.user_engagement().get_user_engagements(
            user_id=user_id,
            status=status,
            limit=page_size
        )
        
        # Serialize engagements
        serialized_engagements = []
        
        for engagement in engagements:
            serialized_engagement = {
                'id': engagement.id,
                'offer': GetOfferUseCase(self.tenant_id)._serialize_offer(engagement.offer),
                'status': engagement.status,
                'created_at': engagement.created_at.isoformat(),
                'started_at': engagement.started_at.isoformat() if engagement.started_at else None,
                'completed_at': engagement.completed_at.isoformat() if engagement.completed_at else None,
                'completion_time_minutes': engagement.completion_time_minutes,
                'device_info': engagement.device_info,
                'conversion': self._get_conversion_data(engagement.id) if hasattr(engagement, 'conversion') else None,
            }
            serialized_engagements.append(serialized_engagement)
        
        return {
            'results': serialized_engagements,
            'page': page,
            'page_size': page_size,
            'total_count': len(serialized_engagements),
            'status': status,
        }
    
    def _get_conversion_data(self, engagement_id: int) -> Optional[Dict[str, Any]]:
        """Get conversion data for engagement"""
        try:
            conversion = OfferConversion.objects.get(engagement_id=engagement_id)
            return {
                'id': conversion.id,
                'status': conversion.status,
                'payout': float(conversion.payout),
                'currency': conversion.currency,
                'created_at': conversion.created_at.isoformat(),
                'approved_at': conversion.approved_at.isoformat() if conversion.approved_at else None,
                'fraud_score': conversion.fraud_score,
                'is_fraud': conversion.is_fraud,
            }
        except OfferConversion.DoesNotExist:
            return None


# ==================== CONVERSION USE CASES ====================

class ApproveConversionUseCase(BaseUseCase):
    """Approve conversion"""
    
    def execute(self, conversion_id: int, approved_by: int = None) -> Dict[str, Any]:
        """Execute use case"""
        with transaction.atomic():
            # Get conversion
            try:
                conversion = OfferConversion.objects.get(
                    id=conversion_id,
                    tenant_id=self.tenant_id
                )
            except OfferConversion.DoesNotExist:
                raise ValueError("Conversion not found")
            
            if conversion.status != ConversionStatus.PENDING:
                raise ValueError("Conversion is not pending")
            
            # Update conversion
            conversion.status = ConversionStatus.APPROVED
            conversion.approved_at = timezone.now()
            conversion.approved_by_id = approved_by
            conversion.save()
            
            # Create reward
            reward = OfferReward.objects.create(
                tenant_id=self.tenant_id,
                user_id=conversion.engagement.user_id,
                offer_id=conversion.engagement.offer_id,
                engagement_id=conversion.engagement.id,
                amount=conversion.payout,
                currency=conversion.currency,
                status=RewardStatus.PENDING,
                created_at=timezone.now(),
            )
            
            # Update user wallet
            wallet = self.selectors.wallet().get_or_create_user_wallet(conversion.engagement.user_id)
            wallet.pending_balance += conversion.payout
            wallet.save(update_fields=['pending_balance'])
            
            return {
                'conversion_id': conversion.id,
                'reward_id': reward.id,
                'status': conversion.status,
                'approved_at': conversion.approved_at.isoformat(),
                'payout': float(conversion.payout),
                'currency': conversion.currency,
            }


class RejectConversionUseCase(BaseUseCase):
    """Reject conversion"""
    
    def execute(self, conversion_id: int, reason: str = None, rejected_by: int = None) -> Dict[str, Any]:
        """Execute use case"""
        with transaction.atomic():
            # Get conversion
            try:
                conversion = OfferConversion.objects.get(
                    id=conversion_id,
                    tenant_id=self.tenant_id
                )
            except OfferConversion.DoesNotExist:
                raise ValueError("Conversion not found")
            
            if conversion.status != ConversionStatus.PENDING:
                raise ValueError("Conversion is not pending")
            
            # Update conversion
            conversion.status = ConversionStatus.REJECTED
            conversion.rejection_reason = reason
            conversion.rejected_by_id = rejected_by
            conversion.save()
            
            return {
                'conversion_id': conversion.id,
                'status': conversion.status,
                'rejection_reason': reason,
                'rejected_at': timezone.now().isoformat(),
            }


# ==================== REWARD USE CASES ====================

class GetUserRewardsUseCase(BaseUseCase):
    """Get user's rewards"""
    
    def execute(self, user_id: int, status: str = None, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Execute use case"""
        rewards = self.selectors.reward().get_user_rewards(
            user_id=user_id,
            status=status,
            limit=page_size
        )
        
        # Serialize rewards
        serialized_rewards = []
        
        for reward in rewards:
            serialized_reward = {
                'id': reward.id,
                'offer': GetOfferUseCase(self.tenant_id)._serialize_offer(reward.offer),
                'amount': float(reward.amount),
                'currency': reward.currency,
                'commission': float(reward.commission) if reward.commission else None,
                'status': reward.status,
                'created_at': reward.created_at.isoformat(),
                'approved_at': reward.approved_at.isoformat() if reward.approved_at else None,
                'paid_at': reward.paid_at.isoformat() if reward.paid_at else None,
                'payment_method': reward.payment_method,
                'payment_reference': reward.payment_reference,
                'total_amount': float(reward.total_amount),
            }
            serialized_rewards.append(serialized_reward)
        
        return {
            'results': serialized_rewards,
            'page': page,
            'page_size': page_size,
            'total_count': len(serialized_rewards),
            'status': status,
        }


class ProcessRewardPaymentUseCase(BaseUseCase):
    """Process reward payment"""
    
    def execute(self, reward_id: int, payment_method: str = None, payment_reference: str = None) -> Dict[str, Any]:
        """Execute use case"""
        with transaction.atomic():
            # Get reward
            try:
                reward = OfferReward.objects.get(
                    id=reward_id,
                    tenant_id=self.tenant_id
                )
            except OfferReward.DoesNotExist:
                raise ValueError("Reward not found")
            
            if reward.status != RewardStatus.APPROVED:
                raise ValueError("Reward is not approved")
            
            # Update reward
            reward.status = RewardStatus.PAID
            reward.paid_at = timezone.now()
            reward.payment_method = payment_method
            reward.payment_reference = payment_reference
            reward.save()
            
            # Update user wallet
            wallet = self.selectors.wallet().get_or_create_user_wallet(reward.user_id)
            wallet.pending_balance -= reward.amount
            wallet.total_withdrawn += reward.amount
            wallet.save(update_fields=['pending_balance', 'total_withdrawn'])
            
            return {
                'reward_id': reward.id,
                'status': reward.status,
                'paid_at': reward.paid_at.isoformat(),
                'amount': float(reward.amount),
                'currency': reward.currency,
                'payment_method': payment_method,
                'payment_reference': payment_reference,
            }


# ==================== WALLET USE CASES ====================

class GetUserWalletUseCase(BaseUseCase):
    """Get user wallet information"""
    
    def execute(self, user_id: int) -> Dict[str, Any]:
        """Execute use case"""
        wallet_balance = self.selectors.wallet().get_wallet_balance(user_id)
        
        # Get earnings summary
        earnings = self.selectors.reward().get_user_earnings(user_id, days=30)
        
        return {
            'balance': wallet_balance,
            'earnings': earnings,
        }


# ==================== NETWORK USE CASES ====================

class GetNetworksUseCase(BaseUseCase):
    """Get ad networks"""
    
    def execute(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Execute use case"""
        if active_only:
            networks = self.selectors.network().get_active_networks()
        else:
            networks = AdNetwork.objects.filter(tenant_id=self.tenant_id)
        
        # Serialize networks
        serialized_networks = []
        
        for network in networks:
            serialized_network = {
                'id': network.id,
                'name': network.name,
                'network_type': network.network_type,
                'category': network.category,
                'status': network.status,
                'is_active': network.is_active,
                'description': network.description,
                'logo_url': network.logo_url,
                'website_url': network.website_url,
                'support_url': network.support_url,
                'api_documentation_url': network.api_documentation_url,
                'country_support': network.country_support,
                'supports_offers': network.supports_offers,
                'supports_postback': network.supports_postback,
                'supports_surveys': network.supports_surveys,
                'supports_video': network.supports_video,
                'is_verified': network.is_verified,
                'trust_score': network.trust_score,
                'total_payout': float(network.total_payout) if network.total_payout else 0,
                'last_sync': network.last_sync.isoformat() if network.last_sync else None,
                'created_at': network.created_at.isoformat(),
                'updated_at': network.updated_at.isoformat(),
            }
            serialized_networks.append(serialized_network)
        
        return serialized_networks


# ==================== ANALYTICS USE CASES ====================

class GetUserAnalyticsUseCase(BaseUseCase):
    """Get user analytics data"""
    
    def execute(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Execute use case"""
        # Get user statistics
        engagements = self.selectors.user_engagement().get_user_completed_engagements(user_id, days)
        conversions = self.selectors.conversion().get_user_conversions(user_id, days=days)
        earnings = self.selectors.reward().get_user_earnings(user_id, days=days)
        
        # Calculate metrics
        total_engagements = len(engagements)
        total_conversions = len(conversions)
        conversion_rate = (total_conversions / total_engagements * 100) if total_engagements > 0 else 0
        
        return {
            'period_days': days,
            'total_engagements': total_engagements,
            'total_conversions': total_conversions,
            'conversion_rate': round(conversion_rate, 2),
            'total_earned': float(earnings.get('total_earned', 0)),
            'pending_amount': float(earnings.get('pending_amount', 0)),
            'paid_amount': float(earnings.get('paid_amount', 0)),
            'average_reward': float(earnings.get('total_earned', 0)) / total_conversions if total_conversions > 0 else 0,
            'engagements_by_day': self._get_engagements_by_day(user_id, days),
            'earnings_by_day': self._get_earnings_by_day(user_id, days),
        }
    
    def _get_engagements_by_day(self, user_id: int, days: int) -> List[Dict[str, Any]]:
        """Get engagements grouped by day"""
        # This would typically use database aggregation
        # For now, return empty list
        return []
    
    def _get_earnings_by_day(self, user_id: int, days: int) -> List[Dict[str, Any]]:
        """Get earnings grouped by day"""
        # This would typically use database aggregation
        # For now, return empty list
        return []


# ==================== USE CASE FACTORY ====================

class UseCaseFactory:
    """Factory for creating use cases"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
    
    def get_offer(self) -> GetOfferUseCase:
        """Create get offer use case"""
        return GetOfferUseCase(self.tenant_id)
    
    def list_offers(self) -> ListOffersUseCase:
        """Create list offers use case"""
        return ListOffersUseCase(self.tenant_id)
    
    def start_offer(self) -> StartOfferUseCase:
        """Create start offer use case"""
        return StartOfferUseCase(self.tenant_id)
    
    def complete_offer(self) -> CompleteOfferUseCase:
        """Create complete offer use case"""
        return CompleteOfferUseCase(self.tenant_id)
    
    def get_user_engagements(self) -> GetUserEngagementsUseCase:
        """Create get user engagements use case"""
        return GetUserEngagementsUseCase(self.tenant_id)
    
    def approve_conversion(self) -> ApproveConversionUseCase:
        """Create approve conversion use case"""
        return ApproveConversionUseCase(self.tenant_id)
    
    def reject_conversion(self) -> RejectConversionUseCase:
        """Create reject conversion use case"""
        return RejectConversionUseCase(self.tenant_id)
    
    def get_user_rewards(self) -> GetUserRewardsUseCase:
        """Create get user rewards use case"""
        return GetUserRewardsUseCase(self.tenant_id)
    
    def process_reward_payment(self) -> ProcessRewardPaymentUseCase:
        """Create process reward payment use case"""
        return ProcessRewardPaymentUseCase(self.tenant_id)
    
    def get_user_wallet(self) -> GetUserWalletUseCase:
        """Create get user wallet use case"""
        return GetUserWalletUseCase(self.tenant_id)
    
    def get_networks(self) -> GetNetworksUseCase:
        """Create get networks use case"""
        return GetNetworksUseCase(self.tenant_id)
    
    def get_user_analytics(self) -> GetUserAnalyticsUseCase:
        """Create get user analytics use case"""
        return GetUserAnalyticsUseCase(self.tenant_id)


# ==================== EXPORTS ====================

__all__ = [
    # Base use case
    'BaseUseCase',
    
    # Offer use cases
    'GetOfferUseCase',
    'ListOffersUseCase',
    'StartOfferUseCase',
    'CompleteOfferUseCase',
    
    # User engagement use cases
    'GetUserEngagementsUseCase',
    
    # Conversion use cases
    'ApproveConversionUseCase',
    'RejectConversionUseCase',
    
    # Reward use cases
    'GetUserRewardsUseCase',
    'ProcessRewardPaymentUseCase',
    
    # Wallet use cases
    'GetUserWalletUseCase',
    
    # Network use cases
    'GetNetworksUseCase',
    
    # Analytics use cases
    'GetUserAnalyticsUseCase',
    
    # Factory
    'UseCaseFactory',
]
