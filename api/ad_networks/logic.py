"""
api/ad_networks/logic.py
Business logic for ad networks module
SaaS-ready with tenant support
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple, Union
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Sum, Avg, F, ExpressionWrapper, FloatField

from .models import (
    AdNetwork, Offer, UserOfferEngagement, OfferConversion,
    OfferReward, UserWallet, OfferClick, NetworkHealthCheck,
    OfferDailyLimit, KnownBadIP
)
from .choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus, DeviceType, Difficulty
)
from .constants import (
    FRAUD_SCORE_THRESHOLD, DEFAULT_DAILY_LIMIT,
    CACHE_TIMEOUTS, REWARD_MULTIPLIERS
)

logger = logging.getLogger(__name__)
User = get_user_model()


class OfferLogic:
    """Business logic for offers"""
    
    @staticmethod
    def get_available_offers(user=None, tenant_id='default', 
                           filters: Dict[str, Any] = None) -> List[Offer]:
        """Get available offers for user"""
        queryset = Offer.objects.filter(
            status=OfferStatus.ACTIVE,
            tenant_id=tenant_id
        )
        
        # Apply filters
        if filters:
            if 'category_id' in filters:
                queryset = queryset.filter(category_id=filters['category_id'])
            
            if 'network_id' in filters:
                queryset = queryset.filter(ad_network_id=filters['network_id'])
            
            if 'min_reward' in filters:
                queryset = queryset.filter(reward_amount__gte=filters['min_reward'])
            
            if 'max_reward' in filters:
                queryset = queryset.filter(reward_amount__lte=filters['max_reward'])
            
            if 'countries' in filters:
                queryset = queryset.filter(
                    Q(countries__contains=filters['countries']) |
                    Q(countries__isnull=True)
                )
            
            if 'platforms' in filters:
                queryset = queryset.filter(
                    Q(platforms__contains=filters['platforms']) |
                    Q(platforms__isnull=True)
                )
            
            if 'device_type' in filters:
                queryset = queryset.filter(
                    Q(device_type=filters['device_type']) |
                    Q(device_type='any')
                )
            
            if 'difficulty' in filters:
                queryset = queryset.filter(difficulty=filters['difficulty'])
        
        # Filter out expired offers
        queryset = queryset.filter(
            Q(expires_at__isnull=True) |
            Q(expires_at__gt=timezone.now())
        )
        
        # Order by priority and creation date
        queryset = queryset.order_by('-priority', '-created_at')
        
        return list(queryset)
    
    @staticmethod
    def can_user_access_offer(user: User, offer: Offer, 
                           tenant_id: str) -> Tuple[bool, List[str]]:
        """Check if user can access offer"""
        errors = []
        
        # Check if offer is active
        if offer.status != OfferStatus.ACTIVE:
            errors.append("Offer is not active")
        
        # Check if offer is expired
        if offer.expires_at and offer.expires_at < timezone.now():
            errors.append("Offer has expired")
        
        # Check daily limit
        if OfferLogic.has_reached_daily_limit(user, offer, tenant_id):
            errors.append("Daily limit exceeded")
        
        # Check if user has pending engagement
        if OfferLogic.has_pending_engagement(user, offer, tenant_id):
            errors.append("User has pending engagement for this offer")
        
        # Check user eligibility based on offer requirements
        if not OfferLogic.is_user_eligible(user, offer):
            errors.append("User is not eligible for this offer")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def has_reached_daily_limit(user: User, offer: Offer, 
                              tenant_id: str) -> bool:
        """Check if user has reached daily limit for offer"""
        try:
            daily_limit = OfferDailyLimit.objects.get(
                user=user,
                offer=offer,
                tenant_id=tenant_id
            )
            
            # Reset count if it's a new day
            if daily_limit.last_reset_at.date() < timezone.now().date():
                daily_limit.count_today = 0
                daily_limit.last_reset_at = timezone.now()
                daily_limit.save()
            
            return daily_limit.count_today >= daily_limit.daily_limit
            
        except OfferDailyLimit.DoesNotExist:
            # Create daily limit record
            OfferDailyLimit.objects.create(
                user=user,
                offer=offer,
                daily_limit=DEFAULT_DAILY_LIMIT,
                count_today=0,
                last_reset_at=timezone.now(),
                tenant_id=tenant_id
            )
            return False
    
    @staticmethod
    def has_pending_engagement(user: User, offer: Offer, 
                             tenant_id: str) -> bool:
        """Check if user has pending engagement for offer"""
        return UserOfferEngagement.objects.filter(
            user=user,
            offer=offer,
            status__in=[EngagementStatus.STARTED, EngagementStatus.VIEWED],
            tenant_id=tenant_id
        ).exists()
    
    @staticmethod
    def is_user_eligible(user: User, offer: Offer) -> bool:
        """Check if user is eligible for offer based on requirements"""
        # This would implement complex eligibility logic
        # For now, just return True
        return True
    
    @staticmethod
    def calculate_engagement_rate(offer: Offer, tenant_id: str,
                                days: int = 30) -> float:
        """Calculate engagement rate for offer"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        total_clicks = OfferClick.objects.filter(
            offer=offer,
            tenant_id=tenant_id,
            clicked_at__gte=cutoff_date
        ).count()
        
        total_engagements = UserOfferEngagement.objects.filter(
            offer=offer,
            tenant_id=tenant_id,
            created_at__gte=cutoff_date
        ).count()
        
        if total_clicks == 0:
            return 0.0
        
        return (total_engagements / total_clicks) * 100
    
    @staticmethod
    def calculate_conversion_rate(offer: Offer, tenant_id: str,
                                days: int = 30) -> float:
        """Calculate conversion rate for offer"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        total_engagements = UserOfferEngagement.objects.filter(
            offer=offer,
            tenant_id=tenant_id,
            created_at__gte=cutoff_date
        ).count()
        
        total_conversions = OfferConversion.objects.filter(
            engagement__offer=offer,
            tenant_id=tenant_id,
            created_at__gte=cutoff_date
        ).count()
        
        if total_engagements == 0:
            return 0.0
        
        return (total_conversions / total_engagements) * 100
    
    @staticmethod
    def get_offer_analytics(offer: Offer, tenant_id: str,
                          days: int = 30) -> Dict[str, Any]:
        """Get comprehensive offer analytics"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Click analytics
        clicks = OfferClick.objects.filter(
            offer=offer,
            tenant_id=tenant_id,
            clicked_at__gte=cutoff_date
        )
        
        total_clicks = clicks.count()
        unique_clicks = clicks.values('ip_address').distinct().count()
        
        # Engagement analytics
        engagements = UserOfferEngagement.objects.filter(
            offer=offer,
            tenant_id=tenant_id,
            created_at__gte=cutoff_date
        )
        
        total_engagements = engagements.count()
        completed_engagements = engagements.filter(
            status=EngagementStatus.COMPLETED
        ).count()
        
        # Conversion analytics
        conversions = OfferConversion.objects.filter(
            engagement__offer=offer,
            tenant_id=tenant_id,
            created_at__gte=cutoff_date
        )
        
        total_conversions = conversions.count()
        approved_conversions = conversions.filter(
            conversion_status=ConversionStatus.APPROVED
        ).count()
        
        total_payout = conversions.aggregate(
            total=Sum('payout')
        )['total'] or Decimal('0.00')
        
        # Calculate rates
        engagement_rate = (completed_engagements / total_clicks * 100) if total_clicks > 0 else 0
        conversion_rate = (approved_conversions / completed_engagements * 100) if completed_engagements > 0 else 0
        
        # Top countries
        top_countries = clicks.values('country').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Top devices
        top_devices = clicks.values('device').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return {
            'period_days': days,
            'clicks': {
                'total': total_clicks,
                'unique': unique_clicks
            },
            'engagements': {
                'total': total_engagements,
                'completed': completed_engagements,
                'rate': round(engagement_rate, 2)
            },
            'conversions': {
                'total': total_conversions,
                'approved': approved_conversions,
                'rate': round(conversion_rate, 2),
                'total_payout': float(total_payout)
            },
            'top_countries': list(top_countries),
            'top_devices': list(top_devices)
        }


