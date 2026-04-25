"""
api/ad_networks/analytics.py
Analytics and reporting for ad networks module
SaaS-ready with tenant support
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union, Tuple
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Sum, Avg, F, ExpressionWrapper, FloatField, Case, When
from django.core.cache import cache
from django.db.models.functions import TruncDate, TruncHour, TruncDay, TruncWeek, TruncMonth

from .models import (
    AdNetwork, Offer, OfferCategory, UserOfferEngagement,
    OfferConversion, OfferReward, UserWallet, OfferClick,
    OfferTag, OfferTagging, NetworkAPILog
)
from .choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus
)
from .constants import FRAUD_SCORE_THRESHOLD, CACHE_TIMEOUTS
from .helpers import get_cache_key, calculate_percentage

logger = logging.getLogger(__name__)
User = get_user_model()


# ==================== ANALYTICS PERIODS ====================

class AnalyticsPeriod:
    """Analytics time periods"""
    
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    THIS_YEAR = "this_year"
    LAST_YEAR = "last_year"
    CUSTOM = "custom"


# ==================== BASE ANALYTICS ====================

class BaseAnalytics:
    """Base analytics class with common functionality"""
    
    def __init__(self, tenant_id: str = 'default'):
        self.tenant_id = tenant_id
        self.cache_timeout = CACHE_TIMEOUTS.get('analytics', 1800)  # 30 minutes
    
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
    
    def _get_date_range(self, period: str, start_date: datetime = None, 
                       end_date: datetime = None) -> Tuple[datetime, datetime]:
        """Get date range for period"""
        now = timezone.now()
        
        if period == AnalyticsPeriod.TODAY:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif period == AnalyticsPeriod.YESTERDAY:
            yesterday = now - timedelta(days=1)
            start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == AnalyticsPeriod.LAST_7_DAYS:
            start_date = now - timedelta(days=7)
            end_date = now
        elif period == AnalyticsPeriod.LAST_30_DAYS:
            start_date = now - timedelta(days=30)
            end_date = now
        elif period == AnalyticsPeriod.LAST_90_DAYS:
            start_date = now - timedelta(days=90)
            end_date = now
        elif period == AnalyticsPeriod.THIS_MONTH:
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif period == AnalyticsPeriod.LAST_MONTH:
            last_month = now.replace(day=1) - timedelta(days=1)
            start_date = last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = last_month.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == AnalyticsPeriod.THIS_YEAR:
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif period == AnalyticsPeriod.LAST_YEAR:
            last_year = now.replace(year=now.year - 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            start_date = last_year
            end_date = last_year.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
        elif period == AnalyticsPeriod.CUSTOM:
            if not start_date or not end_date:
                raise ValueError("Custom period requires start_date and end_date")
        else:
            raise ValueError(f"Unknown period: {period}")
        
        return start_date, end_date


# ==================== OFFER ANALYTICS ====================

class OfferAnalytics(BaseAnalytics):
    """Analytics for offers"""
    
    def get_offer_performance(self, offer_id: int, period: str = AnalyticsPeriod.LAST_30_DAYS) -> Dict[str, Any]:
        """Get offer performance analytics"""
        cache_key = self._get_cache_key('offer_performance', offer_id, period)
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        start_date, end_date = self._get_date_range(period)
        
        try:
            # Get offer
            offer = Offer.objects.get(id=offer_id, tenant_id=self.tenant_id)
            
            # Get engagement metrics
            engagements = UserOfferEngagement.objects.filter(
                tenant_id=self.tenant_id,
                offer=offer,
                created_at__range=[start_date, end_date]
            )
            
            total_engagements = engagements.count()
            completed_engagements = engagements.filter(status=EngagementStatus.COMPLETED).count()
            in_progress_engagements = engagements.filter(status=EngagementStatus.IN_PROGRESS).count()
            
            # Get conversion metrics
            conversions = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                engagement__offer=offer,
                created_at__range=[start_date, end_date]
            )
            
            total_conversions = conversions.count()
            approved_conversions = conversions.filter(status=ConversionStatus.APPROVED).count()
            rejected_conversions = conversions.filter(status=ConversionStatus.REJECTED).count()
            fraudulent_conversions = conversions.filter(is_fraud=True).count()
            
            # Calculate metrics
            completion_rate = calculate_percentage(completed_engagements, total_engagements)
            conversion_rate = calculate_percentage(approved_conversions, total_engagements)
            fraud_rate = calculate_percentage(fraudulent_conversions, total_conversions)
            
            # Revenue metrics
            total_revenue = conversions.filter(status=ConversionStatus.APPROVED).aggregate(
                total=Sum('payout')
            )['total'] or 0
            
            avg_revenue = approved_conversions > 0 and (total_revenue / approved_conversions) or 0
            
            # Time analytics
            avg_completion_time = engagements.filter(
                status=EngagementStatus.COMPLETED,
                completed_at__isnull=False
            ).aggregate(
                avg_time=Avg(
                    ExpressionWrapper(
                        (F('completed_at') - F('started_at')).total_seconds() / 60,
                        output_field=FloatField()
                    )
                )
            )['avg_time'] or 0
            
            # Daily breakdown
            daily_stats = self._get_offer_daily_stats(offer_id, start_date, end_date)
            
            analytics_data = {
                'offer_id': offer_id,
                'offer_title': offer.title,
                'period': period,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                },
                'engagements': {
                    'total': total_engagements,
                    'completed': completed_engagements,
                    'in_progress': in_progress_engagements,
                    'completion_rate': completion_rate,
                },
                'conversions': {
                    'total': total_conversions,
                    'approved': approved_conversions,
                    'rejected': rejected_conversions,
                    'fraudulent': fraudulent_conversions,
                    'conversion_rate': conversion_rate,
                    'fraud_rate': fraud_rate,
                },
                'revenue': {
                    'total': float(total_revenue),
                    'average': float(avg_revenue),
                },
                'time': {
                    'average_completion_minutes': avg_completion_time,
                },
                'daily_breakdown': daily_stats,
            }
            
            self._set_cache(cache_key, analytics_data)
            return analytics_data
            
        except Offer.DoesNotExist:
            return {'error': 'Offer not found'}
        except Exception as e:
            logger.error(f"Error getting offer performance: {str(e)}")
            return {'error': str(e)}
    
    def _get_offer_daily_stats(self, offer_id: int, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get daily statistics for offer"""
        daily_stats = []
        
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            day_start = timezone.make_aware(datetime.combine(current_date, datetime.min.time()))
            day_end = day_start + timedelta(days=1)
            
            # Get day's metrics
            engagements = UserOfferEngagement.objects.filter(
                tenant_id=self.tenant_id,
                offer_id=offer_id,
                created_at__range=[day_start, day_end]
            )
            
            conversions = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                engagement__offer_id=offer_id,
                created_at__range=[day_start, day_end]
            )
            
            day_stats = {
                'date': current_date.isoformat(),
                'engagements': {
                    'total': engagements.count(),
                    'completed': engagements.filter(status=EngagementStatus.COMPLETED).count(),
                },
                'conversions': {
                    'total': conversions.count(),
                    'approved': conversions.filter(status=ConversionStatus.APPROVED).count(),
                },
                'revenue': float(conversions.filter(status=ConversionStatus.APPROVED).aggregate(
                    total=Sum('payout')
                )['total'] or 0),
            }
            
            daily_stats.append(day_stats)
            current_date += timedelta(days=1)
        
        return daily_stats
    
    def get_top_performing_offers(self, period: str = AnalyticsPeriod.LAST_30_DAYS, 
                                limit: int = 10) -> List[Dict[str, Any]]:
        """Get top performing offers"""
        cache_key = self._get_cache_key('top_offers', period, limit)
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        start_date, end_date = self._get_date_range(period)
        
        try:
            offers = Offer.objects.filter(
                tenant_id=self.tenant_id,
                status=OfferStatus.ACTIVE
            ).annotate(
                total_conversions=Count(
                    'userofferengagement__offerconversion',
                    filter=Q(
                        userofferengagement__offerconversion__created_at__range=[start_date, end_date],
                        userofferengagement__offerconversion__status=ConversionStatus.APPROVED
                    )
                ),
                total_revenue=Sum(
                    'userofferengagement__offerconversion__payout',
                    filter=Q(
                        userofferengagement__offerconversion__created_at__range=[start_date, end_date],
                        userofferengagement__offerconversion__status=ConversionStatus.APPROVED
                    )
                ),
                conversion_rate=ExpressionWrapper(
                    Case(
                        When(
                            total_conversions__gt=0,
                            then=(F('total_conversions') * 100.0) / Count('userofferengagement')
                        ),
                        default=0,
                        output_field=FloatField()
                    )
                )
            ).order_by('-total_revenue')[:limit]
            
            top_offers = []
            for offer in offers:
                top_offers.append({
                    'id': offer.id,
                    'title': offer.title,
                    'category': offer.category.name if offer.category else None,
                    'total_conversions': offer.total_conversions or 0,
                    'total_revenue': float(offer.total_revenue or 0),
                    'conversion_rate': float(offer.conversion_rate or 0),
                    'performance_score': offer.performance_score,
                })
            
            self._set_cache(cache_key, top_offers)
            return top_offers
            
        except Exception as e:
            logger.error(f"Error getting top performing offers: {str(e)}")
            return []
    
    def get_category_analytics(self, period: str = AnalyticsPeriod.LAST_30_DAYS) -> List[Dict[str, Any]]:
        """Get analytics by offer category"""
        cache_key = self._get_cache_key('category_analytics', period)
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        start_date, end_date = self._get_date_range(period)
        
        try:
            categories = OfferCategory.objects.annotate(
                total_offers=Count(
                    'offer',
                    filter=Q(
                        offer__tenant_id=self.tenant_id,
                        offer__status=OfferStatus.ACTIVE
                    )
                ),
                total_conversions=Count(
                    'offer__userofferengagement__offerconversion',
                    filter=Q(
                        offer__tenant_id=self.tenant_id,
                        offer__userofferengagement__offerconversion__created_at__range=[start_date, end_date],
                        offer__userofferengagement__offerconversion__status=ConversionStatus.APPROVED
                    )
                ),
                total_revenue=Sum(
                    'offer__userofferengagement__offerconversion__payout',
                    filter=Q(
                        offer__tenant_id=self.tenant_id,
                        offer__userofferengagement__offerconversion__created_at__range=[start_date, end_date],
                        offer__userofferengagement__offerconversion__status=ConversionStatus.APPROVED
                    )
                )
            ).filter(total_offers__gt=0).order_by('-total_revenue')
            
            category_analytics = []
            for category in categories:
                category_analytics.append({
                    'id': category.id,
                    'name': category.name,
                    'total_offers': category.total_offers,
                    'total_conversions': category.total_conversions or 0,
                    'total_revenue': float(category.total_revenue or 0),
                    'avg_revenue_per_offer': float(
                        (category.total_revenue or 0) / category.total_offers
                        if category.total_offers > 0 else 0
                    ),
                })
            
            self._set_cache(cache_key, category_analytics)
            return category_analytics
            
        except Exception as e:
            logger.error(f"Error getting category analytics: {str(e)}")
            return []


