"""
api/ad_networks/querysets.py
Custom querysets for ad networks module
SaaS-ready with tenant support
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Union

from django.db import models
from django.db.models import Q, Count, Sum, Avg, F, ExpressionWrapper, FloatField
from django.utils import timezone
from django.core.cache import cache

from .models import (
    AdNetwork, Offer, UserOfferEngagement, OfferConversion,
    OfferReward, UserWallet, OfferClick, NetworkHealthCheck,
    OfferDailyLimit, OfferTag, OfferTagging, KnownBadIP
)
from .choices import OfferStatus, EngagementStatus, ConversionStatus, RewardStatus

logger = logging.getLogger(__name__)


class TenantQuerySet(models.QuerySet):
    """Base queryset with tenant filtering"""
    
    def tenant(self, tenant_id: str):
        """Filter by tenant ID"""
        return self.filter(tenant_id=tenant_id)
    
    def active(self):
        """Filter by active status"""
        return self.filter(is_active=True)
    
    def inactive(self):
        """Filter by inactive status"""
        return self.filter(is_active=False)
    
    def created_since(self, days: int):
        """Filter records created since N days ago"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff_date)
    
    def created_until(self, days: int):
        """Filter records created until N days ago"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(created_at__lte=cutoff_date)
    
    def updated_since(self, days: int):
        """Filter records updated since N days ago"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(updated_at__gte=cutoff_date)


class AdNetworkQuerySet(TenantQuerySet):
    """Custom queryset for AdNetwork model"""
    
    def by_status(self, status: str):
        """Filter by status"""
        return self.filter(status=status)
    
    def by_category(self, category: str):
        """Filter by category"""
        return self.filter(category=category)
    
    def by_network_type(self, network_type: str):
        """Filter by network type"""
        return self.filter(network_type=network_type)
    
    def supports_postback(self):
        """Filter networks that support postback"""
        return self.filter(supports_postback=True)
    
    def supports_webhook(self):
        """Filter networks that support webhook"""
        return self.filter(supports_webhook=True)
    
    def verified(self):
        """Filter verified networks"""
        return self.filter(is_verified=True)
    
    def testing(self):
        """Filter testing networks"""
        return self.filter(is_testing=True)
    
    def healthy(self):
        """Filter healthy networks"""
        return self.filter(is_healthy=True)
    
    def by_country_support(self, country_support: str):
        """Filter by country support"""
        return self.filter(country_support=country_support)
    
    def by_min_payout(self, min_payout: Union[int, float, Decimal]):
        """Filter by minimum payout"""
        return self.filter(min_payout__gte=min_payout)
    
    def by_max_payout(self, max_payout: Union[int, float, Decimal]):
        """Filter by maximum payout"""
        return self.filter(max_payout__lte=max_payout)
    
    def by_rating(self, min_rating: float = None, max_rating: float = None):
        """Filter by rating range"""
        queryset = self
        if min_rating is not None:
            queryset = queryset.filter(rating__gte=min_rating)
        if max_rating is not None:
            queryset = queryset.filter(rating__lte=max_rating)
        return queryset
    
    def by_trust_score(self, min_score: float = None, max_score: float = None):
        """Filter by trust score range"""
        queryset = self
        if min_score is not None:
            queryset = queryset.filter(trust_score__gte=min_score)
        if max_score is not None:
            queryset = queryset.filter(trust_score__lte=max_score)
        return queryset
    
    def by_priority(self, min_priority: int = None, max_priority: int = None):
        """Filter by priority range"""
        queryset = self
        if min_priority is not None:
            queryset = queryset.filter(priority__gte=min_priority)
        if max_priority is not None:
            queryset = queryset.filter(priority__lte=max_priority)
        return queryset
    
    def with_offer_counts(self):
        """Annotate with offer counts"""
        return self.annotate(
            total_offers=Count('offer'),
            active_offers=Count(
                'offer',
                filter=Q(offer__status=OfferStatus.ACTIVE)
            ),
            expired_offers=Count(
                'offer',
                filter=Q(offer__status=OfferStatus.EXPIRED)
            )
        )
    
    def with_conversion_stats(self):
        """Annotate with conversion statistics"""
        from django.db.models import Window
        from django.db.models.functions import Coalesce
        
        return self.annotate(
            total_conversions=Count(
                'offer__userofferengagement__offerconversion'
            ),
            approved_conversions=Count(
                'offer__userofferengagement__offerconversion',
                filter=Q(
                    offer__userofferengagement__offerconversion__conversion_status=ConversionStatus.APPROVED
                )
            ),
            total_payout=Coalesce(
                Sum(
                    'offer__userofferengagement__offerconversion__payout',
                    filter=Q(
                        offer__userofferengagement__offerconversion__conversion_status=ConversionStatus.APPROVED
                    )
                ),
                0
            )
        )
    
    def with_health_stats(self):
        """Annotate with health statistics"""
        return self.annotate(
            health_checks_count=Count('networkhealthcheck'),
            healthy_checks_count=Count(
                'networkhealthcheck',
                filter=Q(networkhealthcheck__is_healthy=True)
            ),
            avg_response_time=Avg('networkhealthcheck__response_time_ms')
        )
    
    def search(self, query: str):
        """Search networks by name, description, or type"""
        return self.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(network_type__icontains=query) |
            Q(category__icontains=query)
        )