class ConversionLogic:
    """Business logic for conversions"""
    
    @staticmethod
    def create_conversion(engagement: UserOfferEngagement, 
                        payout: Decimal, currency: str = 'USD',
                        conversion_data: Dict[str, Any] = None) -> OfferConversion:
        """Create a new conversion"""
        conversion = OfferConversion.objects.create(
            engagement=engagement,
            payout=payout,
            currency=currency,
            conversion_status=ConversionStatus.PENDING,
            conversion_data=conversion_data or {},
            tenant_id=engagement.tenant_id
        )
        
        # Calculate initial fraud score
        fraud_score = ConversionLogic.calculate_fraud_score(conversion)
        conversion.fraud_score = fraud_score
        conversion.save(update_fields=['fraud_score'])
        
        return conversion
    
    @staticmethod
    def calculate_fraud_score(conversion: OfferConversion) -> float:
        """Calculate fraud score for conversion"""
        score = 0.0
        indicators = []
        
        # Check completion time
        if conversion.engagement.started_at and conversion.engagement.completed_at:
            completion_time = conversion.engagement.completed_at - conversion.engagement.started_at
            if completion_time.total_seconds() < 60:  # Less than 1 minute
                score += 30
                indicators.append('suspiciously_fast_completion')
            elif completion_time.total_seconds() < 300:  # Less than 5 minutes
                score += 15
                indicators.append('fast_completion')
        
        # Check payout amount
        if conversion.payout > 100:
            score += 25
            indicators.append('high_payout_amount')
        elif conversion.payout > 50:
            score += 10
            indicators.append('moderate_payout_amount')
        
        # Check IP address
        if conversion.engagement.ip_address:
            if KnownBadIP.objects.filter(
                ip_address=conversion.engagement.ip_address,
                is_active=True
            ).exists():
                score += 50
                indicators.append('known_bad_ip')
        
        # Check user pattern
        user_conversions = OfferConversion.objects.filter(
            engagement__user=conversion.engagement.user,
            tenant_id=conversion.tenant_id,
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        if user_conversions > 20:
            score += 35
            indicators.append('high_conversion_velocity')
        elif user_conversions > 10:
            score += 20
            indicators.append('moderate_conversion_velocity')
        
        # Check offer pattern
        offer_conversions = OfferConversion.objects.filter(
            engagement__offer=conversion.engagement.offer,
            tenant_id=conversion.tenant_id,
            created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        
        if offer_conversions > 50:
            score += 25
            indicators.append('high_offer_conversion_rate')
        
        # Check time of day
        current_hour = timezone.now().hour
        if 2 <= current_hour <= 5:  # Unusual hours
            score += 15
            indicators.append('unusual_time')
        
        return min(score, 100.0)
    
    @staticmethod
    def approve_conversion(conversion: OfferConversion, 
                        approved_by: User = None,
                        notes: str = None) -> bool:
        """Approve a conversion"""
        try:
            with transaction.atomic():
                conversion.conversion_status = ConversionStatus.APPROVED
                conversion.approved_at = timezone.now()
                conversion.verification_notes = notes
                conversion.save(update_fields=[
                    'conversion_status', 'approved_at', 'verification_notes'
                ])
                
                # Create reward
                RewardLogic.create_reward(
                    conversion.engagement.user,
                    conversion.engagement.offer,
                    conversion.payout,
                    conversion.currency,
                    engagement=conversion.engagement,
                    tenant_id=conversion.tenant_id
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error approving conversion {conversion.id}: {str(e)}")
            return False
    
    @staticmethod
    def reject_conversion(conversion: OfferConversion, 
                        rejected_by: User = None,
                        reason: str = None) -> bool:
        """Reject a conversion"""
        try:
            conversion.conversion_status = ConversionStatus.REJECTED
            conversion.rejected_at = timezone.now()
            conversion.rejection_reason = reason
            conversion.save(update_fields=[
                'conversion_status', 'rejected_at', 'rejection_reason'
            ])
            
            return True
            
        except Exception as e:
            logger.error(f"Error rejecting conversion {conversion.id}: {str(e)}")
            return False
    
    @staticmethod
    def process_chargeback(conversion: OfferConversion, 
                         reason: str = None) -> bool:
        """Process chargeback for conversion"""
        try:
            with transaction.atomic():
                conversion.conversion_status = ConversionStatus.CHARGEBACK
                conversion.chargeback_at = timezone.now()
                conversion.save(update_fields=[
                    'conversion_status', 'chargeback_at'
                ])
                
                # Reverse reward if exists
                try:
                    reward = OfferReward.objects.get(
                        engagement=conversion.engagement,
                        tenant_id=conversion.tenant_id
                    )
                    RewardLogic.reverse_reward(reward, reason or 'Chargeback processed')
                except OfferReward.DoesNotExist:
                    pass
                
                return True
                
        except Exception as e:
            logger.error(f"Error processing chargeback for conversion {conversion.id}: {str(e)}")
            return False


class RewardLogic:
    """Business logic for rewards"""
    
    @staticmethod
    def create_reward(user: User, offer: Offer, amount: Decimal,
                     currency: str = 'USD', engagement: UserOfferEngagement = None,
                     tenant_id: str = 'default') -> OfferReward:
        """Create a new reward"""
        # Apply user multipliers
        final_amount = RewardLogic.calculate_final_reward_amount(
            user, amount, offer, tenant_id
        )
        
        reward = OfferReward.objects.create(
            user=user,
            offer=offer,
            engagement=engagement,
            amount=final_amount,
            currency=currency,
            status=RewardStatus.PENDING,
            tenant_id=tenant_id
        )
        
        return reward
    
    @staticmethod
    def calculate_final_reward_amount(user: User, base_amount: Decimal,
                                    offer: Offer, tenant_id: str) -> Decimal:
        """Calculate final reward amount with multipliers"""
        final_amount = base_amount
        
        # Apply loyalty multiplier
        loyalty_multiplier = RewardLogic.get_loyalty_multiplier(user, tenant_id)
        final_amount *= loyalty_multiplier
        
        # Apply offer multiplier
        if offer.is_featured:
            final_amount *= REWARD_MULTIPLIERS.get('featured', 1.0)
        
        if offer.is_hot:
            final_amount *= REWARD_MULTIPLIERS.get('hot', 1.0)
        
        # Apply user-specific multiplier
        user_multiplier = RewardLogic.get_user_multiplier(user, tenant_id)
        final_amount *= user_multiplier
        
        return final_amount.quantize(Decimal('0.01'))
    
    @staticmethod
    def get_loyalty_multiplier(user: User, tenant_id: str) -> Decimal:
        """Get loyalty multiplier for user"""
        # This would calculate based on user's history
        # For now, return default
        return Decimal(str(REWARD_MULTIPLIERS.get('loyalty', 1.0)))
    
    @staticmethod
    def get_user_multiplier(user: User, tenant_id: str) -> Decimal:
        """Get user-specific multiplier"""
        # This would calculate based on user's profile
        # For now, return default
        return Decimal(str(REWARD_MULTIPLIERS.get('user_default', 1.0)))
    
    @staticmethod
    def approve_reward(reward: OfferReward, 
                     approved_by: User = None) -> bool:
        """Approve a reward"""
        try:
            with transaction.atomic():
                reward.status = RewardStatus.APPROVED
                reward.approved_at = timezone.now()
                reward.save(update_fields=['status', 'approved_at'])
                
                # Credit user wallet
                RewardLogic.credit_user_wallet(
                    reward.user, reward.amount, reward.currency,
                    reward.tenant_id
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error approving reward {reward.id}: {str(e)}")
            return False
    
    @staticmethod
    def credit_user_wallet(user: User, amount: Decimal, currency: str,
                          tenant_id: str) -> bool:
        """Credit amount to user wallet"""
        try:
            wallet, created = UserWallet.objects.get_or_create(
                user=user,
                defaults={
                    'balance': Decimal('0.00'),
                    'total_earned': Decimal('0.00'),
                    'currency': currency,
                    'tenant_id': tenant_id
                }
            )
            
            wallet.balance += amount
            wallet.total_earned += amount
            wallet.save(update_fields=['balance', 'total_earned'])
            
            return True
            
        except Exception as e:
            logger.error(f"Error crediting wallet for user {user.id}: {str(e)}")
            return False
    
    @staticmethod
    def reverse_reward(reward: OfferReward, reason: str = None) -> bool:
        """Reverse a reward"""
        try:
            with transaction.atomic():
                reward.status = RewardStatus.CANCELLED
                reward.cancellation_reason = reason
                reward.cancelled_at = timezone.now()
                reward.save(update_fields=[
                    'status', 'cancellation_reason', 'cancelled_at'
                ])
                
                # Debit user wallet
                try:
                    wallet = UserWallet.objects.get(
                        user=reward.user,
                        currency=reward.currency,
                        tenant_id=reward.tenant_id
                    )
                    wallet.balance -= reward.amount
                    wallet.save(update_fields=['balance'])
                except UserWallet.DoesNotExist:
                    pass
                
                return True
                
        except Exception as e:
            logger.error(f"Error reversing reward {reward.id}: {str(e)}")
            return False


class UserLogic:
    """Business logic for user operations"""
    
    @staticmethod
    def get_user_stats(user: User, tenant_id: str,
                      days: int = 30) -> Dict[str, Any]:
        """Get comprehensive user statistics"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Engagement stats
        engagements = UserOfferEngagement.objects.filter(
            user=user,
            tenant_id=tenant_id,
            created_at__gte=cutoff_date
        )
        
        total_engagements = engagements.count()
        completed_engagements = engagements.filter(
            status=EngagementStatus.COMPLETED
        ).count()
        
        # Conversion stats
        conversions = OfferConversion.objects.filter(
            engagement__user=user,
            tenant_id=tenant_id,
            created_at__gte=cutoff_date
        )
        
        total_conversions = conversions.count()
        approved_conversions = conversions.filter(
            conversion_status=ConversionStatus.APPROVED
        ).count()
        
        # Reward stats
        rewards = OfferReward.objects.filter(
            user=user,
            tenant_id=tenant_id,
            created_at__gte=cutoff_date
        )
        
        total_rewards = rewards.count()
        approved_rewards = rewards.filter(
            status=RewardStatus.APPROVED
        ).count()
        
        total_earned = rewards.filter(
            status=RewardStatus.APPROVED
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Calculate rates
        engagement_rate = (completed_engagements / total_engagements * 100) if total_engagements > 0 else 0
        conversion_rate = (approved_conversions / completed_engagements * 100) if completed_engagements > 0 else 0
        
        # Wallet info
        try:
            wallet = UserWallet.objects.get(
                user=user,
                tenant_id=tenant_id
            )
            wallet_balance = float(wallet.balance)
        except UserWallet.DoesNotExist:
            wallet_balance = 0.0
        
        return {
            'period_days': days,
            'engagements': {
                'total': total_engagements,
                'completed': completed_engagements,
                'rate': round(engagement_rate, 2)
            },
            'conversions': {
                'total': total_conversions,
                'approved': approved_conversions,
                'rate': round(conversion_rate, 2)
            },
            'rewards': {
                'total': total_rewards,
                'approved': approved_rewards,
                'total_earned': float(total_earned)
            },
            'wallet': {
                'balance': wallet_balance
            }
        }
    
    @staticmethod
    def get_user_preferences(user: User, tenant_id: str) -> Dict[str, Any]:
        """Get user preferences"""
        # This would get from user profile
        # For now, return defaults
        return {
            'preferred_categories': [],
            'preferred_networks': [],
            'preferred_difficulty': 'easy',
            'notification_settings': {
                'email': True,
                'push': True,
                'sms': False
            },
            'privacy_settings': {
                'share_analytics': True,
                'allow_tracking': True
            }
        }
    
    @staticmethod
    def update_user_preferences(user: User, preferences: Dict[str, Any],
                              tenant_id: str) -> bool:
        """Update user preferences"""
        try:
            # This would update user profile
            # For now, just log
            logger.info(f"Updated preferences for user {user.id}: {preferences}")
            return True
        except Exception as e:
            logger.error(f"Error updating preferences for user {user.id}: {str(e)}")
            return False


class NetworkLogic:
    """Business logic for network operations"""
    
    @staticmethod
    def get_network_stats(network: AdNetwork, tenant_id: str,
                        days: int = 30) -> Dict[str, Any]:
        """Get comprehensive network statistics"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Offer stats
        offers = Offer.objects.filter(
            ad_network=network,
            tenant_id=tenant_id
        )
        
        total_offers = offers.count()
        active_offers = offers.filter(status=OfferStatus.ACTIVE).count()
        
        # Conversion stats
        conversions = OfferConversion.objects.filter(
            engagement__offer__ad_network=network,
            tenant_id=tenant_id,
            created_at__gte=cutoff_date
        )
        
        total_conversions = conversions.count()
        approved_conversions = conversions.filter(
            conversion_status=ConversionStatus.APPROVED
        ).count()
        
        total_payout = conversions.aggregate(
            total=Sum('payout')
        )['total'] or Decimal('0.00')
        
        # Health stats
        health_checks = NetworkHealthCheck.objects.filter(
            network=network,
            tenant_id=tenant_id,
            checked_at__gte=cutoff_date
        )
        
        total_checks = health_checks.count()
        healthy_checks = health_checks.filter(is_healthy=True).count()
        uptime_percentage = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
        
        # Performance metrics
        avg_response_time = health_checks.aggregate(
            avg=Avg('response_time_ms')
        )['avg'] or 0
        
        return {
            'period_days': days,
            'offers': {
                'total': total_offers,
                'active': active_offers
            },
            'conversions': {
                'total': total_conversions,
                'approved': approved_conversions,
                'total_payout': float(total_payout)
            },
            'health': {
                'total_checks': total_checks,
                'healthy_checks': healthy_checks,
                'uptime_percentage': round(uptime_percentage, 2),
                'avg_response_time_ms': round(avg_response_time, 2)
            }
        }
    
    @staticmethod
    def is_network_healthy(network: AdNetwork, tenant_id: str) -> bool:
        """Check if network is healthy"""
        try:
            latest_check = NetworkHealthCheck.objects.filter(
                network=network,
                tenant_id=tenant_id
            ).order_by('-checked_at').first()
            
            if not latest_check:
                return False
            
            # Consider healthy if last check was within 24 hours and was successful
            cutoff_time = timezone.now() - timedelta(hours=24)
            return (latest_check.checked_at >= cutoff_time and 
                   latest_check.is_healthy)
            
        except Exception as e:
            logger.error(f"Error checking network health: {str(e)}")
            return False


class AnalyticsLogic:
    """Business logic for analytics operations"""
    
    @staticmethod
    def get_dashboard_stats(tenant_id: str, days: int = 30) -> Dict[str, Any]:
        """Get dashboard statistics"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Overall stats
        total_offers = Offer.objects.filter(
            tenant_id=tenant_id,
            status=OfferStatus.ACTIVE
        ).count()
        
        total_conversions = OfferConversion.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=cutoff_date
        ).count()
        
        total_payout = OfferConversion.objects.filter(
            tenant_id=tenant_id,
            conversion_status=ConversionStatus.APPROVED,
            created_at__gte=cutoff_date
        ).aggregate(
            total=Sum('payout')
        )['total'] or Decimal('0.00')
        
        total_users = User.objects.filter(
            userofferengagement__tenant_id=tenant_id,
            userofferengagement__created_at__gte=cutoff_date
        ).distinct().count()
        
        # Network stats
        network_stats = AdNetwork.objects.filter(
            tenant_id=tenant_id,
            is_active=True
        ).count()
        
        # Health stats
        healthy_networks = 0
        for network in AdNetwork.objects.filter(tenant_id=tenant_id, is_active=True):
            if NetworkLogic.is_network_healthy(network, tenant_id):
                healthy_networks += 1
        
        return {
            'period_days': days,
            'offers': {
                'total_active': total_offers
            },
            'conversions': {
                'total': total_conversions,
                'total_payout': float(total_payout)
            },
            'users': {
                'total_active': total_users
            },
            'networks': {
                'total_active': network_stats,
                'healthy': healthy_networks
            }
        }
    
    @staticmethod
    def get_trending_offers(tenant_id: str, days: int = 7, 
                          limit: int = 10) -> List[Dict[str, Any]]:
        """Get trending offers"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        offers = Offer.objects.filter(
            tenant_id=tenant_id,
            status=OfferStatus.ACTIVE
        ).annotate(
            recent_conversions=Count(
                'userofferengagement__offerconversion',
                filter=Q(
                    userofferengagement__offerconversion__created_at__gte=cutoff_date,
                    userofferengagement__offerconversion__conversion_status=ConversionStatus.APPROVED
                )
            )
        ).order_by('-recent_conversions')[:limit]
        
        trending = []
        for offer in offers:
            trending.append({
                'id': offer.id,
                'title': offer.title,
                'reward_amount': float(offer.reward_amount),
                'recent_conversions': offer.recent_conversions,
                'conversion_rate': OfferLogic.calculate_conversion_rate(offer, tenant_id, days)
            })
        
        return trending
    
    @staticmethod
    def get_top_users(tenant_id: str, days: int = 30, 
                     limit: int = 10) -> List[Dict[str, Any]]:
        """Get top users by earnings"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        users = User.objects.annotate(
            total_earned=Sum(
                'offerreward__amount',
                filter=Q(
                    offerreward__tenant_id=tenant_id,
                    offerreward__status=RewardStatus.APPROVED,
                    offerreward__created_at__gte=cutoff_date
                )
            )
        ).filter(
            total_earned__isnull=False
        ).order_by('-total_earned')[:limit]
        
        top_users = []
        for user in users:
            top_users.append({
                'id': user.id,
                'username': user.username,
                'total_earned': float(user.total_earned),
                'conversions': OfferConversion.objects.filter(
                    engagement__user=user,
                    tenant_id=tenant_id,
                    conversion_status=ConversionStatus.APPROVED,
                    created_at__gte=cutoff_date
                ).count()
            })
        
        return top_users


# Export all logic classes
__all__ = [
    'OfferLogic',
    'ConversionLogic',
    'RewardLogic',
    'UserLogic',
    'NetworkLogic',
    'AnalyticsLogic'
]
