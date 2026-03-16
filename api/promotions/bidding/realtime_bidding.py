# =============================================================================
# api/promotions/bidding/realtime_bidding.py
# Real-Time Bidding (RTB) — Millisecond-level bid response
# OpenRTB 2.6 compatible bid request/response
# =============================================================================

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from django.core.cache import cache

logger = logging.getLogger('bidding.rtb')

RTB_TIMEOUT_MS      = 100   # 100ms — RTB standard timeout
CACHE_PREFIX_RTB    = 'bid:rtb:{}'


@dataclass
class BidRequest:
    """OpenRTB 2.6 Bid Request (simplified)।"""
    id:           str
    slot_id:      str
    platform:     str
    category:     str
    country:      str
    device_type:  str       # mobile, desktop, tablet
    user_segment: dict      # user targeting data (anonymized)
    floor_price:  Decimal
    auction_type: int       # 1 = first price, 2 = second price
    tmax:         int       # max response time in ms
    timestamp:    float     = field(default_factory=time.time)


@dataclass
class BidResponse:
    """OpenRTB 2.6 Bid Response।"""
    request_id:   str
    campaign_id:  Optional[int]
    bid_price:    Decimal
    ad_markup:    str
    win_notice_url: str
    loss_notice_url: str
    response_ms:  float
    status:       str       # 'bid', 'no_bid', 'error'
    reason:       str       = ''


@dataclass
class RTBStats:
    total_requests:  int
    total_bids:      int
    win_count:       int
    no_bid_count:    int
    avg_response_ms: float
    avg_bid_price:   Decimal
    win_rate:        float


