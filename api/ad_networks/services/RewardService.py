"""
api/ad_networks/services/RewardService.py
Service for calculating and crediting user rewards
SaaS-ready with tenant support
"""

import logging
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from typing import Dict, Optional, List

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import User

from api.ad_networks.models import (
    OfferReward, UserOfferEngagement, Offer, OfferConversion,
    OfferDailyLimit, UserWallet
)
from api.ad_networks.choices import RewardStatus, EngagementStatus
from api.ad_networks.constants import (
    MAX_DAILY_OFFER_LIMIT,
    CACHE_KEY_PATTERNS
)

logger = logging.getLogger(__name__)


class RewardService:
    """
    Service for calculating and managing user rewards
    """
    
    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id
    
    def calculate_reward(self, engagement: UserOfferEngagement, 
                      conversion_data: Dict = None) -> Dict:
        """
        Calculate reward amount for engagement
        """
        try:
            if not engagement.offer:
                return {
                    'success': False,
                    'error': 'No offer associated with engagement'
                }
            
            offer = engagement.offer
            
            # Base reward amount
            base_reward = offer.reward_amount
            
            # Apply multipliers
            multiplier = self._calculate_reward_multiplier(engagement.user, offer)
            final_reward = base_reward * multiplier
            
            # Apply bonuses
            bonus_amount = self._calculate_bonus_amount(engagement.user, offer, final_reward)
            total_reward = final_reward + bonus_amount
            
            # Apply taxes/fees
            net_reward = self._apply_taxes_and_fees(total_reward, offer)
            
            # Check daily limits
            daily_limit_result = self._check_daily_limit(engagement.user, offer, net_reward)
            if not daily_limit_result['allowed']:
                return {
                    'success': False,
                    'error': daily_limit_result['reason'],
                    'code': 'daily_limit_exceeded'
                }
            
            # Check user wallet
            wallet_result = self._check_user_wallet(engagement.user, net_reward)
            if not wallet_result['allowed']:
                return {
                    'success': False,
                    'error': wallet_result['reason'],
                    'code': 'wallet_limit_exceeded'
                }
            
            result = {
                'success': True,
                'base_reward': base_reward,
                'multiplier': multiplier,
                'bonus_amount': bonus_amount,
                'gross_reward': total_reward,
                'net_reward': net_reward,
                'currency': offer.reward_currency,
                'taxes_applied': self._get_tax_breakdown(total_reward, net_reward),
                'daily_limit_remaining': daily_limit_result['remaining']
            }
            
            logger.info(f"Reward calculated for user {engagement.user.id}: {net_reward}")
            
            return result
            
        except Exception as e:
            logger.error(f"Reward calculation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'code': 'calculation_error'
            }
    
    def credit_reward(self, engagement: UserOfferEngagement, 
                    reward_amount: Decimal, currency: str = 'USD',
                    reason: str = None) -> Dict:
        """
        Credit reward to user wallet
        """
        try:
            with transaction.atomic():
                # Get or create user wallet
                wallet = self._get_or_create_wallet(engagement.user)
                
                # Create reward record
                reward = OfferReward.objects.create(
                    user=engagement.user,
                    offer=engagement.offer,
                    engagement=engagement,
                    amount=reward_amount,
                    currency=currency,
                    status=RewardStatus.PENDING,
                    reason=reason or 'offer_completion',
                    tenant_id=self.tenant_id
                )
                
                # Update wallet balance
                wallet.balance += reward_amount
                wallet.total_earned += reward_amount
                wallet.last_activity = timezone.now()
                wallet.save(update_fields=['balance', 'total_earned', 'last_activity'])
                
                # Update reward status
                reward.status = RewardStatus.APPROVED
                reward.approved_at = timezone.now()
                reward.save(update_fields=['status', 'approved_at'])
                
                # Update engagement
                engagement.reward_earned = reward_amount
                engagement.save(update_fields=['reward_earned'])
                
                # Clear caches
                self._clear_user_caches(engagement.user)
                
                # Trigger reward notification
                self._send_reward_notification(engagement.user, reward)
                
                logger.info(f"Reward credited: {reward_amount} {currency} to user {engagement.user.id}")
                
                return {
                    'success': True,
                    'reward_id': reward.id,
                    'amount': float(reward_amount),
                    'currency': currency,
                    'new_balance': float(wallet.balance),
                    'total_earned': float(wallet.total_earned)
                }
                
        except Exception as e:
            logger.error(f"Reward crediting failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'code': 'crediting_error'
            }
    
    def reverse_reward(self, reward_id: int, reason: str = None) -> Dict:
        """
        Reverse a reward (chargeback)
        """
        try:
            with transaction.atomic():
                # Get reward
                reward = OfferReward.objects.get(id=reward_id)
                
                if reward.status == RewardStatus.CANCELLED:
                    return {
                        'success': False,
                        'error': 'Reward already cancelled',
                        'code': 'already_cancelled'
                    }
                
                # Get user wallet
                wallet = self._get_or_create_wallet(reward.user)
                
                # Check if wallet has sufficient balance
                if wallet.balance < reward.amount:
                    logger.warning(f"Insufficient balance for reward reversal: user {reward.user.id}")
                    # Allow negative balance for chargebacks
                    wallet.balance -= reward.amount
                else:
                    wallet.balance -= reward.amount
                
                wallet.total_earned -= reward.amount
                wallet.last_activity = timezone.now()
                wallet.save(update_fields=['balance', 'total_earned', 'last_activity'])
                
                # Update reward status
                reward.status = RewardStatus.CANCELLED
                reward.cancelled_at = timezone.now()
                reward.cancellation_reason = reason
                reward.save(update_fields=['status', 'cancelled_at', 'cancellation_reason'])
                
                # Clear caches
                self._clear_user_caches(reward.user)
                
                # Send notification
                self._send_reversal_notification(reward.user, reward, reason)
                
                logger.info(f"Reward reversed: {reward.amount} for user {reward.user.id}")
                
                return {
                    'success': True,
                    'reward_id': reward.id,
                    'reversed_amount': float(reward.amount),
                    'new_balance': float(wallet.balance),
                    'reason': reason
                }
                
        except OfferReward.DoesNotExist:
            return {
                'success': False,
                'error': f'Reward with ID {reward_id} not found',
                'code': 'not_found'
            }
        except Exception as e:
            logger.error(f"Reward reversal failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'code': 'reversal_error'
            }
    
    def get_user_rewards(self, user_id: int, status: str = None,
                       limit: int = None, offset: int = 0) -> Dict:
        """
        Get user's rewards with pagination
        """
        try:
            rewards = OfferReward.objects.filter(
                user_id=user_id
            ).select_related(
                'offer', 'engagement'
            ).order_by('-created_at')
            
            if status:
                rewards = rewards.filter(status=status)
            
            total_count = rewards.count()
            
            if limit:
                rewards = rewards[offset:offset + limit]
            
            rewards_data = []
            for reward in rewards:
                rewards_data.append({
                    'id': reward.id,
                    'offer_id': reward.offer.id if reward.offer else None,
                    'offer_title': reward.offer.title if reward.offer else 'Unknown',
                    'engagement_id': reward.engagement.id if reward.engagement else None,
                    'amount': float(reward.amount),
                    'currency': reward.currency,
                    'status': reward.status,
                    'reason': reward.reason,
                    'created_at': reward.created_at,
                    'approved_at': reward.approved_at,
                    'paid_at': reward.paid_at,
                    'cancellation_reason': reward.cancellation_reason
                })
            
            return {
                'success': True,
                'rewards': rewards_data,
                'total_count': total_count,
                'has_more': offset + limit < total_count if limit else False
            }
            
        except Exception as e:
            logger.error(f"Failed to get user rewards: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'rewards': []
            }
    
    def get_user_wallet(self, user_id: int) -> Dict:
        """
        Get user wallet information
        """
        try:
            wallet = self._get_or_create_wallet_by_id(user_id)
            
            # Get recent rewards
            recent_rewards = OfferReward.objects.filter(
                user_id=user_id,
                status=RewardStatus.APPROVED
            ).order_by('-approved_at')[:5]
            
            recent_data = []
            for reward in recent_rewards:
                recent_data.append({
                    'id': reward.id,
                    'amount': float(reward.amount),
                    'currency': reward.currency,
                    'offer_title': reward.offer.title if reward.offer else 'Unknown',
                    'approved_at': reward.approved_at
                })
            
            return {
                'success': True,
                'wallet': {
                    'balance': float(wallet.balance),
                    'total_earned': float(wallet.total_earned),
                    'total_withdrawn': float(wallet.total_withdrawn),
                    'pending_rewards': float(wallet.pending_rewards),
                    'last_activity': wallet.last_activity,
                    'created_at': wallet.created_at
                },
                'recent_rewards': recent_data
            }
            
        except Exception as e:
            logger.error(f"Failed to get user wallet: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_reward_stats(self, user_id: int = None, days: int = 30) -> Dict:
        """
        Get reward statistics
        """
        try:
            from django.db.models import Count, Sum, Avg, Q
            
            # Calculate date range
            end_date = timezone.now()
            start_date = end_date - timedelta(days=days)
            
            # Base queryset
            rewards = OfferReward.objects.filter(
                created_at__gte=start_date,
                created_at__lte=end_date
            )
            
            if user_id:
                rewards = rewards.filter(user_id=user_id)
            
            # Calculate stats
            stats = rewards.aggregate(
                total_rewards=Count('id'),
                approved_rewards=Count(
                    'id',
                    filter=Q(status=RewardStatus.APPROVED)
                ),
                pending_rewards=Count(
                    'id',
                    filter=Q(status=RewardStatus.PENDING)
                ),
                cancelled_rewards=Count(
                    'id',
                    filter=Q(status=RewardStatus.CANCELLED)
                ),
                total_amount=Sum('amount'),
                approved_amount=Sum(
                    'amount',
                    filter=Q(status=RewardStatus.APPROVED)
                ),
                avg_reward=Avg('amount')
            )
            
            # Calculate rates
            approval_rate = 0
            if stats['total_rewards'] > 0:
                approval_rate = (stats['approved_rewards'] / stats['total_rewards']) * 100
            
            return {
                'success': True,
                'period_days': days,
                'total_rewards': stats['total_rewards'],
                'approved_rewards': stats['approved_rewards'],
                'pending_rewards': stats['pending_rewards'],
                'cancelled_rewards': stats['cancelled_rewards'],
                'total_amount': float(stats['total_amount'] or 0),
                'approved_amount': float(stats['approved_amount'] or 0),
                'avg_reward': float(stats['avg_reward'] or 0),
                'approval_rate': round(approval_rate, 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to get reward stats: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_reward_multiplier(self, user: User, offer: Offer) -> Decimal:
        """
        Calculate reward multiplier for user and offer
        """
        multiplier = Decimal('1.0')
        
        # User level multiplier
        if hasattr(user, 'profile') and hasattr(user.profile, 'level'):
            level_multipliers = {
                'bronze': Decimal('1.0'),
                'silver': Decimal('1.1'),
                'gold': Decimal('1.2'),
                'platinum': Decimal('1.3'),
                'diamond': Decimal('1.5')
            }
            user_level = getattr(user.profile, 'level', 'bronze')
            multiplier *= level_multipliers.get(user_level, Decimal('1.0'))
        
        # Offer category multiplier
        category_multipliers = {
            'offerwall': Decimal('1.0'),
            'survey': Decimal('1.2'),
            'video': Decimal('0.8'),
            'gaming': Decimal('1.1'),
            'app_install': Decimal('1.5'),
            'cashback': Decimal('0.9')
        }
        if offer.category:
            multiplier *= category_multipliers.get(offer.category.slug, Decimal('1.0'))
        
        # Time-based multiplier (bonus hours)
        current_hour = timezone.now().hour
        if 19 <= current_hour <= 23:  # Evening bonus
            multiplier *= Decimal('1.1')
        elif 6 <= current_hour <= 9:   # Morning bonus
            multiplier *= Decimal('1.05')
        
        return multiplier
    
    def _calculate_bonus_amount(self, user: User, offer: Offer, 
                            base_reward: Decimal) -> Decimal:
        """
        Calculate bonus amount
        """
        bonus = Decimal('0.0')
        
        # First-time user bonus
        if hasattr(user, 'profile'):
            user_rewards_count = OfferReward.objects.filter(
                user=user,
                status=RewardStatus.APPROVED
            ).count()
            
            if user_rewards_count == 0:
                bonus += base_reward * Decimal('0.5')  # 50% first-time bonus
        
        # Offer-specific bonus
        if offer.is_new:
            bonus += base_reward * Decimal('0.1')  # 10% new offer bonus
        
        if offer.is_hot:
            bonus += base_reward * Decimal('0.15')  # 15% hot offer bonus
        
        # Referral bonus (if applicable)
        if hasattr(user, 'profile') and hasattr(user.profile, 'referred_by'):
            referral_bonus = base_reward * Decimal('0.05')  # 5% referral bonus
            bonus += referral_bonus
        
        return bonus
    
    def _apply_taxes_and_fees(self, amount: Decimal, offer: Offer) -> Decimal:
        """
        Apply taxes and fees to reward amount
        """
        net_amount = amount
        
        # Platform fee (usually 5-10%)
        platform_fee_rate = Decimal('0.05')  # 5%
        platform_fee = net_amount * platform_fee_rate
        net_amount -= platform_fee
        
        # Network fee (varies by network)
        if offer.ad_network and hasattr(offer.ad_network, 'commission_rate'):
            network_fee_rate = offer.ad_network.commission_rate / 100
            network_fee = net_amount * network_fee_rate
            net_amount -= network_fee
        
        # Payment processing fee (usually 2-3%)
        payment_fee_rate = Decimal('0.02')  # 2%
        payment_fee = net_amount * payment_fee_rate
        net_amount -= payment_fee
        
        return max(Decimal('0.0'), net_amount)  # Ensure non-negative
    
    def _get_tax_breakdown(self, gross_amount: Decimal, net_amount: Decimal) -> Dict:
        """
        Get tax and fee breakdown
        """
        total_fees = gross_amount - net_amount
        
        return {
            'gross_amount': float(gross_amount),
            'net_amount': float(net_amount),
            'total_fees': float(total_fees),
            'platform_fee': float(gross_amount * Decimal('0.05')),
            'network_fee': float(gross_amount * Decimal('0.10')),  # Estimated
            'payment_fee': float(gross_amount * Decimal('0.02')),
            'fee_rate': float((total_fees / gross_amount * 100) if gross_amount > 0 else 0)
        }
    
    def _check_daily_limit(self, user: User, offer: Offer, 
                          reward_amount: Decimal) -> Dict:
        """
        Check daily limit for user and offer
        """
        try:
            # Get or create daily limit record
            daily_limit, created = OfferDailyLimit.objects.get_or_create(
                user=user,
                offer=offer,
                defaults={
                    'count_today': 0,
                    'daily_limit': MAX_DAILY_OFFER_LIMIT,
                    'last_reset_at': timezone.now()
                }
            )
            
            # Reset if needed
            now = timezone.now()
            if daily_limit.last_reset_at.date() < now.date():
                daily_limit.count_today = 0
                daily_limit.last_reset_at = now
                daily_limit.save(update_fields=['count_today', 'last_reset_at'])
            
            # Check limit
            remaining = daily_limit.daily_limit - daily_limit.count_today
            
            return {
                'allowed': remaining > 0,
                'remaining': remaining,
                'reason': 'Daily limit exceeded' if remaining <= 0 else None
            }
            
        except Exception as e:
            logger.error(f"Daily limit check failed: {str(e)}")
            return {
                'allowed': True,
                'remaining': MAX_DAILY_OFFER_LIMIT,
                'reason': None
            }
    
    def _check_user_wallet(self, user: User, reward_amount: Decimal) -> Dict:
        """
        Check user wallet for limits
        """
        try:
            wallet = self._get_or_create_wallet(user)
            
            # Check maximum balance (anti-fraud)
            max_balance = Decimal('10000.00')  # $10,000 max balance
            if wallet.balance + reward_amount > max_balance:
                return {
                    'allowed': False,
                    'reason': 'Maximum wallet balance exceeded'
                }
            
            return {
                'allowed': True,
                'reason': None
            }
            
        except Exception as e:
            logger.error(f"Wallet check failed: {str(e)}")
            return {
                'allowed': True,
                'reason': None
            }
    
    def _get_or_create_wallet(self, user: User) -> UserWallet:
        """
        Get or create user wallet
        """
        wallet, created = UserWallet.objects.get_or_create(
            user=user,
            defaults={
                'balance': Decimal('0.00'),
                'total_earned': Decimal('0.00'),
                'total_withdrawn': Decimal('0.00'),
                'pending_rewards': Decimal('0.00'),
                'currency': 'USD'
            }
        )
        
        if created:
            logger.info(f"Created wallet for user {user.id}")
        
        return wallet
    
    def _get_or_create_wallet_by_id(self, user_id: int) -> UserWallet:
        """
        Get or create wallet by user ID
        """
        try:
            user = User.objects.get(id=user_id)
            return self._get_or_create_wallet(user)
        except User.DoesNotExist:
            raise ValueError(f"User with ID {user_id} not found")
    
    def _clear_user_caches(self, user: User):
        """
        Clear user-related caches
        """
        try:
            # Clear wallet cache
            cache.delete(f'user_{user.id}_wallet')
            
            # Clear rewards cache
            cache.delete(f'user_{user.id}_rewards')
            
            # Clear stats cache
            cache.delete(f'user_{user.id}_stats')
            
        except Exception as e:
            logger.error(f"Failed to clear user caches: {str(e)}")
    
    def _send_reward_notification(self, user: User, reward: OfferReward):
        """
        Send reward notification to user
        """
        try:
            # This would integrate with your notification system
            # For demo, we'll just log it
            logger.info(f"Reward notification sent to user {user.id}: {reward.amount} {reward.currency}")
            
            # You could send email, push notification, etc.
            # send_email_notification(user, 'reward_credited', {'reward': reward})
            # send_push_notification(user, 'reward_credited', {'amount': reward.amount})
            
        except Exception as e:
            logger.error(f"Failed to send reward notification: {str(e)}")
    
    def _send_reversal_notification(self, user: User, reward: OfferReward, reason: str):
        """
        Send reward reversal notification to user
        """
        try:
            # This would integrate with your notification system
            logger.info(f"Reward reversal notification sent to user {user.id}: {reward.amount} {reward.currency} - {reason}")
            
            # You could send email, push notification, etc.
            # send_email_notification(user, 'reward_reversed', {'reward': reward, 'reason': reason})
            # send_push_notification(user, 'reward_reversed', {'amount': reward.amount, 'reason': reason})
            
        except Exception as e:
            logger.error(f"Failed to send reversal notification: {str(e)}")
    
    @classmethod
    def process_pending_rewards(cls, limit: int = 100) -> Dict:
        """
        Process pending rewards (for batch processing)
        """
        try:
            with transaction.atomic():
                # Get pending rewards
                pending_rewards = OfferReward.objects.filter(
                    status=RewardStatus.PENDING
                ).select_related('user', 'offer')[:limit]
                
                processed_count = 0
                for reward in pending_rewards:
                    # Get user wallet
                    wallet, created = UserWallet.objects.get_or_create(
                        user=reward.user,
                        defaults={
                            'balance': Decimal('0.00'),
                            'total_earned': Decimal('0.00'),
                            'currency': 'USD'
                        }
                    )
                    
                    # Update wallet
                    wallet.balance += reward.amount
                    wallet.total_earned += reward.amount
                    wallet.last_activity = timezone.now()
                    wallet.save(update_fields=['balance', 'total_earned', 'last_activity'])
                    
                    # Update reward status
                    reward.status = RewardStatus.APPROVED
                    reward.approved_at = timezone.now()
                    reward.save(update_fields=['status', 'approved_at'])
                    
                    processed_count += 1
                
                logger.info(f"Processed {processed_count} pending rewards")
                
                return {
                    'success': True,
                    'processed_count': processed_count
                }
                
        except Exception as e:
            logger.error(f"Failed to process pending rewards: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