# ==================== USER ANALYTICS ====================

class UserAnalytics(BaseAnalytics):
    """Analytics for users"""
    
    def get_user_analytics(self, user_id: int, period: str = AnalyticsPeriod.LAST_30_DAYS) -> Dict[str, Any]:
        """Get user analytics"""
        cache_key = self._get_cache_key('user_analytics', user_id, period)
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        start_date, end_date = self._get_date_range(period)
        
        try:
            # Get user
            user = User.objects.get(id=user_id)
            
            # Engagement metrics
            engagements = UserOfferEngagement.objects.filter(
                tenant_id=self.tenant_id,
                user=user,
                created_at__range=[start_date, end_date]
            )
            
            total_engagements = engagements.count()
            completed_engagements = engagements.filter(status=EngagementStatus.COMPLETED).count()
            
            # Conversion metrics
            conversions = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                engagement__user=user,
                created_at__range=[start_date, end_date]
            )
            
            total_conversions = conversions.count()
            approved_conversions = conversions.filter(status=ConversionStatus.APPROVED).count()
            
            # Reward metrics
            rewards = OfferReward.objects.filter(
                tenant_id=self.tenant_id,
                user=user,
                created_at__range=[start_date, end_date]
            )
            
            total_rewards = rewards.count()
            approved_rewards = rewards.filter(status=RewardStatus.APPROVED).count()
            paid_rewards = rewards.filter(status=RewardStatus.PAID).count()
            
            # Revenue metrics
            total_earned = rewards.filter(status=RewardStatus.APPROVED).aggregate(
                total=Sum('amount')
            )['total'] or 0
            
            # Wallet metrics
            try:
                wallet = UserWallet.objects.get(user=user, tenant_id=self.tenant_id)
                wallet_balance = wallet.current_balance
                pending_balance = wallet.pending_balance
            except UserWallet.DoesNotExist:
                wallet_balance = 0
                pending_balance = 0
            
            # Calculate rates
            completion_rate = calculate_percentage(completed_engagements, total_engagements)
            conversion_rate = calculate_percentage(approved_conversions, total_engagements)
            approval_rate = calculate_percentage(approved_rewards, total_rewards)
            
            analytics_data = {
                'user_id': user_id,
                'username': user.username,
                'period': period,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                },
                'engagements': {
                    'total': total_engagements,
                    'completed': completed_engagements,
                    'completion_rate': completion_rate,
                },
                'conversions': {
                    'total': total_conversions,
                    'approved': approved_conversions,
                    'conversion_rate': conversion_rate,
                },
                'rewards': {
                    'total': total_rewards,
                    'approved': approved_rewards,
                    'paid': paid_rewards,
                    'approval_rate': approval_rate,
                },
                'revenue': {
                    'total_earned': float(total_earned),
                    'average_per_conversion': float(
                        total_earned / approved_conversions
                        if approved_conversions > 0 else 0
                    ),
                },
                'wallet': {
                    'current_balance': float(wallet_balance),
                    'pending_balance': float(pending_balance),
                },
            }
            
            self._set_cache(cache_key, analytics_data)
            return analytics_data
            
        except User.DoesNotExist:
            return {'error': 'User not found'}
        except Exception as e:
            logger.error(f"Error getting user analytics: {str(e)}")
            return {'error': str(e)}
    
    def get_top_users(self, period: str = AnalyticsPeriod.LAST_30_DAYS, 
                     metric: str = 'revenue', limit: int = 10) -> List[Dict[str, Any]]:
        """Get top users by metric"""
        cache_key = self._get_cache_key('top_users', period, metric, limit)
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        start_date, end_date = self._get_date_range(period)
        
        try:
            if metric == 'revenue':
                # Top users by revenue
                users = User.objects.annotate(
                    total_revenue=Sum(
                        'offerreward__amount',
                        filter=Q(
                            offerreward__tenant_id=self.tenant_id,
                            offerreward__created_at__range=[start_date, end_date],
                            offerreward__status=RewardStatus.APPROVED
                        )
                    )
                ).filter(total_revenue__gt=0).order_by('-total_revenue')[:limit]
                
                top_users = []
                for user in users:
                    top_users.append({
                        'id': user.id,
                        'username': user.username,
                        'total_revenue': float(user.total_revenue or 0),
                    })
                
            elif metric == 'conversions':
                # Top users by conversions
                users = User.objects.annotate(
                    total_conversions=Count(
                        'userofferengagement__offerconversion',
                        filter=Q(
                            userofferengagement__offerconversion__tenant_id=self.tenant_id,
                            userofferengagement__offerconversion__created_at__range=[start_date, end_date],
                            userofferengagement__offerconversion__status=ConversionStatus.APPROVED
                        )
                    )
                ).filter(total_conversions__gt=0).order_by('-total_conversions')[:limit]
                
                top_users = []
                for user in users:
                    top_users.append({
                        'id': user.id,
                        'username': user.username,
                        'total_conversions': user.total_conversions or 0,
                    })
                
            else:
                top_users = []
            
            self._set_cache(cache_key, top_users)
            return top_users
            
        except Exception as e:
            logger.error(f"Error getting top users: {str(e)}")
            return []
    
    def get_user_retention_analytics(self, period: str = AnalyticsPeriod.LAST_30_DAYS) -> Dict[str, Any]:
        """Get user retention analytics"""
        cache_key = self._get_cache_key('user_retention', period)
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        start_date, end_date = self._get_date_range(period)
        
        try:
            # Get users who joined in the period
            new_users = User.objects.filter(
                date_joined__range=[start_date, end_date]
            )
            
            total_new_users = new_users.count()
            
            if total_new_users == 0:
                return {
                    'period': period,
                    'total_new_users': 0,
                    'retention_rate': 0,
                    'retention_breakdown': [],
                }
            
            # Calculate retention by checking if users had any activity
            retained_users = 0
            retention_breakdown = []
            
            for days in [1, 7, 14, 30]:
                if days > (end_date - start_date).days:
                    continue
                
                cutoff_date = start_date + timedelta(days=days)
                active_users = new_users.filter(
                    userofferengagement__created_at__gte=cutoff_date
                ).distinct().count()
                
                retention_rate = calculate_percentage(active_users, total_new_users)
                
                retention_breakdown.append({
                    'days': days,
                    'active_users': active_users,
                    'retention_rate': retention_rate,
                })
                
                if days == 30:
                    retained_users = active_users
            
            overall_retention_rate = calculate_percentage(retained_users, total_new_users)
            
            retention_data = {
                'period': period,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                },
                'total_new_users': total_new_users,
                'retained_users': retained_users,
                'retention_rate': overall_retention_rate,
                'retention_breakdown': retention_breakdown,
            }
            
            self._set_cache(cache_key, retention_data)
            return retention_data
            
        except Exception as e:
            logger.error(f"Error getting user retention analytics: {str(e)}")
            return {'error': str(e)}