class OfferQuerySet(TenantQuerySet):
    """Custom queryset for Offer model"""
    
    def by_status(self, status: str):
        """Filter by status"""
        return self.filter(status=status)
    
    def by_network(self, network_id: int):
        """Filter by network ID"""
        return self.filter(ad_network_id=network_id)
    
    def by_category(self, category_id: int):
        """Filter by category ID"""
        return self.filter(category_id=category_id)
    
    def by_external_id(self, external_id: str):
        """Filter by external ID"""
        return self.filter(external_id=external_id)
    
    def featured(self):
        """Filter featured offers"""
        return self.filter(is_featured=True)
    
    def hot(self):
        """Filter hot offers"""
        return self.filter(is_hot=True)
    
    def new(self):
        """Filter new offers"""
        return self.filter(is_new=True)
    
    def by_countries(self, countries: List[str]):
        """Filter by countries (offers available in these countries)"""
        return self.filter(
            Q(countries__contains=countries) |
            Q(countries__isnull=True) |
            Q(countries__exact=[])
        )
    
    def by_platforms(self, platforms: List[str]):
        """Filter by platforms"""
        return self.filter(
            Q(platforms__contains=platforms) |
            Q(platforms__isnull=True) |
            Q(platforms__exact=[])
        )
    
    def by_device_type(self, device_type: str):
        """Filter by device type"""
        return self.filter(
            Q(device_type=device_type) |
            Q(device_type='any')
        )
    
    def by_difficulty(self, difficulty: str):
        """Filter by difficulty"""
        return self.filter(difficulty=difficulty)
    
    def by_reward_amount(self, min_amount: Union[int, float, Decimal] = None,
                        max_amount: Union[int, float, Decimal] = None):
        """Filter by reward amount range"""
        queryset = self
        if min_amount is not None:
            queryset = queryset.filter(reward_amount__gte=min_amount)
        if max_amount is not None:
            queryset = queryset.filter(reward_amount__lte=max_amount)
        return queryset
    
    def by_currency(self, currency: str):
        """Filter by currency"""
        return self.filter(reward_currency=currency)
    
    def expiring_soon(self, days: int = 7):
        """Filter offers expiring soon"""
        cutoff_date = timezone.now() + timedelta(days=days)
        return self.filter(
            expires_at__isnull=False,
            expires_at__lte=cutoff_date
        )
    
    def expired(self):
        """Filter expired offers"""
        return self.filter(
            expires_at__isnull=False,
            expires_at__lt=timezone.now()
        )
    
    def not_expired(self):
        """Filter non-expired offers"""
        return self.filter(
            Q(expires_at__isnull=True) |
            Q(expires_at__gt=timezone.now())
        )
    
    def by_priority(self, min_priority: int = None, max_priority: int = None):
        """Filter by priority range"""
        queryset = self
        if min_priority is not None:
            queryset = queryset.filter(priority__gte=min_priority)
        if max_priority is not None:
            queryset = queryset.filter(priority__lte=max_priority)
        return queryset
    
    def with_engagement_stats(self):
        """Annotate with engagement statistics"""
        return self.annotate(
            total_clicks=Count('offerclick'),
            unique_clicks=Count('offerclick__ip_address', distinct=True),
            total_engagements=Count('userofferengagement'),
            completed_engagements=Count(
                'userofferengagement',
                filter=Q(userofferengagement__status=EngagementStatus.COMPLETED)
            ),
            total_conversions=Count('userofferengagement__offerconversion'),
            approved_conversions=Count(
                'userofferengagement__offerconversion',
                filter=Q(
                    userofferengagement__offerconversion__conversion_status=ConversionStatus.APPROVED
                )
            )
        )
    
    def with_conversion_rates(self):
        """Annotate with conversion rates"""
        return self.annotate(
            engagement_rate=ExpressionWrapper(
                Count('userofferengagement') * 100.0 / Count('offerclick'),
                output_field=FloatField()
            ),
            conversion_rate=ExpressionWrapper(
                Count('userofferengagement__offerconversion') * 100.0 / Count('userofferengagement'),
                output_field=FloatField()
            ),
            approval_rate=ExpressionWrapper(
                Count(
                    'userofferengagement__offerconversion',
                    filter=Q(
                        userofferengagement__offerconversion__conversion_status=ConversionStatus.APPROVED
                    )
                ) * 100.0 / Count('userofferengagement__offerconversion'),
                output_field=FloatField()
            )
        )
    
    def with_payout_stats(self):
        """Annotate with payout statistics"""
        return self.annotate(
            total_payout=Sum(
                'userofferengagement__offerconversion__payout',
                filter=Q(
                    userofferengagement__offerconversion__conversion_status=ConversionStatus.APPROVED
                )
            ),
            avg_payout=Avg(
                'userofferengagement__offerconversion__payout',
                filter=Q(
                    userofferengagement__offerconversion__conversion_status=ConversionStatus.APPROVED
                )
            )
        )
    
    def search(self, query: str):
        """Search offers by title, description, or requirements"""
        return self.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(short_description__icontains=query) |
            Q(requirements__icontains=query) |
            Q(instructions__icontains=query)
        )
    
    def for_user(self, user):
        """Filter offers suitable for user"""
        # This would implement complex user targeting logic
        # For now, just return active offers
        return self.filter(status=OfferStatus.ACTIVE)


