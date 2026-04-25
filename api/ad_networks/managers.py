"""
api/ad_networks/managers.py
Custom Django managers for ad networks models
SaaS-ready with tenant support
"""

from django.db import models
from django.db.models import Q, Count, Sum, Avg, F, ExpressionWrapper, FloatField
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any

from api.ad_networks.choices import (
    OfferStatus, EngagementStatus, ConversionStatus,
    RewardStatus, NetworkStatus
)
from api.ad_networks.constants import FRAUD_SCORE_THRESHOLD


class TenantModelManager(models.Manager):
    """
    Base manager for tenant-aware models
    """
    
    def get_queryset(self):
        """Filter by tenant if available"""
        queryset = super().get_queryset()
        
        # Try to get tenant from thread local or context
        try:
            from django.utils.deprecation import MiddlewareMixin
            tenant_id = getattr(self.model, '_tenant_id', None)
            if tenant_id:
                queryset = queryset.filter(tenant_id=tenant_id)
        except:
            pass
        
        return queryset
    
    def for_tenant(self, tenant_id: str):
        """Filter by specific tenant"""
        return self.get_queryset().filter(tenant_id=tenant_id)
    
    def active(self):
        """Filter by active status"""
        return self.get_queryset().filter(is_active=True)
    
    def inactive(self):
        """Filter by inactive status"""
        return self.get_queryset().filter(is_active=False)


class AdNetworkManager(TenantModelManager):
    """
    Manager for AdNetwork model
    """
    
    def active_networks(self):
        """Get active networks"""
        return self.get_queryset().filter(
            is_active=True,
            status=NetworkStatus.ACTIVE
        )
    
    def by_type(self, network_type: str):
        """Filter by network type"""
        return self.get_queryset().filter(network_type=network_type)
    
    def by_category(self, category: str):
        """Filter by category"""
        return self.get_queryset().filter(category=category)
    
    def with_offers(self):
        """Get networks with offers"""
        return self.get_queryset().filter(
            offer__isnull=False
        ).distinct()
    
    def with_stats(self):
        """Get networks with statistics"""
        return self.get_queryset().annotate(
            total_offers=Count('offer', distinct=True),
            active_offers=Count('offer', filter=Q(offer__status=OfferStatus.ACTIVE), distinct=True),
            total_conversions=Count('offer__userofferengagement__offerconversion', distinct=True),
            total_payout=Sum('offer__userofferengagement__offerconversion__payout'),
            avg_conversion_rate=ExpressionWrapper(
                Avg('offer__conversion_rate'),
                output_field=FloatField()
            )
        )
    
    def healthy_networks(self):
        """Get healthy networks based on recent health checks"""
        from api.ad_networks.models import NetworkHealthCheck
        
        cutoff_time = timezone.now() - timedelta(hours=24)
        healthy_networks = NetworkHealthCheck.objects.filter(
            checked_at__gte=cutoff_time,
            is_healthy=True
        ).values_list('network_id', flat=True)
        
        return self.get_queryset().filter(id__in=healthy_networks)
    
    def unhealthy_networks(self):
        """Get unhealthy networks based on recent health checks"""
        from api.ad_networks.models import NetworkHealthCheck
        
        cutoff_time = timezone.now() - timedelta(hours=24)
        unhealthy_networks = NetworkHealthCheck.objects.filter(
            checked_at__gte=cutoff_time,
            is_healthy=False
        ).values_list('network_id', flat=True)
        
        return self.get_queryset().filter(id__in=unhealthy_networks)
    
    def by_country_support(self, country_support: str):
        """Filter by country support"""
        return self.get_queryset().filter(country_support=country_support)
    
    def with_min_payout(self, min_payout: Decimal):
        """Filter by minimum payout"""
        return self.get_queryset().filter(min_payout__gte=min_payout)
    
    def with_priority(self, min_priority: int = 50):
        """Filter by priority"""
        return self.get_queryset().filter(priority__gte=min_priority)
    
    def verified_networks(self):
        """Get verified networks"""
        return self.get_queryset().filter(is_verified=True)
    
    def testing_networks(self):
        """Get testing networks"""
        return self.get_queryset().filter(is_testing=True)
    
    def production_ready(self):
        """Get production-ready networks"""
        return self.get_queryset().filter(
            is_active=True,
            is_verified=True,
            is_testing=False,
            status=NetworkStatus.ACTIVE
        )