class RTBBidder:
    """
    Real-Time Bidding engine।

    Flow:
    1. Bid Request আসে (slot available)
    2. 100ms এর মধ্যে bid করবো কিনা decide
    3. Bid price calculate করে response পাঠাই
    4. Win/loss notification handle করি

    Compatible with: Google Ad Manager, AppNexus, PubMatic
    """

    def __init__(self):
        from .auction_logic import QualityScoreCalculator
        from .budget_pacing import BudgetPacer
        self._qs_calc  = QualityScoreCalculator()
        self._pacer    = BudgetPacer()

    def process_bid_request(self, request: BidRequest) -> BidResponse:
        """
        Bid request process করে response দেয়।
        100ms এর মধ্যে respond করতে হবে।
        """
        start = time.monotonic()

        # Eligible campaigns খুঁজো
        campaigns = self._find_eligible_campaigns(request)

        if not campaigns:
            return BidResponse(
                request_id=request.id, campaign_id=None,
                bid_price=Decimal('0'), ad_markup='',
                win_notice_url='', loss_notice_url='',
                response_ms=round((time.monotonic() - start) * 1000, 2),
                status='no_bid', reason='no_eligible_campaigns',
            )

        # Best campaign select করো
        best_campaign, bid_price = self._select_best_bid(campaigns, request)

        if not best_campaign:
            return BidResponse(
                request_id=request.id, campaign_id=None,
                bid_price=Decimal('0'), ad_markup='',
                win_notice_url='', loss_notice_url='',
                response_ms=round((time.monotonic() - start) * 1000, 2),
                status='no_bid', reason='below_floor',
            )

        elapsed = round((time.monotonic() - start) * 1000, 2)

        # Log for analytics
        self._log_bid(request, best_campaign['id'], bid_price, elapsed)

        return BidResponse(
            request_id=request.id,
            campaign_id=best_campaign['id'],
            bid_price=bid_price,
            ad_markup=self._generate_ad_markup(best_campaign, request),
            win_notice_url=f'/rtb/win/{request.id}/',
            loss_notice_url=f'/rtb/loss/{request.id}/',
            response_ms=elapsed,
            status='bid',
        )

    def handle_win_notification(self, request_id: str, clearing_price: Decimal) -> None:
        """Win notification — actual charge করো।"""
        bid_data = cache.get(CACHE_PREFIX_RTB.format(f'bid:{request_id}'))
        if not bid_data:
            logger.warning(f'RTB win notification: bid data not found for {request_id}')
            return

        campaign_id = bid_data['campaign_id']
        logger.info(f'RTB Win: campaign={campaign_id}, price=${clearing_price}')

        # Budget deduct করো
        try:
            from api.promotions.models import Campaign
            Campaign.objects.filter(pk=campaign_id).update(
                spent_usd=models.F('spent_usd') + clearing_price
            )
        except Exception as e:
            logger.error(f'RTB win budget deduct failed: {e}')

    def handle_loss_notification(self, request_id: str, reason: str = '') -> None:
        """Loss notification — analytics update।"""
        logger.debug(f'RTB Loss: request={request_id}, reason={reason}')

    def get_stats(self, window_minutes: int = 60) -> RTBStats:
        """RTB stats return করে।"""
        stats_key = CACHE_PREFIX_RTB.format('stats')
        stats     = cache.get(stats_key) or {
            'total': 0, 'bids': 0, 'wins': 0, 'no_bids': 0,
            'total_ms': 0.0, 'total_price': 0.0,
        }
        return RTBStats(
            total_requests  = stats['total'],
            total_bids      = stats['bids'],
            win_count       = stats['wins'],
            no_bid_count    = stats['no_bids'],
            avg_response_ms = round(stats['total_ms'] / max(stats['total'], 1), 2),
            avg_bid_price   = Decimal(str(stats['total_price'] / max(stats['bids'], 1))),
            win_rate        = stats['wins'] / max(stats['bids'], 1),
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _find_eligible_campaigns(self, request: BidRequest) -> list:
        """Targeting match করা campaigns খুঁজো।"""
        from api.promotions.models import Campaign
        from api.promotions.choices import CampaignStatus
        from django.db.models import Q

        campaigns = Campaign.objects.filter(
            status=CampaignStatus.ACTIVE,
            platform__name__iexact=request.platform,
            spent_usd__lt=models.F('total_budget_usd'),
        ).filter(
            Q(targeting__countries__contains=[request.country]) | Q(targeting__isnull=True)
        ).select_related('targeting', 'platform', 'category').values(
            'id', 'advertiser_id', 'bid_amount_usd', 'spent_usd',
            'total_budget_usd', 'category__name',
        )[:20]

        return list(campaigns)

    def _select_best_bid(self, campaigns: list, request: BidRequest) -> tuple:
        """Best bid select করো।"""
        from .budget_pacing import BudgetPacer
        pacer    = BudgetPacer()
        best     = None
        best_eff = Decimal('0')

        for c in campaigns:
            # Budget check
            remaining = Decimal(str(c['total_budget_usd'])) - Decimal(str(c['spent_usd']))
            if remaining < request.floor_price:
                continue

            # Pacing check (quick cache lookup)
            pacing_key = CACHE_PREFIX_RTB.format(f'pace:{c["id"]}')
            throttle   = cache.get(pacing_key)
            if throttle is None:
                throttle = pacer.get_bid_modifier(c['id'])
                cache.set(pacing_key, throttle, timeout=30)
            if throttle == 0.0:
                continue

            bid_amount = Decimal(str(c['bid_amount_usd'])) * Decimal(str(throttle))
            qs         = self._qs_calc.calculate(c['id'], '', c.get('category__name', ''))
            eff_bid    = bid_amount * Decimal(str(qs))

            if eff_bid > best_eff and bid_amount >= request.floor_price:
                best     = c
                best_eff = eff_bid

        if not best:
            return None, Decimal('0')

        return best, Decimal(str(best['bid_amount_usd']))

    @staticmethod
    def _generate_ad_markup(campaign: dict, request: BidRequest) -> str:
        """Ad markup (HTML/JSON) generate করে।"""
        return json.dumps({
            'campaign_id': campaign['id'],
            'slot_id':     request.slot_id,
            'track_url':   f'/track/{campaign["id"]}/',
        })

    def _log_bid(self, request: BidRequest, campaign_id: int, price: Decimal, ms: float):
        """Bid log করে + stats update।"""
        cache.set(
            CACHE_PREFIX_RTB.format(f'bid:{request.id}'),
            {'campaign_id': campaign_id, 'price': float(price)},
            timeout=300,
        )
        # Stats update
        stats_key = CACHE_PREFIX_RTB.format('stats')
        stats     = cache.get(stats_key) or {'total': 0, 'bids': 0, 'wins': 0, 'no_bids': 0, 'total_ms': 0.0, 'total_price': 0.0}
        stats['total']       += 1
        stats['bids']        += 1
        stats['total_ms']    += ms
        stats['total_price'] += float(price)
        cache.set(stats_key, stats, timeout=3600)
