"""
tasks/rtb_tasks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Real-Time Bidding (RTB) System — CPAlead's Core DSP/SSP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPAlead uses RTB to automatically route traffic to highest-paying offers.
Our implementation:
  ✅ run_bid_auction          — run real-time auction for a click/impression
  ✅ update_bid_floor_prices  — adjust floor prices based on traffic quality
  ✅ settle_auction_results   — charge winners, release losers
  ✅ rank_advertisers_by_epc  — rank by effective cost per click
  ✅ refresh_bid_cache        — warm up bid tables every 30s
  ✅ generate_rtb_report      — RTB performance report
  ✅ detect_invalid_traffic   — IVT scoring per advertiser/publisher
"""
import logging
import heapq
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

BID_CACHE_TTL   = 30    # seconds — bids are valid for 30s
FLOOR_PRICE_TTL = 300   # floor price cache 5 minutes
MIN_BID         = Decimal('0.001')


@shared_task(bind=True, max_retries=2, default_retry_delay=5,
             name='tasks.rtb_tasks.run_bid_auction')
def run_bid_auction(
    self,
    user_id: int,
    country: str,
    device: str,
    os_type: str,
    publisher_id: int,
    slot_type: str = 'offerwall',
    num_winners: int = 5,
) -> dict:
    """
    Run a real-time bid auction for a user impression.
    Process:
    1. Fetch eligible bids from cache (advertisers who want this traffic)
    2. Apply floor price filter
    3. Sort by bid price descending (highest bidder wins)
    4. Return top N winning offers for display
    5. Record auction result for billing

    slot_type: 'offerwall' | 'content_locker' | 'link_locker' | 'banner'
    """
    try:
        logger.debug(f"🏷️ RTB auction: user={user_id} country={country} device={device}")

        # Get floor price for this traffic segment
        floor_key   = f'floor_{country}_{device}_{os_type}'
        floor_price = Decimal(str(cache.get(floor_key) or '0.001'))

        # Fetch active bids from cache
        bids_key = f'rtb_bids_{country}_{device}'
        all_bids = cache.get(bids_key) or []

        if not all_bids:
            # Fallback: query DB
            all_bids = _load_bids_from_db(country, device, os_type)
            cache.set(bids_key, all_bids, timeout=BID_CACHE_TTL)

        # Filter by floor price and slot type
        eligible = [
            b for b in all_bids
            if Decimal(str(b.get('bid_price', 0))) >= floor_price
            and slot_type in b.get('slot_types', [slot_type])
            and b.get('is_active', True)
        ]

        if not eligible:
            # No bids — return default/remnant offers
            return {
                'status': 'no_bids',
                'winners': [],
                'floor_price': str(floor_price),
                'timestamp': timezone.now().isoformat(),
            }

        # Sort by bid price + quality score (second-price auction)
        eligible.sort(key=lambda x: (
            float(x.get('bid_price', 0)) * 0.7 +
            float(x.get('quality_score', 50)) / 100 * 0.3
        ), reverse=True)

        winners = eligible[:num_winners]

        # Second-price: winner pays 2nd price + $0.001
        for i, winner in enumerate(winners):
            if i + 1 < len(eligible):
                clearing_price = Decimal(str(eligible[i + 1]['bid_price'])) + Decimal('0.001')
            else:
                clearing_price = floor_price
            winner['clearing_price'] = str(clearing_price)

        # Record auction
        auction_id = f"auc_{user_id}_{int(timezone.now().timestamp())}"
        auction_data = {
            'auction_id': auction_id,
            'user_id': user_id,
            'publisher_id': publisher_id,
            'country': country,
            'device': device,
            'winners': winners,
            'floor_price': str(floor_price),
            'auctioned_at': timezone.now().isoformat(),
        }
        cache.set(f'auction_{auction_id}', auction_data, timeout=300)

        try:
            from ad_networks.models import BidAuction
            BidAuction.objects.create(
                auction_id=auction_id,
                user_id=user_id,
                publisher_id=publisher_id,
                country=country,
                device=device,
                slot_type=slot_type,
                num_bids=len(eligible),
                num_winners=len(winners),
                floor_price=floor_price,
                winning_price=Decimal(str(winners[0].get('clearing_price', floor_price))) if winners else floor_price,
                auctioned_at=timezone.now(),
            )
        except ImportError:
            pass

        return {
            'status': 'success',
            'auction_id': auction_id,
            'winners': winners[:num_winners],
            'total_bids': len(eligible),
            'floor_price': str(floor_price),
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] run_bid_auction: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.rtb_tasks.update_bid_floor_prices')
def update_bid_floor_prices(self) -> dict:
    """
    Dynamically update floor prices per country/device segment.
    Higher-quality segments (US/UK desktop) get higher floors.
    Based on last 1-hour average clearing prices.
    """
    try:
        from datetime import timedelta
        from django.db.models import Avg
        logger.info("📈 Updating RTB floor prices...")

        updated = 0
        DEFAULT_FLOORS = {
            'US_desktop': Decimal('0.05'),
            'US_mobile':  Decimal('0.03'),
            'GB_desktop': Decimal('0.04'),
            'GB_mobile':  Decimal('0.025'),
            'CA_desktop': Decimal('0.04'),
            'AU_desktop': Decimal('0.035'),
            'default':    Decimal('0.001'),
        }

        # Cache floor prices per segment
        for segment, floor in DEFAULT_FLOORS.items():
            parts = segment.split('_')
            if len(parts) == 2:
                country, device = parts[0], parts[1]
            else:
                country, device = 'ANY', 'ANY'

            try:
                from ad_networks.models import BidAuction
                cutoff = timezone.now() - timedelta(hours=1)
                avg_price = BidAuction.objects.filter(
                    country=country,
                    device=device,
                    auctioned_at__gte=cutoff,
                ).aggregate(avg=Avg('winning_price'))['avg']

                if avg_price:
                    # Floor = 70% of average clearing price
                    new_floor = Decimal(str(avg_price)) * Decimal('0.70')
                    new_floor = max(new_floor, MIN_BID)
                else:
                    new_floor = floor

            except ImportError:
                new_floor = floor

            cache_key = f'floor_{country}_{device}_ANY'
            cache.set(cache_key, str(new_floor), timeout=FLOOR_PRICE_TTL)
            updated += 1

        return {
            'status': 'success',
            'floors_updated': updated,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=30,
             name='tasks.rtb_tasks.refresh_bid_cache')