class UserOfferEngagementQuerySet(TenantQuerySet):
    """Custom queryset for UserOfferEngagement model"""
    
    def by_user(self, user_id: int):
        """Filter by user ID"""
        return self.filter(user_id=user_id)
    
    def by_offer(self, offer_id: int):
        """Filter by offer ID"""
        return self.filter(offer_id=offer_id)
    
    def by_status(self, status: str):
        """Filter by status"""
        return self.filter(status=status)
    
    def started(self):
        """Filter started engagements"""
        return self.filter(status=EngagementStatus.STARTED)
    
    def viewed(self):
        """Filter viewed engagements"""
        return self.filter(status=EngagementStatus.VIEWED)
    
    def completed(self):
        """Filter completed engagements"""
        return self.filter(status=EngagementStatus.COMPLETED)
    
    def approved(self):
        """Filter approved engagements"""
        return self.filter(status=EngagementStatus.APPROVED)
    
    def rejected(self):
        """Filter rejected engagements"""
        return self.filter(status=EngagementStatus.REJECTED)
    
    def with_conversion(self):
        """Filter engagements that have conversions"""
        return self.filter(offerconversion__isnull=False)
    
    def without_conversion(self):
        """Filter engagements without conversions"""
        return self.filter(offerconversion__isnull=True)
    
    def by_ip_address(self, ip_address: str):
        """Filter by IP address"""
        return self.filter(ip_address=ip_address)
    
    def by_country(self, country: str):
        """Filter by country"""
        return self.filter(country=country)
    
    def by_device(self, device: str):
        """Filter by device"""
        return self.filter(device_info__contains={'type': device})
    
    def started_since(self, days: int):
        """Filter engagements started since N days ago"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(started_at__gte=cutoff_date)
    
    def completed_since(self, days: int):
        """Filter engagements completed since N days ago"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(
            completed_at__isnull=False,
            completed_at__gte=cutoff_date
        )
    
    def with_duration(self):
        """Annotate with duration in minutes"""
        return self.annotate(
            duration_minutes=ExpressionWrapper(
                (F('completed_at') - F('started_at')).total_seconds() / 60,
                output_field=FloatField()
            )
        )
    
    def with_conversion_data(self):
        """Annotate with conversion data"""
        return self.annotate(
            has_conversion=Count('offerconversion'),
            conversion_status=Count(
                'offerconversion__conversion_status',
                distinct=True
            ),
            conversion_payout=Sum('offerconversion__payout')
        )
    
    def by_time_range(self, start_date: datetime = None, end_date: datetime = None):
        """Filter by time range"""
        queryset = self
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        return queryset


