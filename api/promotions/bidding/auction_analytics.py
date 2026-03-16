# =============================================================================
# api/promotions/bidding/auction_analytics.py
# Auction Analytics — Performance tracking, revenue analysis, win/loss reports
# =============================================================================

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from django.core.cache import cache
from django.db.models import Avg, Count, Sum, Max, Min, Q

logger = logging.getLogger('bidding.analytics')

CACHE_PREFIX_ANALYTICS = 'bid:analytics:{}'
CACHE_TTL_ANALYTICS    = 600   # 10 min


@dataclass
class AuctionPerformanceReport:
    period:             str
    total_auctions:     int
    fill_rate:          float
    avg_clearing_price: Decimal
    total_revenue:      Decimal
    top_campaigns:      list
    platform_breakdown: dict
    hourly_revenue:     list
    floor_price_impact: dict    # Floor এর কারণে কত revenue gained/lost


@dataclass
class CampaignAuctionReport:
    campaign_id:     int
    win_count:       int
    loss_count:      int
    win_rate:        float
    avg_bid:         Decimal
    avg_winning_bid: Decimal
    total_spend:     Decimal
    avg_quality_score: float
    lost_reasons:    dict   # {'below_floor': 10, 'outbid': 25}


class AuctionAnalytics:
    """
    Auction performance analytics।

    Reports:
    1. Platform-level revenue
    2. Campaign win/loss analysis
    3. Floor price effectiveness
    4. Hourly/daily patterns
    5. Competitor insights
    """

    def platform_revenue_report(self, days: int = 7) -> dict:
        """Platform-wise revenue report।"""
        cache_key = CACHE_PREFIX_ANALYTICS.format(f'platform_rev:{days}')
        cached    = cache.get(cache_key)
        if cached:
            return cached

        from api.promotions.models import AdminCommissionLog
        from django.utils import timezone
        from datetime import timedelta

        since = timezone.now() - timedelta(days=days)
        data  = (
            AdminCommissionLog.objects
            .filter(created_at__gte=since)
            .values('campaign__platform__name')
            .annotate(
                total_revenue = Sum('total_amount_usd'),
                total_commissions = Count('id'),
                avg_commission = Avg('commission_usd'),
            )
            .order_by('-total_revenue')
        )
        result = {
            row['campaign__platform__name']: {
                'revenue':    float(row['total_revenue'] or 0),
                'count':      row['total_commissions'],
                'avg_amount': float(row['avg_commission'] or 0),
            }
            for row in data
        }
        cache.set(cache_key, result, timeout=CACHE_TTL_ANALYTICS)
        return result

    def campaign_win_loss_report(self, campaign_id: int) -> CampaignAuctionReport:
        """Campaign এর auction win/loss analysis।"""
        from api.promotions.models import TaskSubmission, Campaign
        from api.promotions.choices import SubmissionStatus

        try:
            campaign = Campaign.objects.get(pk=campaign_id)
        except Campaign.DoesNotExist:
            return None

        subs     = TaskSubmission.objects.filter(campaign_id=campaign_id)
        approved = subs.filter(status=SubmissionStatus.APPROVED).count()
        rejected = subs.filter(status=SubmissionStatus.REJECTED).count()
        total    = subs.count()

        return CampaignAuctionReport(
            campaign_id     = campaign_id,
            win_count       = approved,
            loss_count      = rejected,
            win_rate        = round(approved / max(total, 1), 3),
            avg_bid         = campaign.bid_amount_usd or Decimal('0'),
            avg_winning_bid = campaign.bid_amount_usd or Decimal('0'),
            total_spend     = campaign.spent_usd,
            avg_quality_score = 0.7,
            lost_reasons    = {'outbid': rejected},
        )

    def hourly_revenue_pattern(self, days: int = 7) -> list:
        """Hourly revenue pattern — peak hours identify করে।"""
        cache_key = CACHE_PREFIX_ANALYTICS.format(f'hourly:{days}')
        cached    = cache.get(cache_key)
        if cached:
            return cached

        from api.promotions.models import AdminCommissionLog
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models.functions import ExtractHour

        since = timezone.now() - timedelta(days=days)
        data  = (
            AdminCommissionLog.objects
            .filter(created_at__gte=since)
            .annotate(hour=ExtractHour('created_at'))
            .values('hour')
            .annotate(revenue=Sum('total_amount_usd'), count=Count('id'))
            .order_by('hour')
        )
        hourly = [0.0] * 24
        counts = [0]    * 24
        for row in data:
            h = row['hour']
            if 0 <= h < 24:
                hourly[h] = float(row['revenue'] or 0)
                counts[h] = row['count']

        result = [{'hour': h, 'revenue': hourly[h], 'count': counts[h]} for h in range(24)]
        cache.set(cache_key, result, timeout=CACHE_TTL_ANALYTICS)
        return result

    def floor_price_impact_analysis(self, days: int = 7) -> dict:
        """
        Floor price effectiveness analyze করে।
        কতটা revenue floor এর কারণে gained/lost হয়েছে।
        """
        # Simplified — production এ auction log table থেকে calculate করুন
        return {
            'floor_enforcements':  0,
            'revenue_from_floor':  0.0,
            'lost_bids_below_floor': 0,
            'avg_floor_premium':   0.0,
            'recommendation':      'Analyze auction_log table for detailed insights',
        }

    def generate_daily_summary(self) -> dict:
        """Daily summary generate করে — Celery task থেকে call করো।"""
        return {
            'platform_revenue': self.platform_revenue_report(days=1),
            'hourly_pattern':   self.hourly_revenue_pattern(days=1),
        }