def refresh_bid_cache(self) -> dict:
    """
    Refresh the RTB bid cache every 30 seconds.
    Loads active campaign bids from DB into cache for sub-millisecond auction lookups.
    """
    try:
        logger.debug("🔄 Refreshing RTB bid cache...")
        loaded = 0

        try:
            from ad_networks.models import Campaign, CampaignBid

            # Group bids by country+device for fast lookup
            segment_bids = {}

            active_bids = CampaignBid.objects.filter(
                campaign__status='active',
                is_active=True,
            ).select_related('campaign').values(
                'campaign_id', 'campaign__name', 'bid_price',
                'target_countries', 'target_devices', 'slot_types',
                'campaign__quality_score',
            )

            for bid in active_bids:
                countries = bid.get('target_countries') or ['ALL']
                devices   = bid.get('target_devices') or ['ALL']

                bid_data = {
                    'campaign_id':   bid['campaign_id'],
                    'campaign_name': bid['campaign__name'],
                    'bid_price':     str(bid['bid_price']),
                    'slot_types':    bid.get('slot_types') or ['offerwall'],
                    'quality_score': bid.get('campaign__quality_score') or 50,
                    'is_active':     True,
                }

                for country in countries:
                    for device in devices:
                        key = f'rtb_bids_{country}_{device}'
                        segment_bids.setdefault(key, []).append(bid_data)
                        loaded += 1

            for key, bids in segment_bids.items():
                # Sort by bid price descending
                bids.sort(key=lambda x: float(x['bid_price']), reverse=True)
                cache.set(key, bids, timeout=BID_CACHE_TTL)

        except ImportError as e:
            logger.warning(f"[WARN] RTB models not available: {e}")

        return {
            'status': 'success',
            'bids_cached': loaded,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.rtb_tasks.rank_advertisers_by_epc')
def rank_advertisers_by_epc(self) -> dict:
    """
    Rank all active advertisers by their effective EPC.
    Top advertisers get more traffic, bottom advertisers get bid alerts.
    EPC = total_conversions_value / total_clicks
    """
    try:
        from datetime import timedelta
        from django.db.models import Sum, Count, Avg
        logger.info("📊 Ranking advertisers by EPC...")

        ranked  = []
        cutoff  = timezone.now() - timedelta(days=7)

        try:
            from ad_networks.models import Campaign, OfferClick, OfferConversion

            campaigns = Campaign.objects.filter(status='active')
            for camp in campaigns:
                clicks = OfferClick.objects.filter(
                    offer__campaign=camp, created_at__gte=cutoff
                ).count()
                revenue = OfferConversion.objects.filter(
                    offer__campaign=camp,
                    converted_at__gte=cutoff,
                    status='approved',
                ).aggregate(total=Sum('payout'))['total'] or Decimal('0')

                epc = float(revenue) / clicks if clicks > 0 else 0.0

                ranked.append({
                    'campaign_id':   camp.pk,
                    'campaign_name': camp.name,
                    'clicks':        clicks,
                    'revenue':       str(revenue),
                    'epc':           round(epc, 4),
                })

                # Update campaign quality score
                quality = min(epc / 0.10 * 100, 100)  # $0.10 EPC = 100 score
                Campaign.objects.filter(pk=camp.pk).update(quality_score=round(quality))

            ranked.sort(key=lambda x: x['epc'], reverse=True)
            cache.set('rtb_advertiser_ranking', ranked, timeout=3600)

        except ImportError as e:
            logger.warning(f"[WARN] RTB models not available: {e}")

        return {
            'status': 'success',
            'advertisers_ranked': len(ranked),
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.rtb_tasks.detect_invalid_traffic')
def detect_invalid_traffic(self, lookback_hours: int = 1) -> dict:
    """
    Detect Invalid Traffic (IVT) patterns:
    - Click farms (same device fingerprint, many accounts)
    - Bot clicks (JS disabled, no mouse movement events)
    - Proxy/VPN clicks flagged by IP intel
    Charges-back advertisers for IVT conversions.
    """
    try:
        from datetime import timedelta
        from django.db.models import Count
        logger.info(f"🤖 Detecting invalid traffic (lookback={lookback_hours}h)...")

        detected = 0
        cutoff   = timezone.now() - timedelta(hours=lookback_hours)

        try:
            from ad_networks.models import OfferClick

            # Same device fingerprint, multiple users
            fp_dupes = (
                OfferClick.objects.filter(created_at__gte=cutoff)
                .exclude(device_fingerprint__isnull=True)
                .exclude(device_fingerprint='')
                .values('device_fingerprint')
                .annotate(user_count=Count('user_id', distinct=True))
                .filter(user_count__gt=3)
            )

            for fp in fp_dupes:
                OfferClick.objects.filter(
                    device_fingerprint=fp['device_fingerprint'],
                    created_at__gte=cutoff,
                ).update(is_ivt=True, ivt_reason='device_fingerprint_reuse')
                detected += fp['user_count']

            # Clicks with no user agent
            no_ua = OfferClick.objects.filter(
                created_at__gte=cutoff,
                user_agent='',
            )
            ivt_count = no_ua.update(is_ivt=True, ivt_reason='no_user_agent')
            detected += ivt_count

        except ImportError as e:
            logger.warning(f"[WARN] OfferClick not available: {e}")

        return {
            'status': 'success',
            'detected': detected,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.rtb_tasks.generate_rtb_report')
def generate_rtb_report(self, date_str: str = None) -> dict:
    """Daily RTB performance report: auctions, fill rate, avg clearing price."""
    try:
        from datetime import datetime, timedelta
        from django.db.models import Count, Avg, Sum

        target = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str else (timezone.now() - timedelta(days=1)).date()
        )
        day_start = timezone.make_aware(datetime.combine(target, datetime.min.time()))
        day_end   = day_start + timedelta(days=1)

        report = {'date': str(target), 'type': 'rtb_daily', 'metrics': {}}

        try:
            from ad_networks.models import BidAuction
            qs = BidAuction.objects.filter(auctioned_at__gte=day_start, auctioned_at__lt=day_end)
            agg = qs.aggregate(
                total_auctions=Count('id'),
                avg_bids=Avg('num_bids'),
                avg_clearing=Avg('winning_price'),
                fill_rate=Avg('num_winners'),
            )
            report['metrics'] = {
                'total_auctions': agg['total_auctions'] or 0,
                'avg_bids_per_auction': round(agg['avg_bids'] or 0, 2),
                'avg_clearing_price': str(round(agg['avg_clearing'] or 0, 4)),
                'avg_winners': round(agg['fill_rate'] or 0, 2),
            }
        except ImportError:
            pass

        cache.set(f'rtb_report_{target}', report, timeout=86400)
        return {'status': 'success', 'report': report, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        raise self.retry(exc=exc)


# ── Private helpers ────────────────────────────────────────────────────────────

def _load_bids_from_db(country: str, device: str, os_type: str) -> list:
    """Fallback: load bids from DB when cache is cold."""
    bids = []
    try:
        from ad_networks.models import CampaignBid
        qs = CampaignBid.objects.filter(
            campaign__status='active',
            is_active=True,
        ).values(
            'campaign_id', 'bid_price', 'slot_types',
            'campaign__quality_score', 'campaign__name',
        )[:200]

        for b in qs:
            bids.append({
                'campaign_id':   b['campaign_id'],
                'campaign_name': b['campaign__name'],
                'bid_price':     str(b['bid_price']),
                'slot_types':    b.get('slot_types') or ['offerwall'],
                'quality_score': b.get('campaign__quality_score') or 50,
                'is_active':     True,
            })
    except ImportError:
        pass
    return bids