class OfferManager(TenantModelManager):
    """
    Manager for Offer model
    """
    
    def active_offers(self):
        """Get active offers"""
        return self.get_queryset().filter(status=OfferStatus.ACTIVE)
    
    def by_network(self, network_id: int):
        """Filter by network"""
        return self.get_queryset().filter(ad_network_id=network_id)
    
    def by_category(self, category_id: int):
        """Filter by category"""
        return self.get_queryset().filter(category_id=category_id)
    
    def by_country(self, country: str):
        """Filter by country (offers available in country)"""
        return self.get_queryset().filter(
            Q(countries__contains=[country]) | Q(countries__isnull=True)
        )
    
    def by_platform(self, platform: str):
        """Filter by platform"""
        return self.get_queryset().filter(
            Q(platforms__contains=[platform]) | Q(platforms__isnull=True)
        )
    
    def by_device_type(self, device_type: str):
        """Filter by device type"""
        return self.get_queryset().filter(
            Q(device_type=device_type) | Q(device_type='any')
        )
    
    def by_difficulty(self, difficulty: str):
        """Filter by difficulty"""
        return self.get_queryset().filter(difficulty=difficulty)
    
    def by_reward_range(self, min_reward: Decimal, max_reward: Decimal = None):
        """Filter by reward amount range"""
        queryset = self.get_queryset().filter(reward_amount__gte=min_reward)
        if max_reward:
            queryset = queryset.filter(reward_amount__lte=max_reward)
        return queryset
    
    def featured_offers(self):
        """Get featured offers"""
        return self.get_queryset().filter(is_featured=True)
    
    def hot_offers(self):
        """Get hot offers"""
        return self.get_queryset().filter(is_hot=True)
    
    def new_offers(self):
        """Get new offers"""
        cutoff_time = timezone.now() - timedelta(days=7)
        return self.get_queryset().filter(
            is_new=True,
            created_at__gte=cutoff_time
        )
    
    def expiring_soon(self, days: int = 7):
        """Get offers expiring soon"""
        cutoff_time = timezone.now() + timedelta(days=days)
        return self.get_queryset().filter(
            expires_at__isnull=False,
            expires_at__lte=cutoff_time
        )
    
    def with_engagement_stats(self):
        """Get offers with engagement statistics"""
        return self.get_queryset().annotate(
            total_clicks=Count('userofferengagement'),
            total_conversions=Count('userofferengagement__offerconversion'),
            conversion_rate=ExpressionWrapper(
                Count('userofferengagement__offerconversion') * 100.0 / 
                Count('userofferengagement'),
                output_field=FloatField()
            ),
            total_payout=Sum('userofferengagement__offerconversion__payout'),
            avg_reward=Avg('reward_amount')
        )
    
    def high_converting(self, min_rate: float = 5.0):
        """Get offers with high conversion rates"""
        return self.with_engagement_stats().filter(
            conversion_rate__gte=min_rate
        )
    
    def trending(self, days: int = 7):
        """Get trending offers based on recent engagement"""
        cutoff_time = timezone.now() - timedelta(days=days)
        
        return self.get_queryset().filter(
            userofferengagement__created_at__gte=cutoff_time
        ).annotate(
            recent_engagements=Count('userofferengagement', filter=Q(
                userofferengagement__created_at__gte=cutoff_time
            ))
        ).order_by('-recent_engagements')
    
    def recommended_for_user(self, user_id: int):
        """Get offers recommended for specific user"""
        # This would integrate with recommendation service
        return self.get_queryset().filter(
            status=OfferStatus.ACTIVE
        )
    
    def by_completion_time(self, max_time: int = 30):
        """Filter by estimated completion time"""
        return self.get_queryset().filter(
            estimated_time__lte=max_time
        )
    
    def with_high_rewards(self, min_reward: Decimal = Decimal('10.00')):
        """Get offers with high rewards"""
        return self.get_queryset().filter(
            reward_amount__gte=min_reward
        )
    
    def by_user_preferences(self, user_id: int):
        """Get offers based on user preferences"""
        # This would integrate with user profile
        return self.get_queryset().filter(
            status=OfferStatus.ACTIVE
        )


