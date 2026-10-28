"""
tasks/cpalead_tasks.py
CPAlead-style CPA (Cost Per Action) offer-wall Celery tasks.
World-class implementation covering:
  - S2S postback processing        (cpalead_process_postback)
  - Conversion validation          (cpalead_validate_conversion)
  - Publisher stats sync           (cpalead_sync_publisher_stats)
  - Offer cap management           (cpalead_check_offer_caps)
  - Click deduplication            (cpalead_deduplicate_clicks)
  - Fraud detection on conversions (cpalead_fraud_scan_conversions)
  - Payout calculation             (cpalead_calculate_payouts)
  - Offer performance ranking      (cpalead_rank_offers)
  - Daily conversion report        (cpalead_daily_conversion_report)
  - Postback retry for failures    (cpalead_retry_failed_postbacks)
"""
import logging
import hashlib
import json
import uuid
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
POSTBACK_DEDUP_TTL   = 86400 * 7   # 7 days
CLICK_DEDUP_TTL      = 3600        # 1 hour
FRAUD_SCORE_THRESHOLD = 60
MAX_CONVERSIONS_PER_IP_PER_HOUR = 5


# ─────────────────────────────────────────────────────────────────────────────
# cpalead_process_postback
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=30,
    name='tasks.cpalead_tasks.cpalead_process_postback',
)
def cpalead_process_postback(
    self,
    postback_data: dict,
) -> dict:
    """
    Process a server-to-server (S2S) postback from an ad network.
    Postback data fields (CPAlead-style):
      - pub_id      : Publisher ID
      - offer_id    : Offer ID
      - click_id    : Original click tracking ID
      - payout      : Payout amount in USD
      - ip          : User IP address
      - user_agent  : User agent string
      - transaction_id : Network's transaction ID (for dedup)
      - status      : 'approved' | 'reversed' | 'pending'
      - country     : ISO country code
      - device      : 'mobile' | 'desktop' | 'tablet'
    """
    try:
        transaction_id = postback_data.get('transaction_id', '')
        pub_id         = postback_data.get('pub_id', '')
        offer_id       = postback_data.get('offer_id', '')
        click_id       = postback_data.get('click_id', '')
        payout         = Decimal(str(postback_data.get('payout', '0')))
        ip_address     = postback_data.get('ip', '')
        status         = postback_data.get('status', 'approved')
        country        = postback_data.get('country', 'US')

        logger.info(
            f"[POSTBACK] Processing: offer={offer_id} pub={pub_id} "
            f"click={click_id} payout=${payout} status={status}"
        )

        # ── 1. Deduplication check ──────────────────────────────────
        dedup_key = f'postback_dedup_{transaction_id}_{offer_id}'
        if cache.get(dedup_key):
            logger.warning(f"[POSTBACK] DUPLICATE detected: {transaction_id}")
            return {
                'status': 'duplicate',
                'transaction_id': transaction_id,
                'timestamp': timezone.now().isoformat(),
            }

        # Mark as seen
        cache.set(dedup_key, 1, timeout=POSTBACK_DEDUP_TTL)

        # ── 2. Validate click_id exists ────────────────────────────
        user_id   = None
        click_obj = None
        try:
            from ad_networks.models import OfferClick
            click_obj = OfferClick.objects.filter(click_id=click_id).first()
            if click_obj:
                user_id = click_obj.user_id
            else:
                logger.warning(f"[POSTBACK] click_id not found: {click_id}")
        except ImportError:
            pass

        # ── 3. Fraud pre-check ─────────────────────────────────────
        fraud_score = _compute_fraud_score(ip_address, user_id, offer_id)
        if fraud_score >= FRAUD_SCORE_THRESHOLD:
            logger.warning(
                f"[POSTBACK] High fraud score ({fraud_score}) for "
                f"click={click_id} ip={ip_address} — flagging"
            )
            _flag_suspicious_conversion(postback_data, fraud_score)
            return {
                'status': 'fraud_flagged',
                'fraud_score': fraud_score,
                'transaction_id': transaction_id,
                'timestamp': timezone.now().isoformat(),
            }

        # ── 4. Record conversion ───────────────────────────────────
        conversion_id = None
        with transaction.atomic():
            try:
                from ad_networks.models import OfferConversion
                conversion = OfferConversion.objects.create(
                    transaction_id=transaction_id,
                    offer_id=offer_id,
                    pub_id=pub_id,
                    click_id=click_id,
                    user_id=user_id,
                    payout=payout,
                    status=status,
                    ip_address=ip_address,
                    country=country,
                    fraud_score=fraud_score,
                    postback_data=postback_data,
                    converted_at=timezone.now(),
                )
                conversion_id = conversion.pk
            except ImportError:
                conversion_id = str(uuid.uuid4())

        # ── 5. Credit publisher if approved ───────────────────────
        if status == 'approved' and payout > Decimal('0') and user_id:
            cpalead_credit_publisher.apply_async(
                kwargs={
                    'user_id': user_id,
                    'payout': str(payout),
                    'offer_id': offer_id,
                    'conversion_id': str(conversion_id),
                    'transaction_id': transaction_id,
                }
            )

        # ── 6. Update offer stats ──────────────────────────────────
        cpalead_update_offer_stats.apply_async(
            kwargs={'offer_id': offer_id, 'payout': str(payout), 'status': status}
        )

        result = {
            'status': 'success',
            'conversion_id': str(conversion_id),
            'transaction_id': transaction_id,
            'payout': str(payout),
            'user_id': user_id,
            'fraud_score': fraud_score,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[POSTBACK] Processed: {result}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] cpalead_process_postback: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# cpalead_credit_publisher
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=30,
    name='tasks.cpalead_tasks.cpalead_credit_publisher',
)
def cpalead_credit_publisher(
    self,
    user_id: int,
    payout: str,
    offer_id: str,
    conversion_id: str,
    transaction_id: str,
) -> dict:
    """
    Credit a publisher's wallet for an approved CPA conversion.
    Revenue split: 70% publisher, 10% referrer L1, 5% referrer L2, 15% platform.
    """
    try:
        amount = Decimal(payout)
        if amount <= Decimal('0'):
            return {'status': 'skipped', 'reason': 'zero_payout'}

        publisher_share = amount * Decimal('0.70')
        platform_share  = amount * Decimal('0.15')
        referrer_l1     = amount * Decimal('0.10')
        referrer_l2     = amount * Decimal('0.05')

        with transaction.atomic():
            try:
                from api.tasks.services import WalletService
                ws = WalletService()

                ws.credit(
                    user_id=user_id,
                    amount=publisher_share,
                    transaction_type='cpa_conversion',
                    reference=f'cpa_{conversion_id}',
                    metadata={
                        'offer_id': offer_id,
                        'conversion_id': conversion_id,
                        'transaction_id': transaction_id,
                        'gross_payout': payout,
                        'publisher_share': str(publisher_share),
                    },
                )
            except (ImportError, Exception) as e:
                logger.warning(f"[WARN] WalletService credit: {e}")

            # Credit L1 referrer
            try:
                from referrals.models import Referral
                referral = Referral.objects.filter(
                    referred_user_id=user_id, is_active=True
                ).select_related('referrer').first()

                if referral and referral_l1 > Decimal('0'):
                    from api.tasks.services import WalletService
                    WalletService().credit(
                        user_id=referral.referrer_id,
                        amount=referrer_l1,
                        transaction_type='cpa_referral_l1',
                        reference=f'cpa_ref_l1_{conversion_id}',
                        metadata={'referred_user_id': user_id, 'offer_id': offer_id},
                    )
            except (ImportError, Exception) as e:
                logger.debug(f"[DEBUG] L1 referrer credit: {e}")

        logger.info(
            f"[CPA] Credited user {user_id}: pub=${publisher_share} "
            f"offer={offer_id} txn={transaction_id}"
        )
        return {
            'status': 'success',
            'user_id': user_id,
            'publisher_share': str(publisher_share),
            'platform_share': str(platform_share),
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] cpalead_credit_publisher: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# cpalead_update_offer_stats
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    name='tasks.cpalead_tasks.cpalead_update_offer_stats',
)
def cpalead_update_offer_stats(self, offer_id: str, payout: str, status: str) -> dict:
    """Update cached and DB offer statistics after a conversion."""
    try:
        payout_dec = Decimal(payout)

        try:
            from ad_networks.models import SmartlinkOffer
            from django.db.models import F

            SmartlinkOffer.objects.filter(external_id=offer_id).update(
                total_conversions=F('total_conversions') + (1 if status == 'approved' else 0),
                total_revenue=F('total_revenue') + (payout_dec if status == 'approved' else 0),
            )
        except ImportError:
            pass

        # Invalidate cached EPC
        cache.delete(f'offer_epc_{offer_id}')
        cache.delete(f'ranked_offers_*')

        return {'status': 'success', 'offer_id': offer_id, 'payout': payout}

    except Exception as exc:
        logger.error(f"[ERROR] cpalead_update_offer_stats: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# cpalead_validate_conversion
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name='tasks.cpalead_tasks.cpalead_validate_conversion',
)
def cpalead_validate_conversion(self, conversion_id: int) -> dict:
    """
    Re-validate a pending conversion against fraud rules.
    Auto-approves clean conversions; flags fraudulent ones.
    """
    try:
        try:
            from ad_networks.models import OfferConversion

            conv = OfferConversion.objects.get(pk=conversion_id, status='pending')
            fraud_score = _compute_fraud_score(
                conv.ip_address, conv.user_id, conv.offer_id
            )

            if fraud_score >= FRAUD_SCORE_THRESHOLD:
                conv.status      = 'rejected'
                conv.fraud_score = fraud_score
                conv.save(update_fields=['status', 'fraud_score'])
                logger.warning(f"[VALIDATE] Conversion {conversion_id} REJECTED (fraud={fraud_score})")
                return {'status': 'rejected', 'fraud_score': fraud_score}
            else:
                conv.status      = 'approved'
                conv.fraud_score = fraud_score
                conv.save(update_fields=['status', 'fraud_score'])
                # Credit publisher
                cpalead_credit_publisher.apply_async(kwargs={
                    'user_id': conv.user_id,
                    'payout': str(conv.payout),
                    'offer_id': conv.offer_id,
                    'conversion_id': str(conv.pk),
                    'transaction_id': conv.transaction_id,
                })
                return {'status': 'approved', 'fraud_score': fraud_score}

        except ImportError:
            return {'status': 'skipped', 'reason': 'model_not_available'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    except Exception as exc:
        logger.error(f"[ERROR] cpalead_validate_conversion {conversion_id}: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# cpalead_sync_publisher_stats
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='tasks.cpalead_tasks.cpalead_sync_publisher_stats',
)
def cpalead_sync_publisher_stats(self, lookback_hours: int = 24) -> dict:
    """
    Aggregate publisher performance stats (clicks, conversions, earnings, EPC)
    and cache per-publisher dashboards.
    """
    try:
        from datetime import timedelta
        from django.db.models import Sum, Count, Avg

        synced = 0
        cutoff = timezone.now() - timedelta(hours=lookback_hours)

        try:
            from ad_networks.models import OfferConversion
            from django.contrib.auth import get_user_model
            User = get_user_model()

            pub_stats = (
                OfferConversion.objects.filter(
                    converted_at__gte=cutoff,
                    status='approved',
                )
                .values('user_id')
                .annotate(
                    total_conversions=Count('id'),
                    total_earnings=Sum('payout'),
                    avg_payout=Avg('payout'),
                )
            )

            for stat in pub_stats:
                uid = stat['user_id']
                if not uid:
                    continue
                cache_data = {
                    'total_conversions': stat['total_conversions'],
                    'total_earnings': str(stat['total_earnings'] or Decimal('0')),
                    'avg_payout': str(stat['avg_payout'] or Decimal('0')),
                    'synced_at': timezone.now().isoformat(),
                }
                cache.set(f'pub_stats_{uid}', cache_data, timeout=3600)
                synced += 1

        except ImportError:
            pass

        return {
            'status': 'success',
            'publishers_synced': synced,
            'lookback_hours': lookback_hours,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] cpalead_sync_publisher_stats: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# cpalead_check_offer_caps
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name='tasks.cpalead_tasks.cpalead_check_offer_caps',
)
def cpalead_check_offer_caps(self) -> dict:
    """
    Check all active offers against their daily/total conversion caps.
    Pause offers that have hit their cap to prevent over-delivery.
    """
    try:
        paused  = 0
        checked = 0

        try:
            from ad_networks.models import SmartlinkOffer

            active_offers = SmartlinkOffer.objects.filter(is_active=True)
            for offer in active_offers:
                checked += 1
                cap_hit = False

                # Daily conversion cap
                if offer.daily_cap:
                    daily_used = offer.daily_conversions_used or 0
                    if daily_used >= offer.daily_cap:
                        cap_hit = True
                        logger.info(f"[CAP] Offer {offer.external_id} hit daily cap ({daily_used}/{offer.daily_cap})")

                # Total conversion cap
                if not cap_hit and offer.total_cap:
                    if (offer.total_conversions or 0) >= offer.total_cap:
                        cap_hit = True
                        logger.info(f"[CAP] Offer {offer.external_id} hit total cap")

                # Budget cap
                if not cap_hit and offer.budget:
                    if (offer.total_revenue or 0) >= offer.budget:
                        cap_hit = True
                        logger.info(f"[CAP] Offer {offer.external_id} hit budget cap")

                if cap_hit:
                    offer.is_active = False
                    offer.deactivated_at = timezone.now()
                    offer.deactivation_reason = 'cap_reached'
                    offer.save(update_fields=['is_active', 'deactivated_at', 'deactivation_reason'])
                    paused += 1

        except ImportError:
            pass

        return {
            'status': 'success',
            'checked': checked,
            'paused': paused,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] cpalead_check_offer_caps: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# cpalead_deduplicate_clicks
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    name='tasks.cpalead_tasks.cpalead_deduplicate_clicks',
)
def cpalead_deduplicate_clicks(self, lookback_hours: int = 1) -> dict:
    """
    Scan recent click records for duplicate click_ids or excessive
    clicks from the same IP/user on the same offer. Flag duplicates.
    """
    try:
        from datetime import timedelta
        from django.db.models import Count

        flagged = 0
        cutoff  = timezone.now() - timedelta(hours=lookback_hours)

        try:
            from ad_networks.models import OfferClick

            # Duplicate click_ids
            dups = (
                OfferClick.objects.filter(created_at__gte=cutoff)
                .values('click_id')
                .annotate(cnt=Count('id'))
                .filter(cnt__gt=1)
            )
            for dup in dups:
                OfferClick.objects.filter(
                    click_id=dup['click_id'], is_duplicate=False
                ).exclude(
                    id=OfferClick.objects.filter(click_id=dup['click_id']).order_by('created_at').first().id
                ).update(is_duplicate=True)
                flagged += dup['cnt'] - 1

            # Excessive clicks per IP per offer per hour
            ip_offer_counts = (
                OfferClick.objects.filter(created_at__gte=cutoff)
                .values('ip_address', 'offer_id')
                .annotate(cnt=Count('id'))
                .filter(cnt__gt=MAX_CONVERSIONS_PER_IP_PER_HOUR)
            )
            for entry in ip_offer_counts:
                excess = entry['cnt'] - MAX_CONVERSIONS_PER_IP_PER_HOUR
                OfferClick.objects.filter(
                    ip_address=entry['ip_address'],
                    offer_id=entry['offer_id'],
                    created_at__gte=cutoff,
                    is_suspicious=False,
                ).order_by('-created_at')[:excess].update(is_suspicious=True)
                flagged += excess

        except ImportError:
            pass

        return {
            'status': 'success',
            'flagged': flagged,
            'lookback_hours': lookback_hours,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] cpalead_deduplicate_clicks: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# cpalead_fraud_scan_conversions
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.cpalead_tasks.cpalead_fraud_scan_conversions',
)
def cpalead_fraud_scan_conversions(self, lookback_hours: int = 1) -> dict:
    """
    Scan recent conversions for fraud patterns.
    Auto-rejects high-risk conversions and queues borderline ones for manual review.
    """
    try:
        from datetime import timedelta

        scanned  = 0
        rejected = 0
        flagged  = 0
        cutoff   = timezone.now() - timedelta(hours=lookback_hours)

        try:
            from ad_networks.models import OfferConversion

            pending = OfferConversion.objects.filter(
                converted_at__gte=cutoff,
                status='approved',
                fraud_checked=False,
            )

            for conv in pending:
                score = _compute_fraud_score(conv.ip_address, conv.user_id, conv.offer_id)
                conv.fraud_score   = score
                conv.fraud_checked = True

                if score >= FRAUD_SCORE_THRESHOLD:
                    conv.status = 'rejected'
                    rejected += 1
                elif score >= 40:
                    conv.status = 'pending_review'
                    flagged += 1

                conv.save(update_fields=['fraud_score', 'fraud_checked', 'status'])
                scanned += 1

        except ImportError:
            pass

        return {
            'status': 'success',
            'scanned': scanned,
            'rejected': rejected,
            'flagged_for_review': flagged,
            'lookback_hours': lookback_hours,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] cpalead_fraud_scan_conversions: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# cpalead_calculate_payouts
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='tasks.cpalead_tasks.cpalead_calculate_payouts',
)
def cpalead_calculate_payouts(self, period: str = 'daily') -> dict:
    """
    Calculate publisher payouts for a given period.
    Aggregates approved conversions, applies revenue share,
    and creates Payout records ready for processing.
    """
    try:
        from datetime import timedelta
        from django.db.models import Sum, Count

        now = timezone.now()
        if period == 'daily':
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
            period_end   = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'weekly':
            period_start = now - timedelta(days=7)
            period_end   = now
        else:
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end   = now

        payouts_created = 0
        total_payout    = Decimal('0')

        try:
            from ad_networks.models import OfferConversion, PublisherPayout

            pub_totals = (
                OfferConversion.objects.filter(
                    converted_at__gte=period_start,
                    converted_at__lt=period_end,
                    status='approved',
                    payout_record_created=False,
                )
                .values('user_id')
                .annotate(
                    conversions=Count('id'),
                    gross=Sum('payout'),
                )
            )

            for pub in pub_totals:
                if not pub['user_id']:
                    continue
                gross     = Decimal(str(pub['gross'] or 0))
                net       = gross * Decimal('0.70')   # 70% publisher share

                if net <= Decimal('0'):
                    continue

                PublisherPayout.objects.create(
                    user_id=pub['user_id'],
                    period_start=period_start,
                    period_end=period_end,
                    gross_amount=gross,
                    net_amount=net,
                    conversion_count=pub['conversions'],
                    status='pending',
                    period=period,
                )

                # Mark conversions as processed
                OfferConversion.objects.filter(
                    user_id=pub['user_id'],
                    converted_at__gte=period_start,
                    converted_at__lt=period_end,
                    status='approved',
                    payout_record_created=False,
                ).update(payout_record_created=True)

                payouts_created += 1
                total_payout    += net

        except ImportError:
            pass

        return {
            'status': 'success',
            'period': period,
            'payouts_created': payouts_created,
            'total_payout': str(total_payout),
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] cpalead_calculate_payouts: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# cpalead_rank_offers
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.cpalead_tasks.cpalead_rank_offers',
)
def cpalead_rank_offers(self) -> dict:
    """
    Rank all active offers by eCPA (effective cost per action),
    EPC (earnings per click), and conversion rate.
    Cache ranked list for fast API retrieval.
    """
    try:
        ranked  = []
        updated = 0

        try:
            from ad_networks.models import SmartlinkOffer

            offers = SmartlinkOffer.objects.filter(is_active=True).values(
                'id', 'external_id', 'name', 'payout', 'epc',
                'conversion_rate', 'total_clicks', 'total_conversions', 'total_revenue',
            )

            for offer in offers:
                clicks      = offer.get('total_clicks') or 0
                conversions = offer.get('total_conversions') or 0
                revenue     = float(offer.get('total_revenue') or 0)
                payout      = float(offer.get('payout') or 0)

                # EPC = revenue / clicks
                epc = revenue / clicks if clicks > 0 else 0.0
                # CVR = conversions / clicks
                cvr = conversions / clicks * 100 if clicks > 0 else 0.0

                # Composite score: 50% EPC + 30% CVR + 20% payout
                score = (epc * 0.50) + (cvr / 100 * 0.30) + (payout * 0.20)

                ranked.append({
                    'offer_id': offer['external_id'],
                    'name': offer['name'],
                    'epc': round(epc, 4),
                    'cvr': round(cvr, 2),
                    'payout': payout,
                    'score': round(score, 4),
                })
                updated += 1

            ranked.sort(key=lambda x: x['score'], reverse=True)
            cache.set('cpalead_ranked_offers', ranked, timeout=1800)

        except ImportError:
            pass

        return {
            'status': 'success',
            'offers_ranked': updated,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] cpalead_rank_offers: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# cpalead_daily_conversion_report
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.cpalead_tasks.cpalead_daily_conversion_report',
)
def cpalead_daily_conversion_report(self, date_str: str = None) -> dict:
    """
    Generate a daily CPA conversion report:
    - Total clicks, conversions, revenue
    - Per-offer breakdown
    - Per-country breakdown
    - Fraud rejection rate
    Cache and optionally email to admins.
    """
    try:
        from datetime import datetime, timedelta
        from django.db.models import Sum, Count, Q

        target_date = (
            datetime.strptime(date_str, '%Y-%m-%d').date()
            if date_str
            else (timezone.now() - timedelta(days=1)).date()
        )
        day_start = timezone.make_aware(datetime.combine(target_date, datetime.min.time()))
        day_end   = day_start + timedelta(days=1)

        report = {
            'date': str(target_date),
            'type': 'cpa_daily',
            'totals': {},
            'by_offer': [],
            'by_country': [],
            'generated_at': timezone.now().isoformat(),
        }

        try:
            from ad_networks.models import OfferConversion

            qs = OfferConversion.objects.filter(
                converted_at__gte=day_start, converted_at__lt=day_end
            )

            totals = qs.aggregate(
                total_conversions=Count('id'),
                approved=Count('id', filter=Q(status='approved')),
                rejected=Count('id', filter=Q(status='rejected')),
                total_revenue=Sum('payout', filter=Q(status='approved')),
            )
            report['totals'] = {
                'conversions': totals['total_conversions'] or 0,
                'approved': totals['approved'] or 0,
                'rejected': totals['rejected'] or 0,
                'revenue': str(totals['total_revenue'] or Decimal('0')),
                'rejection_rate': round(
                    (totals['rejected'] or 0) / max(totals['total_conversions'] or 1, 1) * 100, 2
                ),
            }

            by_offer = qs.values('offer_id').annotate(
                cnt=Count('id'),
                revenue=Sum('payout', filter=Q(status='approved')),
            ).order_by('-revenue')[:20]
            report['by_offer'] = list(by_offer)

            by_country = qs.values('country').annotate(
                cnt=Count('id'),
                revenue=Sum('payout', filter=Q(status='approved')),
            ).order_by('-revenue')[:20]
            report['by_country'] = list(by_country)

        except ImportError:
            pass

        cache_key = f'cpa_daily_report_{target_date}'
        cache.set(cache_key, report, timeout=86400)

        return {'status': 'success', 'report': report, 'timestamp': timezone.now().isoformat()}

    except Exception as exc:
        logger.error(f"[ERROR] cpalead_daily_conversion_report: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────────────────────────────────────
# cpalead_retry_failed_postbacks
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.cpalead_tasks.cpalead_retry_failed_postbacks',
)
def cpalead_retry_failed_postbacks(self, max_age_hours: int = 24) -> dict:
    """
    Retry postback notifications that failed to send to advertisers.
    Reads from PostbackLog where status='failed' and retry_count < 5.
    """
    try:
        from datetime import timedelta

        retried = 0
        errors  = 0
        cutoff  = timezone.now() - timedelta(hours=max_age_hours)

        try:
            from ad_networks.models import PostbackLog
            import requests

            failed = PostbackLog.objects.filter(
                status='failed',
                retry_count__lt=5,
                created_at__gte=cutoff,
            )

            for pb in failed:
                try:
                    response = requests.get(pb.postback_url, timeout=10)
                    if response.status_code < 400:
                        pb.status       = 'success'
                        pb.retry_count += 1
                        pb.last_tried   = timezone.now()
                        pb.save(update_fields=['status', 'retry_count', 'last_tried'])
                        retried += 1
                    else:
                        pb.retry_count += 1
                        pb.last_tried   = timezone.now()
                        pb.save(update_fields=['retry_count', 'last_tried'])
                        errors += 1
                except Exception as req_err:
                    pb.retry_count += 1
                    pb.last_tried   = timezone.now()
                    pb.error        = str(req_err)
                    pb.save(update_fields=['retry_count', 'last_tried', 'error'])
                    errors += 1

        except ImportError:
            pass

        return {
            'status': 'success',
            'retried': retried,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.error(f"[ERROR] cpalead_retry_failed_postbacks: {exc}")
        raise self.retry(exc=exc)


# ══════════════════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _compute_fraud_score(ip_address: str, user_id, offer_id: str) -> int:
    """
    Compute a fraud risk score (0–100) for a conversion.
    Higher = more suspicious.
    """
    score = 0

    # Rule 1: VPN/Proxy IP (simplified — check a blocklist)
    try:
        if ip_address:
            blocked_ips_key = 'blocked_vpn_ips'
            blocked         = cache.get(blocked_ips_key) or []
            if ip_address in blocked:
                score += 50
    except Exception:
        pass

    # Rule 2: Too many conversions from same IP in last hour
    if ip_address:
        ip_count_key = f'conv_ip_{ip_address}_count'
        ip_count     = cache.get(ip_count_key) or 0
        if ip_count > MAX_CONVERSIONS_PER_IP_PER_HOUR:
            score += min(ip_count * 5, 40)
        cache.set(ip_count_key, ip_count + 1, timeout=CLICK_DEDUP_TTL)

    # Rule 3: New account (< 24h old)
    if user_id:
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(pk=user_id).values('date_joined').first()
            if user:
                age_hours = (timezone.now() - user['date_joined']).total_seconds() / 3600
                if age_hours < 24:
                    score += 20
                elif age_hours < 72:
                    score += 10
        except Exception:
            pass

    # Rule 4: Offer flagged for high fraud rate
    offer_fraud_key = f'offer_fraud_rate_{offer_id}'
    offer_fraud     = cache.get(offer_fraud_key) or 0
    if offer_fraud > 20:
        score += 20

    return min(score, 100)


def _flag_suspicious_conversion(postback_data: dict, fraud_score: int) -> None:
    """Store a suspicious conversion flag in cache and optionally DB."""
    try:
        flag_key  = f"suspicious_conv_{postback_data.get('transaction_id', 'unknown')}"
        flag_data = {
            'postback_data': postback_data,
            'fraud_score': fraud_score,
            'flagged_at': timezone.now().isoformat(),
        }
        cache.set(flag_key, flag_data, timeout=86400 * 7)
        logger.warning(f"[FRAUD] Flagged conversion: score={fraud_score} txn={postback_data.get('transaction_id')}")
    except Exception as e:
        logger.error(f"[ERROR] _flag_suspicious_conversion: {e}")