# ==================== REVENUE ANALYTICS ====================

class RevenueAnalytics(BaseAnalytics):
    """Analytics for revenue"""
    
    def get_revenue_analytics(self, period: str = AnalyticsPeriod.LAST_30_DAYS) -> Dict[str, Any]:
        """Get revenue analytics"""
        cache_key = self._get_cache_key('revenue_analytics', period)
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        start_date, end_date = self._get_date_range(period)
        
        try:
            # Total revenue
            total_revenue = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                created_at__range=[start_date, end_date],
                status=ConversionStatus.APPROVED
            ).aggregate(total=Sum('payout'))['total'] or 0
            
            # Revenue by day
            daily_revenue = self._get_daily_revenue(start_date, end_date)
            
            # Revenue by category
            category_revenue = self._get_revenue_by_category(start_date, end_date)
            
            # Revenue by network
            network_revenue = self._get_revenue_by_network(start_date, end_date)
            
            # Average revenue metrics
            total_conversions = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                created_at__range=[start_date, end_date],
                status=ConversionStatus.APPROVED
            ).count()
            
            avg_revenue_per_conversion = float(
                total_revenue / total_conversions
                if total_conversions > 0 else 0
            )
            
            # Revenue growth (compare with previous period)
            previous_start = start_date - timedelta(days=(end_date - start_date).days)
            previous_end = start_date
            
            previous_revenue = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                created_at__range=[previous_start, previous_end],
                status=ConversionStatus.APPROVED
            ).aggregate(total=Sum('payout'))['total'] or 0
            
            revenue_growth = calculate_percentage(
                (total_revenue - previous_revenue),
                previous_revenue
            ) if previous_revenue > 0 else 0
            
            revenue_data = {
                'period': period,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                },
                'total_revenue': float(total_revenue),
                'total_conversions': total_conversions,
                'avg_revenue_per_conversion': avg_revenue_per_conversion,
                'revenue_growth': revenue_growth,
                'daily_revenue': daily_revenue,
                'category_breakdown': category_revenue,
                'network_breakdown': network_revenue,
            }
            
            self._set_cache(cache_key, revenue_data)
            return revenue_data
            
        except Exception as e:
            logger.error(f"Error getting revenue analytics: {str(e)}")
            return {'error': str(e)}
    
    def _get_daily_revenue(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get daily revenue breakdown"""
        daily_revenue = []
        
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            day_start = timezone.make_aware(datetime.combine(current_date, datetime.min.time()))
            day_end = day_start + timedelta(days=1)
            
            day_revenue = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                created_at__range=[day_start, day_end],
                status=ConversionStatus.APPROVED
            ).aggregate(
                total=Sum('payout'),
                count=Count('id')
            )
            
            daily_revenue.append({
                'date': current_date.isoformat(),
                'revenue': float(day_revenue['total'] or 0),
                'conversions': day_revenue['count'] or 0,
            })
            
            current_date += timedelta(days=1)
        
        return daily_revenue
    
    def _get_revenue_by_category(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get revenue breakdown by category"""
        category_revenue = OfferCategory.objects.annotate(
            revenue=Sum(
                'offer__userofferengagement__offerconversion__payout',
                filter=Q(
                    offer__tenant_id=self.tenant_id,
                    offer__userofferengagement__offerconversion__created_at__range=[start_date, end_date],
                    offer__userofferengagement__offerconversion__status=ConversionStatus.APPROVED
                )
            ),
            conversions=Count(
                'offer__userofferengagement__offerconversion',
                filter=Q(
                    offer__tenant_id=self.tenant_id,
                    offer__userofferengagement__offerconversion__created_at__range=[start_date, end_date],
                    offer__userofferengagement__offerconversion__status=ConversionStatus.APPROVED
                )
            )
        ).filter(revenue__gt=0).order_by('-revenue')
        
        return [
            {
                'category': category.name,
                'revenue': float(category.revenue or 0),
                'conversions': category.conversions or 0,
            }
            for category in category_revenue
        ]
    
    def _get_revenue_by_network(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get revenue breakdown by network"""
        network_revenue = AdNetwork.objects.annotate(
            revenue=Sum(
                'offer__userofferengagement__offerconversion__payout',
                filter=Q(
                    offer__tenant_id=self.tenant_id,
                    offer__userofferengagement__offerconversion__created_at__range=[start_date, end_date],
                    offer__userofferengagement__offerconversion__status=ConversionStatus.APPROVED
                )
            ),
            conversions=Count(
                'offer__userofferengagement__offerconversion',
                filter=Q(
                    offer__tenant_id=self.tenant_id,
                    offer__userofferengagement__offerconversion__created_at__range=[start_date, end_date],
                    offer__userofferengagement__offerconversion__status=ConversionStatus.APPROVED
                )
            )
        ).filter(revenue__gt=0).order_by('-revenue')
        
        return [
            {
                'network': network.name,
                'revenue': float(network.revenue or 0),
                'conversions': network.conversions or 0,
            }
            for network in network_revenue
        ]


# ==================== CONVERSION ANALYTICS ====================

class ConversionAnalytics(BaseAnalytics):
    """Analytics for conversions"""
    
    def get_conversion_analytics(self, period: str = AnalyticsPeriod.LAST_30_DAYS) -> Dict[str, Any]:
        """Get conversion analytics"""
        cache_key = self._get_cache_key('conversion_analytics', period)
        cached_data = self._get_from_cache(cache_key)
        
        if cached_data:
            return cached_data
        
        start_date, end_date = self._get_date_range(period)
        
        try:
            # Total conversions
            total_conversions = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                created_at__range=[start_date, end_date]
            ).count()
            
            # Conversions by status
            conversions_by_status = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                created_at__range=[start_date, end_date]
            ).values('status').annotate(
                count=Count('id')
            ).order_by('-count')
            
            # Fraud analytics
            fraudulent_conversions = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                created_at__range=[start_date, end_date],
                is_fraud=True
            ).count()
            
            fraud_rate = calculate_percentage(fraudulent_conversions, total_conversions)
            
            # Conversion trends
            conversion_trends = self._get_conversion_trends(start_date, end_date)
            
            # Average approval time
            approved_conversions = OfferConversion.objects.filter(
                tenant_id=self.tenant_id,
                created_at__range=[start_date, end_date],
                status=ConversionStatus.APPROVED,
                approved_at__isnull=False
            )
            
            avg_approval_time = approved_conversions.annotate(
                approval_time=ExpressionWrapper(
                    (F('approved_at') - F('created_at')).total_seconds() / 3600,  # hours
                    output_field=FloatField()
                )
            ).aggregate(avg_time=Avg('approval_time'))['avg_time'] or 0
            
            conversion_data = {
                'period': period,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat(),
                },
                'total_conversions': total_conversions,
                'conversions_by_status': [
                    {
                        'status': item['status'],
                        'count': item['count'],
                        'percentage': calculate_percentage(item['count'], total_conversions),
                    }
                    for item in conversions_by_status
                ],
                'fraud_analytics': {
                    'fraudulent_conversions': fraudulent_conversions,
                    'fraud_rate': fraud_rate,
                },
                'average_approval_time_hours': avg_approval_time,
                'conversion_trends': conversion_trends,
            }
            
            self._set_cache(cache_key, conversion_data)
            return conversion_data
            
        except Exception as e:
            logger.error(f"Error getting conversion analytics: {str(e)}")
            return {'error': str(e)}
    
    def _get_conversion_trends(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get conversion trends over time"""
        # Group by day
        daily_conversions = OfferConversion.objects.filter(
            tenant_id=self.tenant_id,
            created_at__range=[start_date, end_date]
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(status=ConversionStatus.APPROVED)),
            rejected=Count('id', filter=Q(status=ConversionStatus.REJECTED)),
            fraudulent=Count('id', filter=Q(is_fraud=True))
        ).order_by('date')
        
        return [
            {
                'date': item['date'].isoformat(),
                'total': item['total'],
                'approved': item['approved'],
                'rejected': item['rejected'],
                'fraudulent': item['fraudulent'],
            }
            for item in daily_conversions
        ]


# ==================== COMPREHENSIVE ANALYTICS ====================

class ComprehensiveAnalytics(BaseAnalytics):
    """Comprehensive analytics combining all analytics"""
    
    def __init__(self, tenant_id: str = 'default'):
        super().__init__(tenant_id)
        self.offer_analytics = OfferAnalytics(tenant_id)
        self.user_analytics = UserAnalytics(tenant_id)
        self.revenue_analytics = RevenueAnalytics(tenant_id)
        self.conversion_analytics = ConversionAnalytics(tenant_id)
    
    def get_dashboard_analytics(self, period: str = AnalyticsPeriod.LAST_30_DAYS) -> Dict[str, Any]:
        """Get comprehensive dashboard analytics"""
        try:
            return {
                'period': period,
                'offers': {
                    'top_performing': self.offer_analytics.get_top_performing_offers(period, limit=5),
                    'category_breakdown': self.offer_analytics.get_category_analytics(period),
                },
                'users': {
                    'top_users': self.user_analytics.get_top_users(period, 'revenue', limit=5),
                    'retention': self.user_analytics.get_user_retention_analytics(period),
                },
                'revenue': self.revenue_analytics.get_revenue_analytics(period),
                'conversions': self.conversion_analytics.get_conversion_analytics(period),
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard analytics: {str(e)}")
            return {'error': str(e)}
    
    def get_executive_summary(self, period: str = AnalyticsPeriod.LAST_30_DAYS) -> Dict[str, Any]:
        """Get executive summary analytics"""
        try:
            # Get key metrics from all analytics
            revenue_analytics = self.revenue_analytics.get_revenue_analytics(period)
            conversion_analytics = self.conversion_analytics.get_conversion_analytics(period)
            
            # Calculate growth rates
            revenue_growth = revenue_analytics.get('revenue_growth', 0)
            
            # Get top offers and users
            top_offers = self.offer_analytics.get_top_performing_offers(period, limit=3)
            top_users = self.user_analytics.get_top_users(period, 'revenue', limit=3)
            
            summary = {
                'period': period,
                'key_metrics': {
                    'total_revenue': revenue_analytics.get('total_revenue', 0),
                    'revenue_growth': revenue_growth,
                    'total_conversions': conversion_analytics.get('total_conversions', 0),
                    'fraud_rate': conversion_analytics.get('fraud_analytics', {}).get('fraud_rate', 0),
                },
                'top_performers': {
                    'offers': top_offers,
                    'users': top_users,
                },
                'health_indicators': {
                    'revenue_health': 'good' if revenue_growth >= 0 else 'warning',
                    'fraud_health': 'good' if conversion_analytics.get('fraud_analytics', {}).get('fraud_rate', 0) < 5 else 'warning',
                },
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting executive summary: {str(e)}")
            return {'error': str(e)}


# ==================== EXPORTS ====================

__all__ = [
    # Periods and status
    'AnalyticsPeriod',
    
    # Analytics classes
    'BaseAnalytics',
    'OfferAnalytics',
    'UserAnalytics',
    'RevenueAnalytics',
    'ConversionAnalytics',
    'ComprehensiveAnalytics',
]