class UserOfferEngagementManager(TenantModelManager):
    """
    Manager for UserOfferEngagement model
    """
    
    def by_user(self, user_id: int):
        """Filter by user"""
        return self.get_queryset().filter(user_id=user_id)
    
    def by_offer(self, offer_id: int):
        """Filter by offer"""
        return self.get_queryset().filter(offer_id=offer_id)
    
    def by_status(self, status: str):
        """Filter by status"""
        return self.get_queryset().filter(status=status)
    
    def completed(self):
        """Get completed engagements"""
        return self.get_queryset().filter(
            status__in=[EngagementStatus.COMPLETED, EngagementStatus.APPROVED]
        )
    
    def pending(self):
        """Get pending engagements"""
        return self.get_queryset().filter(status=EngagementStatus.PENDING)
    
    def with_conversions(self):
        """Get engagements with conversions"""
        return self.get_queryset().filter(
            offerconversion__isnull=False
        ).distinct()
    
    def recent(self, days: int = 30):
        """Get recent engagements"""
        cutoff_time = timezone.now() - timedelta(days=days)
        return self.get_queryset().filter(created_at__gte=cutoff_time)
    
    def by_ip_address(self, ip_address: str):
        """Filter by IP address"""
        return self.get_queryset().filter(ip_address=ip_address)
    
    def by_device(self, device: str):
        """Filter by device type"""
        return self.get_queryset().filter(device_info__device=device)
    
    def with_conversion_stats(self):
        """Get engagements with conversion statistics"""
        return self.get_queryset().annotate(
            has_conversion=Count('offerconversion'),
            conversion_amount=Sum('offerconversion__payout'),
            conversion_fraud_score=Avg('offerconversion__fraud_score')
        )
    
    def suspicious(self):
        """Get potentially suspicious engagements"""
        return self.with_conversion_stats().filter(
            Q(offerconversion__fraud_score__gte=FRAUD_SCORE_THRESHOLD) |
            Q(completion_time__lt=F('started_at') + timedelta(minutes=1))
        )
    
    def high_value(self, min_amount: Decimal = Decimal('50.00')):
        """Get high-value engagements"""
        return self.with_conversion_stats().filter(
            conversion_amount__gte=min_amount
        )
    
    def by_time_period(self, start_date: datetime, end_date: datetime):
        """Filter by time period"""
        return self.get_queryset().filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
    
    def with_user_stats(self):
        """Get engagements with user statistics"""
        return self.get_queryset().annotate(
            user_total_engagements=Count('user__userofferengagement'),
            user_completed_engagements=Count('user__userofferengagement', filter=Q(
                user__userofferengagement__status__in=[EngagementStatus.COMPLETED, EngagementStatus.APPROVED]
            )),
            user_conversion_rate=ExpressionWrapper(
                Count('user__userofferengagement__offerconversion') * 100.0 / 
                Count('user__userofferengagement'),
                output_field=FloatField()
            )
        )