class OfferConversionQuerySet(TenantQuerySet):
    """Custom queryset for OfferConversion model"""
    
    def by_engagement(self, engagement_id: int):
        """Filter by engagement ID"""
        return self.filter(engagement_id=engagement_id)
    
    def by_user(self, user_id: int):
        """Filter by user ID"""
        return self.filter(engagement__user_id=user_id)
    
    def by_offer(self, offer_id: int):
        """Filter by offer ID"""
        return self.filter(engagement__offer_id=offer_id)
    
    def by_network(self, network_id: int):
        """Filter by network ID"""
        return self.filter(engagement__offer__ad_network_id=network_id)
    
    def by_status(self, status: str):
        """Filter by status"""
        return self.filter(conversion_status=status)
    
    def pending(self):
        """Filter pending conversions"""
        return self.filter(conversion_status=ConversionStatus.PENDING)
    
    def approved(self):
        """Filter approved conversions"""
        return self.filter(conversion_status=ConversionStatus.APPROVED)
    
    def rejected(self):
        """Filter rejected conversions"""
        return self.filter(conversion_status=ConversionStatus.REJECTED)
    
    def chargeback(self):
        """Filter chargeback conversions"""
        return self.filter(conversion_status=ConversionStatus.CHARGEBACK)
    
    def by_payout_range(self, min_amount: Union[int, float, Decimal] = None,
                        max_amount: Union[int, float, Decimal] = None):
        """Filter by payout range"""
        queryset = self
        if min_amount is not None:
            queryset = queryset.filter(payout__gte=min_amount)
        if max_amount is not None:
            queryset = queryset.filter(payout__lte=max_amount)
        return queryset
    
    def by_currency(self, currency: str):
        """Filter by currency"""
        return self.filter(currency=currency)
    
    def by_fraud_score(self, min_score: float = None, max_score: float = None):
        """Filter by fraud score range"""
        queryset = self
        if min_score is not None:
            queryset = queryset.filter(fraud_score__gte=min_score)
        if max_score is not None:
            queryset = queryset.filter(fraud_score__lte=max_score)
        return queryset
    
    def suspicious(self, threshold: float = 70.0):
        """Filter suspicious conversions"""
        return self.filter(fraud_score__gte=threshold)
    
    def not_suspicious(self, threshold: float = 70.0):
        """Filter non-suspicious conversions"""
        return self.filter(fraud_score__lt=threshold)
    
    def by_fraud_indicators(self, indicators: List[str]):
        """Filter by fraud indicators"""
        return self.filter(fraud_indicators__contains=indicators)
    
    def approved_since(self, days: int):
        """Filter conversions approved since N days ago"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(
            conversion_status=ConversionStatus.APPROVED,
            approved_at__gte=cutoff_date
        )
    
    def rejected_since(self, days: int):
        """Filter conversions rejected since N days ago"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(
            conversion_status=ConversionStatus.REJECTED,
            rejected_at__gte=cutoff_date
        )
    
    def with_engagement_data(self):
        """Annotate with engagement data"""
        return self.annotate(
            user_id=F('engagement__user_id'),
            offer_id=F('engagement__offer_id'),
            network_id=F('engagement__offer__ad_network_id'),
            engagement_status=F('engagement__status'),
            engagement_started_at=F('engagement__started_at'),
            engagement_completed_at=F('engagement__completed_at')
        )
    
    def with_processing_time(self):
        """Annotate with processing time"""
        return self.annotate(
            processing_time_hours=ExpressionWrapper(
                (F('approved_at') - F('created_at')).total_seconds() / 3600,
                output_field=FloatField()
            )
        )
    
    def by_time_range(self, start_date: datetime = None, end_date: datetime = None):
        """Filter by time range"""
        queryset = self
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        return queryset


