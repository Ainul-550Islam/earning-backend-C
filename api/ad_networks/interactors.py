"""
api/ad_networks/interactors.py
Interactors for ad networks module - Clean Architecture Pattern
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
from .repositories import RepositoryFactory
from .selectors import SelectorFactory
from .helpers import get_cache_key, generate_tracking_id, calculate_percentage

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== BASE INTERACTOR ====================

class BaseInteractor:
    """Base interactor with common functionality"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.repositories = RepositoryFactory(tenant_id)
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


# ==================== OFFER INTERACTORS ====================

class OfferInteractor(BaseInteractor):
    """Interactor for offer operations"""
    
    def get_offer_details(self, offer_id: int, user_id: int = None) -> Dict[str, Any]:
        """Get detailed offer information"""
        # Get offer
        offer = self.repositories.offer().get_by_id(offer_id)
        if not offer:
            raise ValueError("Offer not found")
        
        # Get user-specific data if user is provided
        user_data = None
        if user_id:
            user_data = self._get_user_offer_data(offer_id, user_id)
        
        # Get offer statistics
        stats = self._get_offer_statistics(offer_id)
        
        # Get related offers
        related_offers = self._get_related_offers(offer_id, limit=5)
        
        return {
            'offer': self._serialize_offer(offer),
            'user_data': user_data,
            'statistics': stats,
            'related_offers': related_offers,
        }
    
    def _get_user_offer_data(self, offer_id: int, user_id: int) -> Dict[str, Any]:
        """Get user-specific data for offer"""
        # Check if user has engagement
        engagement = self.selectors.user_engagement().get_engagement_by_offer(user_id, offer_id)
        
        # Check daily limit
        daily_limit = OfferDailyLimit.objects.filter(
            tenant_id=self.tenant_id,
            user_id=user_id,
            offer_id=offer_id
        ).first()
        
        # Get user's completed similar offers
        similar_offers = self.repositories.offer().list(
            filters={
                'category_id': Offer.objects.get(id=offer_id).category_id
            }
        )
        completed_similar = 0
        for similar_offer in similar_offers:
            if self.selectors.user_engagement().get_engagement_by_offer(user_id, similar_offer.id):
                completed_similar += 1
        
        return {
            'has_engagement': engagement is not None,
            'engagement_status': engagement.status if engagement else None,
            'can_start': engagement is None and (daily_limit is None or not daily_limit.is_limit_reached),
            'daily_limit_reached': daily_limit.is_limit_reached if daily_limit else False,
            'daily_count': daily_limit.count_today if daily_limit else 0,
            'daily_limit': daily_limit.daily_limit if daily_limit else None,
            'completed_similar_offers': completed_similar,
        }
    
    def _get_offer_statistics(self, offer_id: int) -> Dict[str, Any]:
        """Get offer statistics"""
        offer = self.repositories.offer().get_by_id(offer_id)
        
        return {
            'total_conversions': offer.total_conversions,
            'total_clicks': offer.total_clicks,
            'conversion_rate': offer.conversion_rate,
            'performance_score': offer.performance_score,
            'avg_completion_time': offer.avg_completion_time,
            'success_rate': offer.success_rate,
            'remaining_conversions': offer.remaining_conversions,
            'is_available': offer.is_available,
        }
    
    def _get_related_offers(self, offer_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Get related offers"""
        offer = self.repositories.offer().get_by_id(offer_id)
        
        # Get offers from same category
        related = self.repositories.offer().list(
            filters={
                'category_id': offer.category_id,
                'status': OfferStatus.ACTIVE
            },
            limit=limit + 1  # +1 to exclude current offer
        )
        
        # Exclude current offer
        related = [o for o in related if o.id != offer_id][:limit]
        
        return [self._serialize_offer(o) for o in related]
    
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
        }
    
    def start_offer_engagement(self, user_id: int, offer_id: int, device_info: Dict = None) -> Dict[str, Any]:
        """Start offer engagement with business logic"""
        with transaction.atomic():
            # Validate offer
            offer = self.repositories.offer().get_by_id(offer_id)
            if not offer:
                raise ValueError("Offer not found")
            
            if not offer.is_available:
                raise ValueError("Offer is not available")
            
            # Check user eligibility
            self._validate_user_eligibility(user_id, offer)
            
            # Check daily limits
            self._check_daily_limits(user_id, offer_id)
            
            # Create engagement
            engagement_data = {
                'user_id': user_id,
                'offer_id': offer_id,
                'status': EngagementStatus.IN_PROGRESS,
                'started_at': timezone.now(),
                'device_info': device_info or {},
            }
            
            engagement = self.repositories.user_engagement().create(engagement_data)
            
            # Create click tracking
            tracking_id = generate_tracking_id()
            click_data = {
                'user_id': user_id,
                'offer_id': offer_id,
                'tracking_id': tracking_id,
                'clicked_at': timezone.now(),
                'device_info': device_info or {},
            }
            
            self.repositories.offer().create(click_data) if hasattr(self.repositories, 'click') else None
            
            # Update daily limit
            self._increment_daily_limit(user_id, offer_id)
            
            # Update offer stats
            offer.total_clicks += 1
            offer.save(update_fields=['total_clicks'])
            
            return {
                'engagement_id': engagement.id,
                'tracking_id': tracking_id,
                'status': engagement.status,
                'started_at': engagement.started_at.isoformat(),
                'offer_data': self._serialize_offer(offer),
            }
    
    def _validate_user_eligibility(self, user_id: int, offer: Offer):
        """Validate user eligibility for offer"""
        # Check if user already completed
        existing = self.selectors.user_engagement().get_engagement_by_offer(user_id, offer.id)
        if existing and existing.status == EngagementStatus.COMPLETED:
            raise ValueError("Offer already completed")
        
        # Check if user has pending engagement
        if existing and existing.status == EngagementStatus.IN_PROGRESS:
            raise ValueError("Offer already in progress")
        
        # Check age restrictions
        user = User.objects.get(id=user_id)
        if offer.min_age and user.age < offer.min_age:
            raise ValueError(f"User must be at least {offer.min_age} years old")
        
        if offer.max_age and user.age > offer.max_age:
            raise ValueError(f"User must be at most {offer.max_age} years old")
        
        # Check country restrictions
        if offer.countries and user.country not in offer.countries:
            raise ValueError("Offer not available in user's country")
    
    def _check_daily_limits(self, user_id: int, offer_id: int):
        """Check daily limits for offer"""
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


# ==================== USER ENGAGEMENT INTERACTOR ====================

class UserEngagementInteractor(BaseInteractor):
    """Interactor for user engagement operations"""
    
    def complete_offer_engagement(self, user_id: int, engagement_id: int, 
                                completion_data: Dict = None) -> Dict[str, Any]:
        """Complete offer engagement with business logic"""
        with transaction.atomic():
            # Get engagement
            engagement = self.repositories.user_engagement().get_by_id(engagement_id)
            if not engagement or engagement.user_id != user_id:
                raise ValueError("Engagement not found")
            
            if engagement.status != EngagementStatus.IN_PROGRESS:
                raise ValueError("Engagement is not in progress")
            
            # Validate completion data
            validated_data = self._validate_completion_data(completion_data or {})
            
            # Update engagement
            engagement.status = EngagementStatus.COMPLETED
            engagement.completed_at = timezone.now()
            engagement.completion_data = validated_data
            engagement.save()
            
            # Create conversion
            conversion_data = {
                'engagement_id': engagement.id,
                'status': ConversionStatus.PENDING,
                'payout': engagement.offer.reward_amount,
                'currency': engagement.offer.reward_currency,
                'created_at': timezone.now(),
            }
            
            conversion = self.repositories.conversion().create(conversion_data)
            
            # Update offer statistics
            offer = engagement.offer
            offer.total_conversions += 1
            offer.save(update_fields=['total_conversions'])
            
            # Trigger fraud detection
            fraud_score = self._calculate_fraud_score(engagement, validated_data)
            if fraud_score > FRAUD_SCORE_THRESHOLD:
                conversion.fraud_score = fraud_score
                conversion.is_fraud = True
                conversion.save()
            
            return {
                'engagement_id': engagement.id,
                'conversion_id': conversion.id,
                'status': engagement.status,
                'completed_at': engagement.completed_at.isoformat(),
                'conversion_status': conversion.status,
                'payout': float(conversion.payout),
                'currency': conversion.currency,
                'fraud_score': fraud_score,
                'is_fraud': conversion.is_fraud,
            }
    
    def _validate_completion_data(self, data: Dict) -> Dict:
        """Validate completion data"""
        # Add validation logic here
        validated_data = data.copy()
        
        # Validate required fields
        if 'screenshot' in data and not data['screenshot']:
            raise ValueError("Screenshot is required")
        
        if 'completion_proof' in data and not data['completion_proof']:
            raise ValueError("Completion proof is required")
        
        return validated_data
    
    def _calculate_fraud_score(self, engagement: UserOfferEngagement, 
                              completion_data: Dict) -> float:
        """Calculate fraud score for engagement"""
        score = 0.0
        
        # Check completion time
        if engagement.completion_time_minutes and engagement.completion_time_minutes < 1:
            score += 30  # Suspiciously fast completion
        
        # Check device consistency
        if engagement.device_info != completion_data.get('device_info'):
            score += 20  # Device mismatch
        
        # Check IP address
        if hasattr(engagement, 'ip_address') and hasattr(completion_data, 'ip_address'):
            if engagement.ip_address != completion_data.get('ip_address'):
                score += 25  # IP address change
        
        # Check time of day
        completion_hour = engagement.completed_at.hour
        if completion_hour < 6 or completion_hour > 23:
            score += 15  # Unusual completion time
        
        # Check user's completion pattern
        user_engagements = self.selectors.user_engagement().get_user_completed_engagements(
            engagement.user_id, days=7
        )
        if len(user_engagements) > 50:  # Too many completions
            score += 20
        
        return min(score, 100.0)  # Cap at 100
    
    def get_user_engagement_history(self, user_id: int, days: int = 30,
                                   status: str = None) -> Dict[str, Any]:
        """Get user's engagement history with analytics"""
        engagements = self.selectors.user_engagement().get_user_engagements(
            user_id=user_id,
            status=status
        )
        
        # Filter by date range
        if days:
            start_date = timezone.now() - timedelta(days=days)
            engagements = [e for e in engagements if e.created_at >= start_date]
        
        # Calculate statistics
        total_engagements = len(engagements)
        completed_engagements = [e for e in engagements if e.status == EngagementStatus.COMPLETED]
        in_progress_engagements = [e for e in engagements if e.status == EngagementStatus.IN_PROGRESS]
        
        # Calculate completion rate
        completion_rate = calculate_percentage(len(completed_engagements), total_engagements)
        
        # Get daily statistics
        daily_stats = self._calculate_daily_engagement_stats(engagements, days)
        
        return {
            'period_days': days,
            'total_engagements': total_engagements,
            'completed_engagements': len(completed_engagements),
            'in_progress_engagements': len(in_progress_engagements),
            'completion_rate': completion_rate,
            'daily_statistics': daily_stats,
            'engagements': [self._serialize_engagement(e) for e in engagements],
        }
    
    def _calculate_daily_engagement_stats(self, engagements: List[UserOfferEngagement], 
                                        days: int) -> List[Dict[str, Any]]:
        """Calculate daily engagement statistics"""
        daily_stats = []
        
        for i in range(days):
            date = (timezone.now() - timedelta(days=i)).date()
            day_engagements = [e for e in engagements if e.created_at.date() == date]
            
            daily_stats.append({
                'date': date.isoformat(),
                'total_engagements': len(day_engagements),
                'completed_engagements': len([e for e in day_engagements if e.status == EngagementStatus.COMPLETED]),
                'in_progress_engagements': len([e for e in day_engagements if e.status == EngagementStatus.IN_PROGRESS]),
            })
        
        return list(reversed(daily_stats))
    
    def _serialize_engagement(self, engagement: UserOfferEngagement) -> Dict[str, Any]:
        """Serialize engagement data"""
        return {
            'id': engagement.id,
            'offer': OfferInteractor(self.tenant_id)._serialize_offer(engagement.offer),
            'status': engagement.status,
            'created_at': engagement.created_at.isoformat(),
            'started_at': engagement.started_at.isoformat() if engagement.started_at else None,
            'completed_at': engagement.completed_at.isoformat() if engagement.completed_at else None,
            'completion_time_minutes': engagement.completion_time_minutes,
            'device_info': engagement.device_info,
            'completion_data': engagement.completion_data,
        }


# ==================== CONVERSION INTERACTOR ====================

class ConversionInteractor(BaseInteractor):
    """Interactor for conversion operations"""
    
    def approve_conversion(self, conversion_id: int, approved_by: int = None,
                         note: str = None) -> Dict[str, Any]:
        """Approve conversion with business logic"""
        with transaction.atomic():
            # Get conversion
            conversion = self.repositories.conversion().get_by_id(conversion_id)
            if not conversion:
                raise ValueError("Conversion not found")
            
            if conversion.status != ConversionStatus.PENDING:
                raise ValueError("Conversion is not pending")
            
            # Check for fraud
            if conversion.is_fraud and conversion.fraud_score > FRAUD_SCORE_THRESHOLD:
                raise ValueError("Cannot approve fraudulent conversion")
            
            # Approve conversion
            conversion = self.repositories.conversion().approve_conversion(
                conversion_id, approved_by
            )
            
            # Create reward
            reward_data = {
                'user_id': conversion.engagement.user_id,
                'offer_id': conversion.engagement.offer_id,
                'engagement_id': conversion.engagement.id,
                'amount': conversion.payout,
                'currency': conversion.currency,
                'status': RewardStatus.APPROVED,
                'approved_at': timezone.now(),
                'commission': self._calculate_commission(conversion.payout),
            }
            
            reward = self.repositories.reward().create(reward_data)
            
            # Update user wallet
            self._update_user_wallet(conversion.engagement.user_id, conversion.payout)
            
            # Send notifications
            self._send_conversion_notifications(conversion, reward)
            
            return {
                'conversion_id': conversion.id,
                'reward_id': reward.id,
                'status': conversion.status,
                'approved_at': conversion.approved_at.isoformat(),
                'payout': float(conversion.payout),
                'currency': conversion.currency,
                'commission': float(reward.commission),
                'note': note,
            }
    
    def reject_conversion(self, conversion_id: int, reason: str = None,
                        rejected_by: int = None) -> Dict[str, Any]:
        """Reject conversion with business logic"""
        with transaction.atomic():
            # Get conversion
            conversion = self.repositories.conversion().get_by_id(conversion_id)
            if not conversion:
                raise ValueError("Conversion not found")
            
            if conversion.status != ConversionStatus.PENDING:
                raise ValueError("Conversion is not pending")
            
            # Reject conversion
            conversion = self.repositories.conversion().reject_conversion(
                conversion_id, reason, rejected_by
            )
            
            # Send notifications
            self._send_rejection_notifications(conversion, reason)
            
            return {
                'conversion_id': conversion.id,
                'status': conversion.status,
                'rejection_reason': reason,
                'rejected_at': timezone.now().isoformat(),
            }
    
    def _calculate_commission(self, payout: Decimal) -> Decimal:
        """Calculate commission amount"""
        # Get commission rate from settings or use default
        commission_rate = Decimal('0.10')  # 10% commission
        return payout * commission_rate
    
    def _update_user_wallet(self, user_id: int, amount: Decimal):
        """Update user wallet with approved reward"""
        wallet = self.repositories.wallet().get_or_create_user_wallet(user_id)
        
        # Update balances
        wallet.pending_balance += amount
        wallet.total_earned += amount
        wallet.save(update_fields=['pending_balance', 'total_earned'])
    
    def _send_conversion_notifications(self, conversion: OfferConversion, reward: OfferReward):
        """Send conversion approval notifications"""
        # This would integrate with notification service
        logger.info(f"Conversion {conversion.id} approved, reward {reward.id} created")
    
    def _send_rejection_notifications(self, conversion: OfferConversion, reason: str):
        """Send conversion rejection notifications"""
        # This would integrate with notification service
        logger.info(f"Conversion {conversion.id} rejected: {reason}")


# ==================== WALLET INTERACTOR ====================

class WalletInteractor(BaseInteractor):
    """Interactor for wallet operations"""
    
    def get_wallet_summary(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive wallet summary"""
        # Get wallet
        wallet = self.repositories.wallet().get_or_create_user_wallet(user_id)
        
        # Get recent transactions
        recent_rewards = self.selectors.reward().get_user_rewards(
            user_id=user_id,
            limit=10
        )
        
        # Get earnings summary
        earnings_7_days = self.selectors.reward().get_user_earnings(user_id, days=7)
        earnings_30_days = self.selectors.reward().get_user_earnings(user_id, days=30)
        
        # Calculate statistics
        total_withdrawn = wallet.total_withdrawn
        available_balance = wallet.current_balance
        pending_balance = wallet.pending_balance
        
        return {
            'wallet': {
                'current_balance': float(available_balance),
                'pending_balance': float(pending_balance),
                'total_earned': float(wallet.total_earned),
                'total_withdrawn': float(total_withdrawn),
                'currency': wallet.currency,
                'is_active': wallet.is_active,
                'is_frozen': wallet.is_frozen,
                'freeze_reason': wallet.freeze_reason,
            },
            'earnings': {
                'last_7_days': earnings_7_days,
                'last_30_days': earnings_30_days,
            },
            'recent_rewards': [self._serialize_reward(r) for r in recent_rewards],
        }
    
    def request_withdrawal(self, user_id: int, amount: Decimal, 
                         payment_method: str = None) -> Dict[str, Any]:
        """Request withdrawal from wallet"""
        with transaction.atomic():
            # Get wallet
            wallet = self.repositories.wallet().get_or_create_user_wallet(user_id)
            
            # Validate withdrawal
            if wallet.is_frozen:
                raise ValueError("Wallet is frozen")
            
            if amount > wallet.current_balance:
                raise ValueError("Insufficient balance")
            
            if amount <= 0:
                raise ValueError("Invalid withdrawal amount")
            
            # Check minimum withdrawal amount
            min_withdrawal = Decimal('10.00')  # Get from settings
            if amount < min_withdrawal:
                raise ValueError(f"Minimum withdrawal amount is {min_withdrawal}")
            
            # Create withdrawal request (this would typically create a separate model)
            # For now, just update wallet balance
            wallet.current_balance -= amount
            wallet.total_withdrawn += amount
            wallet.save(update_fields=['current_balance', 'total_withdrawn'])
            
            return {
                'amount': float(amount),
                'currency': wallet.currency,
                'payment_method': payment_method,
                'new_balance': float(wallet.current_balance),
                'status': 'processed',
            }
    
    def _serialize_reward(self, reward: OfferReward) -> Dict[str, Any]:
        """Serialize reward data"""
        return {
            'id': reward.id,
            'offer': OfferInteractor(self.tenant_id)._serialize_offer(reward.offer),
            'amount': float(reward.amount),
            'currency': reward.currency,
            'commission': float(reward.commission) if reward.commission else None,
            'status': reward.status,
            'created_at': reward.created_at.isoformat(),
            'approved_at': reward.approved_at.isoformat() if reward.approved_at else None,
            'paid_at': reward.paid_at.isoformat() if reward.paid_at else None,
            'payment_method': reward.payment_method,
            'payment_reference': reward.payment_reference,
        }


# ==================== INTERACTOR FACTORY ====================

class InteractorFactory:
    """Factory for creating interactors"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
    
    def offer(self) -> OfferInteractor:
        """Create offer interactor"""
        return OfferInteractor(self.tenant_id)
    
    def user_engagement(self) -> UserEngagementInteractor:
        """Create user engagement interactor"""
        return UserEngagementInteractor(self.tenant_id)
    
    def conversion(self) -> ConversionInteractor:
        """Create conversion interactor"""
        return ConversionInteractor(self.tenant_id)
    
    def wallet(self) -> WalletInteractor:
        """Create wallet interactor"""
        return WalletInteractor(self.tenant_id)


# ==================== EXPORTS ====================

__all__ = [
    # Base interactor
    'BaseInteractor',
    
    # Interactors
    'OfferInteractor',
    'UserEngagementInteractor',
    'ConversionInteractor',
    'WalletInteractor',
    
    # Factory
    'InteractorFactory',
]