class OfferConversionManager(TenantModelManager):
    """
    Manager for OfferConversion model
    """
    
    def by_user(self, user_id: int):
        """Filter by user"""
        return self.get_queryset().filter(engagement__user_id=user_id)
    
    def by_offer(self, offer_id: int):
        """Filter by offer"""
        return self.get_queryset().filter(engagement__offer_id=offer_id)
    
    def by_status(self, status: str):
        """Filter by status"""
        return self.get_queryset().filter(conversion_status=status)
    
    def approved(self):
        """Get approved conversions"""
        return self.get_queryset().filter(conversion_status=ConversionStatus.APPROVED)
    
    def rejected(self):
        """Get rejected conversions"""
        return self.get_queryset().filter(conversion_status=ConversionStatus.REJECTED)
    
    def fraudulent(self):
        """Get fraudulent conversions"""
        return self.get_queryset().filter(
            fraud_score__gte=FRAUD_SCORE_THRESHOLD
        )
    
    def recent(self, days: int = 30):
        """Get recent conversions"""
        cutoff_time = timezone.now() - timedelta(days=days)
        return self.get_queryset().filter(created_at__gte=cutoff_time)
    
    def by_fraud_score_range(self, min_score: float, max_score: float):
        """Filter by fraud score range"""
        return self.get_queryset().filter(
            fraud_score__gte=min_score,
            fraud_score__lte=max_score
        )
    
    def by_payout_range(self, min_payout: Decimal, max_payout: Decimal = None):
        """Filter by payout range"""
        queryset = self.get_queryset().filter(payout__gte=min_payout)
        if max_payout:
            queryset = queryset.filter(payout__lte=max_payout)
        return queryset
    
    def with_engagement_data(self):
        """Get conversions with engagement data"""
        return self.get_queryset().select_related(
            'engagement', 'engagement__user', 'engagement__offer', 'engagement__offer__ad_network'
        )
    
    def high_value(self, min_payout: Decimal = Decimal('100.00')):
        """Get high-value conversions"""
        return self.get_queryset().filter(payout__gte=min_payout)
    
    def suspicious_patterns(self):
        """Get conversions with suspicious patterns"""
        return self.get_queryset().filter(
            Q(fraud_score__gte=FRAUD_SCORE_THRESHOLD) |
            Q(payout__gte=Decimal('1000.00')) |
            Q(engagement__completion_time__lt=F('engagement__started_at') + timedelta(minutes=1))
        )
    
    def by_network(self, network_id: int):
        """Filter by network"""
        return self.get_queryset().filter(
            engagement__offer__ad_network_id=network_id
        )
    
    def by_time_period(self, start_date: datetime, end_date: datetime):
        """Filter by time period"""
        return self.get_queryset().filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
    
    def with_verification_status(self):
        """Get conversions with verification status"""
        return self.get_queryset().annotate(
            is_verified=Count('verification'),
            verification_count=Count('verification'),
            last_verification_date=Max('verification__created_at')
        )
    
    def pending_verification(self):
        """Get conversions pending verification"""
        return self.get_queryset().filter(
            conversion_status=ConversionStatus.PENDING
        )
    
    def chargebacks(self):
        """Get chargeback conversions"""
        return self.get_queryset().filter(
            conversion_status=ConversionStatus.CHARGEBACK
        )


class OfferRewardManager(TenantModelManager):
    """
    Manager for OfferReward model
    """
    
    def by_user(self, user_id: int):
        """Filter by user"""
        return self.get_queryset().filter(user_id=user_id)
    
    def by_offer(self, offer_id: int):
        """Filter by offer"""
        return self.get_queryset().filter(offer_id=offer_id)
    
    def by_status(self, status: str):
        """Filter by status"""
        return self.get_queryset().filter(status=status)
    
    def approved(self):
        """Get approved rewards"""
        return self.get_queryset().filter(status=RewardStatus.APPROVED)
    
    def pending(self):
        """Get pending rewards"""
        return self.get_queryset().filter(status=RewardStatus.PENDING)
    
    def cancelled(self):
        """Get cancelled rewards"""
        return self.get_queryset().filter(status=RewardStatus.CANCELLED)
    
    def paid(self):
        """Get paid rewards"""
        return self.get_queryset().filter(status=RewardStatus.PAID)
    
    def recent(self, days: int = 30):
        """Get recent rewards"""
        cutoff_time = timezone.now() - timedelta(days=days)
        return self.get_queryset().filter(created_at__gte=cutoff_time)
    
    def by_amount_range(self, min_amount: Decimal, max_amount: Decimal = None):
        """Filter by amount range"""
        queryset = self.get_queryset().filter(amount__gte=min_amount)
        if max_amount:
            queryset = queryset.filter(amount__lte=max_amount)
        return queryset
    
    def with_user_totals(self):
        """Get rewards with user totals"""
        return self.get_queryset().annotate(
            user_total_rewards=Count('user__offerreward'),
            user_total_amount=Sum('user__offerreward__amount'),
            user_approved_amount=Sum('user__offerreward__amount', filter=Q(
                user__offerreward__status=RewardStatus.APPROVED
            ))
        )
    
    def high_value(self, min_amount: Decimal = Decimal('50.00')):
        """Get high-value rewards"""
        return self.get_queryset().filter(amount__gte=min_amount)
    
    def by_currency(self, currency: str):
        """Filter by currency"""
        return self.get_queryset().filter(currency=currency)
    
    def by_time_period(self, start_date: datetime, end_date: datetime):
        """Filter by time period"""
        return self.get_queryset().filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )
    
    def pending_payout(self):
        """Get rewards pending payout"""
        return self.get_queryset().filter(
            status=RewardStatus.APPROVED,
            paid_at__isnull=True
        )
    
    def with_engagement_data(self):
        """Get rewards with engagement data"""
        return self.get_queryset().select_related(
            'user', 'offer', 'engagement', 'engagement__offer__ad_network'
        )
    
    def by_network(self, network_id: int):
        """Filter by network"""
        return self.get_queryset().filter(
            offer__ad_network_id=network_id
        )
    
    def with_payout_info(self):
        """Get rewards with payout information"""
        return self.get_queryset().annotate(
            days_since_created=ExpressionWrapper(
                timezone.now() - F('created_at'),
                output_field=models.DurationField()
            )
        )