class OfferRewardQuerySet(TenantQuerySet):
    """Custom queryset for OfferReward model"""
    
    def by_user(self, user_id: int):
        """Filter by user ID"""
        return self.filter(user_id=user_id)
    
    def by_offer(self, offer_id: int):
        """Filter by offer ID"""
        return self.filter(offer_id=offer_id)
    
    def by_engagement(self, engagement_id: int):
        """Filter by engagement ID"""
        return self.filter(engagement_id=engagement_id)
    
    def by_status(self, status: str):
        """Filter by status"""
        return self.filter(status=status)
    
    def pending(self):
        """Filter pending rewards"""
        return self.filter(status=RewardStatus.PENDING)
    
    def approved(self):
        """Filter approved rewards"""
        return self.filter(status=RewardStatus.APPROVED)
    
    def paid(self):
        """Filter paid rewards"""
        return self.filter(status=RewardStatus.PAID)
    
    def cancelled(self):
        """Filter cancelled rewards"""
        return self.filter(status=RewardStatus.CANCELLED)
    
    def by_amount_range(self, min_amount: Union[int, float, Decimal] = None,
                       max_amount: Union[int, float, Decimal] = None):
        """Filter by amount range"""
        queryset = self
        if min_amount is not None:
            queryset = queryset.filter(amount__gte=min_amount)
        if max_amount is not None:
            queryset = queryset.filter(amount__lte=max_amount)
        return queryset
    
    def by_currency(self, currency: str):
        """Filter by currency"""
        return self.filter(currency=currency)
    
    def by_payment_method(self, payment_method: str):
        """Filter by payment method"""
        return self.filter(payment_method=payment_method)
    
    def approved_since(self, days: int):
        """Filter rewards approved since N days ago"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(
            status=RewardStatus.APPROVED,
            approved_at__gte=cutoff_date
        )
    
    def paid_since(self, days: int):
        """Filter rewards paid since N days ago"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(
            status=RewardStatus.PAID,
            paid_at__gte=cutoff_date
        )
    
    def with_engagement_data(self):
        """Annotate with engagement data"""
        return self.annotate(
            user_id=F('engagement__user_id'),
            offer_id=F('engagement__offer_id'),
            network_id=F('engagement__offer__ad_network_id'),
            engagement_status=F('engagement__status')
        )
    
    def with_processing_time(self):
        """Annotate with processing time"""
        return self.annotate(
            processing_time_hours=ExpressionWrapper(
                (F('approved_at') - F('created_at')).total_seconds() / 3600,
                output_field=FloatField()
            )
        )
    
    def by_time_range(self, start_date: datetime = None, end_date: datetime = None):
        """Filter by time range"""
        queryset = self
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        return queryset


class OfferClickQuerySet(TenantQuerySet):
    """Custom queryset for OfferClick model"""
    
    def by_offer(self, offer_id: int):
        """Filter by offer ID"""
        return self.filter(offer_id=offer_id)
    
    def by_user(self, user_id: int):
        """Filter by user ID"""
        return self.filter(user_id=user_id)
    
    def by_ip_address(self, ip_address: str):
        """Filter by IP address"""
        return self.filter(ip_address=ip_address)
    
    def by_country(self, country: str):
        """Filter by country"""
        return self.filter(country=country)
    
    def by_device(self, device: str):
        """Filter by device"""
        return self.filter(device=device)
    
    def by_browser(self, browser: str):
        """Filter by browser"""
        return self.filter(browser=browser)
    
    def by_os(self, os: str):
        """Filter by operating system"""
        return self.filter(os=os)
    
    def unique(self):
        """Filter unique clicks"""
        return self.filter(is_unique=True)
    
    def fraudulent(self):
        """Filter fraudulent clicks"""
        return self.filter(is_fraud=True)
    
    def not_fraudulent(self):
        """Filter non-fraudulent clicks"""
        return self.filter(is_fraud=False)
    
    def by_fraud_score(self, min_score: float = None, max_score: float = None):
        """Filter by fraud score range"""
        queryset = self
        if min_score is not None:
            queryset = queryset.filter(fraud_score__gte=min_score)
        if max_score is not None:
            queryset = queryset.filter(fraud_score__lte=max_score)
        return queryset
    
    def clicked_since(self, days: int):
        """Filter clicks since N days ago"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(clicked_at__gte=cutoff_date)
    
    def clicked_until(self, days: int):
        """Filter clicks until N days ago"""
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(clicked_at__lte=cutoff_date)
    
    def with_conversion_data(self):
        """Annotate with conversion data"""
        return self.annotate(
            has_conversion=Count('userofferengagement__offerconversion'),
            conversion_status=Count(
                'userofferengagement__offerconversion__conversion_status',
                distinct=True
            )
        )
    
    def by_time_range(self, start_date: datetime = None, end_date: datetime = None):
        """Filter by time range"""
        queryset = self
        if start_date:
            queryset = queryset.filter(clicked_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(clicked_at__lte=end_date)
        return queryset


# Export all querysets
__all__ = [
    'TenantQuerySet',
    'AdNetworkQuerySet',
    'OfferQuerySet',
    'UserOfferEngagementQuerySet',
    'OfferConversionQuerySet',
    'OfferRewardQuerySet',
    'OfferClickQuerySet'
]