class NetworkHealthCheckManager(TenantModelManager):
    """
    Manager for NetworkHealthCheck model
    """
    
    def by_network(self, network_id: int):
        """Filter by network"""
        return self.get_queryset().filter(network_id=network_id)
    
    def recent(self, hours: int = 24):
        """Get recent health checks"""
        cutoff_time = timezone.now() - timedelta(hours=hours)
        return self.get_queryset().filter(checked_at__gte=cutoff_time)
    
    def healthy(self):
        """Get healthy checks"""
        return self.get_queryset().filter(is_healthy=True)
    
    def unhealthy(self):
        """Get unhealthy checks"""
        return self.get_queryset().filter(is_healthy=False)
    
    def by_check_type(self, check_type: str):
        """Filter by check type"""
        return self.get_queryset().filter(check_type=check_type)
    
    def with_response_stats(self):
        """Get health checks with response statistics"""
        return self.get_queryset().annotate(
            avg_response_time=Avg('response_time_ms'),
            min_response_time=Min('response_time_ms'),
            max_response_time=Max('response_time_ms'),
            total_checks=Count('id'),
            healthy_checks=Count('id', filter=Q(is_healthy=True)),
            unhealthy_checks=Count('id', filter=Q(is_healthy=False))
        )
    
    def by_time_period(self, start_date: datetime, end_date: datetime):
        """Filter by time period"""
        return self.get_queryset().filter(
            checked_at__gte=start_date,
            checked_at__lte=end_date
        )
    
    def latest_for_network(self, network_id: int):
        """Get latest health check for network"""
        return self.get_queryset().filter(
            network_id=network_id
        ).order_by('-checked_at').first()
    
    def slow_responses(self, threshold_ms: int = 1000):
        """Get health checks with slow responses"""
        return self.get_queryset().filter(response_time_ms__gt=threshold_ms)
    
    def by_status_code(self, status_code: int):
        """Filter by HTTP status code"""
        return self.get_queryset().filter(status_code=status_code)
    
    def with_error_analysis(self):
        """Get health checks with error analysis"""
        return self.get_queryset().annotate(
            has_error=Count('error'),
            error_types=Count('error', distinct=True)
        )
    
    def uptime_percentage(self, network_id: int, days: int = 30):
        """Calculate uptime percentage for network"""
        cutoff_time = timezone.now() - timedelta(days=days)
        
        total_checks = self.get_queryset().filter(
            network_id=network_id,
            checked_at__gte=cutoff_time
        ).count()
        
        healthy_checks = self.get_queryset().filter(
            network_id=network_id,
            checked_at__gte=cutoff_time,
            is_healthy=True
        ).count()
        
        if total_checks == 0:
            return 0.0
        
        return (healthy_checks / total_checks) * 100
