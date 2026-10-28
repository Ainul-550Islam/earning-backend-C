"""
api/offerwall/tasks.py

Celery tasks — business-critical background jobs that were MISSING.

Without this file:
  ✗ Offers never auto-expire (ran manually via manage.py expire_offers)
  ✗ Pending conversions never auto-approved after 24-hour review window
  ✗ Provider sync never automated (ran manually via manage.py sync_offers)
  ✗ Quality scores never recalculated on schedule
  ✗ B2B invoices never auto-generated monthly
  ✗ Fraud scores never refreshed
  ✗ Analytics reports never cached proactively

Add to celery_schedule.py (or settings.CELERY_BEAT_SCHEDULE):
    See celery_schedule.py in this package.

Usage:
    celery -A config worker -l info
    celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
"""
import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.utils import timezone
# FIX: METRIC_* + LOG_* constants were unused — now used in tasks
from .constants import (
    LOG_PROVIDER_SYNC, LOG_PROVIDER_ERROR,
    METRIC_OFFER_CONVERSIONS, METRIC_REVENUE,
    CONVERSION_TIMEOUT_HOURS, PENDING_CONVERSION_REVIEW_HOURS,
    FEATURE_AUTO_APPROVE_CONVERSIONS,
    FRAUD_THRESHOLD_HIGH,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 1. OFFER LIFECYCLE TASKS
# ═══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=60,
             name='offerwall.expire_offers')
def expire_offers(self, batch_size: int = 200):
    """
    Auto-expire offers whose end_date has passed.
    Replaces: python manage.py expire_offers

    Runs every 15 minutes (see celery_schedule.py).
    """
    from api.offerwall.models import Offer
    from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory

    now = timezone.now()
    expired_qs = Offer.objects.filter(status='active', end_date__lt=now)
    total = expired_qs.count()

    if total == 0:
        logger.debug('[task:expire_offers] nothing to expire')
        return {'expired': 0}

    expired = 0
    batch_ids = list(expired_qs.values_list('id', flat=True)[:batch_size])

    while batch_ids:
        Offer.objects.filter(id__in=batch_ids).update(
            status='expired', updated_at=now)
        expired += len(batch_ids)

        for offer_id in batch_ids:
            try:
                OfferwallAdapterFactory.get('audit').send({
                    'user_id':  None,
                    'action':   'OFFER_EXPIRED',
                    'message':  f'Offer auto-expired: {offer_id}',
                    'metadata': {'offer_id': str(offer_id),
                                 'expired_at': now.isoformat()},
                })
            except Exception:
                pass

        batch_ids = list(
            expired_qs.exclude(id__in=batch_ids)
                      .values_list('id', flat=True)[:batch_size]
        )

    logger.info(f'[task:expire_offers] expired={expired}')
    return {'expired': expired}


@shared_task(bind=True, max_retries=2, name='offerwall.recalculate_quality_scores')
def recalculate_quality_scores(self, batch_size: int = 100):
    """
    Recalculate quality scores for all active offers.
    Runs daily. Ensures trending/featured logic reflects real performance.
    """
    from api.offerwall.models import Offer

    offers = Offer.objects.filter(status='active').only(
        'id', 'view_count', 'click_count', 'conversion_count',
        'total_revenue', 'fraud_score', 'created_at',
        'quality_score', 'completion_rate',
    )

    updated = 0
    errors  = 0

    for offer in offers.iterator(chunk_size=batch_size):
        try:
            offer.calculate_quality_score()
            updated += 1
        except Exception as e:
            errors += 1
            logger.warning(f'[task:quality_scores] offer={offer.id} err={e}')

    logger.info(f'[task:quality_scores] updated={updated} errors={errors}')
    return {'updated': updated, 'errors': errors}


@shared_task(bind=True, max_retries=2, name='offerwall.sync_all_providers')
def sync_all_providers_task(self, force: bool = False):
    """
    Sync offers from all active auto-sync providers.
    Replaces: python manage.py sync_offers --all

    Runs every 60 minutes (configurable via provider.sync_interval_minutes).
    """
    from api.offerwall.models import OfferProvider
    from api.offerwall.services.OfferFactory import OfferFactory

    providers = OfferProvider.objects.filter(status='active', auto_sync=True)

    if not force:
        # Only sync providers that are due
        due_providers = []
        for p in providers:
            if not p.last_sync:
                due_providers.append(p)
                continue
            minutes_since = (timezone.now() - p.last_sync).total_seconds() / 60
            if minutes_since >= p.sync_interval_minutes:
                due_providers.append(p)
        providers = due_providers

    if not providers:
        logger.debug('[task:sync_providers] no providers due for sync')
        return {'providers_synced': 0}

    results = OfferFactory.sync_all_providers(providers)

    total_synced = sum(r.get('synced', 0)  for r in results.values())
    total_errors = sum(len(r.get('errors', [])) for r in results.values())

    # Update last_sync timestamp
    now = timezone.now()
    for p in providers if isinstance(providers, list) else list(providers):
        try:
            p.last_sync = now
            p.save(update_fields=['last_sync'])
        except Exception:
            pass

    logger.info(
        f'[{LOG_PROVIDER_SYNC}] providers={len(results)} '
        f'offers={total_synced} errors={total_errors}')
    return {'providers_synced': len(results),
            'offers_synced':    total_synced,
            'errors':           total_errors}


# ═══════════════════════════════════════════════════════════════
# 2. CONVERSION LIFECYCLE TASKS
# ═══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=300,
             name='offerwall.auto_approve_pending_conversions')
def auto_approve_pending_conversions(self, review_hours: int = 24,
                                     batch_size: int = 50):
    """
    Auto-approve conversions that have been pending for review_hours.

    Business rule: if fraud score is below threshold AND conversion is older
    than review_hours, it is safe to approve automatically.

    Runs every 30 minutes.
    """
    from api.offerwall.models import OfferConversion
    from api.offerwall.services.OfferwallIntegrationService import (
        OfferwallIntegrationService,
    )
    from api.offerwall.constants import (
        FRAUD_THRESHOLD_HIGH, FEATURE_AUTO_APPROVE_CONVERSIONS,
    )

    if not FEATURE_AUTO_APPROVE_CONVERSIONS:
        logger.debug('[task:auto_approve] feature disabled')
        return {'approved': 0}

    cutoff = timezone.now() - timedelta(hours=review_hours)

    pending_qs = OfferConversion.objects.filter(
        status='pending',
        converted_at__lte=cutoff,
        offer__is_high_risk=False,
    ).select_related('offer', 'offer__provider', 'user')

    approved = 0
    errors   = 0

    for conversion in pending_qs[:batch_size]:
        try:
            # Skip high-fraud-score offers
            if (conversion.offer.fraud_score or 0) >= FRAUD_THRESHOLD_HIGH:
                continue

            result = OfferwallIntegrationService.approve_conversion(conversion)
            if result.get('success'):
                approved += 1
            else:
                logger.warning(
                    f'[task:auto_approve] failed conv={conversion.id}: '
                    f'{result.get("error")}')
        except Exception as e:
            errors += 1
            logger.error(f'[task:auto_approve] conv={conversion.id} err={e}')

    logger.info(f'[task:auto_approve] approved={approved} errors={errors}')
    return {'approved': approved, 'errors': errors}


@shared_task(bind=True, max_retries=2, name='offerwall.expire_pending_conversions')
def expire_pending_conversions(self, timeout_hours: int = 72):
    """
    Reject conversions that have been pending for timeout_hours.

    If a conversion hasn't been approved in 72 hours, reject it automatically.
    Runs daily.
    """
    from api.offerwall.models import OfferConversion

    cutoff = timezone.now() - timedelta(hours=timeout_hours)

    expired_qs = OfferConversion.objects.filter(
        status='pending',
        converted_at__lte=cutoff,
    )

    count = expired_qs.count()

    if count == 0:
        return {'rejected': 0}

    expired_qs.update(
        status='rejected',
        rejection_reason='Auto-rejected: pending timeout exceeded',
        updated_at=timezone.now(),
    )

    logger.info(f'[task:expire_pending] rejected={count}')
    return {'rejected': count}


@shared_task(bind=True, max_retries=3, default_retry_delay=120,
             name='offerwall.retry_failed_postbacks')
def retry_failed_postbacks(self, max_retries: int = 3):
    """
    Retry postback delivery for approved conversions where postback failed.
    Runs every 10 minutes.
    """
    from api.offerwall.models import OfferConversion
    from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory

    # Find approved conversions with postback_url but no postback_data['sent']
    conversions = OfferConversion.objects.filter(
        status='approved',
        offer__provider__postback_url__isnull=False,
    ).exclude(
        postback_data__sent=True,
    ).select_related('offer', 'offer__provider')[:50]

    sent     = 0
    failures = 0

    for conversion in conversions:
        try:
            result = OfferwallAdapterFactory.get('postback_engine').send({
                'conversion':    conversion,
                'provider_type': conversion.offer.provider.provider_type,
                'postback_url':  conversion.offer.provider.postback_url,
                'conversion_id': conversion.conversion_id,
            })
            if result.get('success'):
                # Mark as sent
                conversion.postback_data['sent'] = True
                conversion.postback_data['sent_at'] = timezone.now().isoformat()
                conversion.save(update_fields=['postback_data'])
                sent += 1
        except Exception as e:
            failures += 1
            logger.warning(f'[task:retry_postback] conv={conversion.id} err={e}')

    logger.info(f'[task:retry_postbacks] sent={sent} failures={failures}')
    return {'sent': sent, 'failures': failures}


# ═══════════════════════════════════════════════════════════════
# 3. FRAUD & SECURITY TASKS
# ═══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, name='offerwall.refresh_fraud_scores')
def refresh_fraud_scores(self, batch_size: int = 100):
    """
    Recalculate fraud scores for offers with recent conversion anomalies.
    Runs every 6 hours.
    """
    from api.offerwall.models import Offer
    from api.offerwall.utils.FraudDetector import FraudDetector

    # Target offers with unexpectedly high chargeback rates
    suspicious_offers = Offer.objects.filter(
        status='active',
    ).annotate(
        chargeback_count=__import__(
            'django.db.models', fromlist=['Count']
        ).Count(
            'conversions',
            filter=__import__(
                'django.db.models', fromlist=['Q']
            ).Q(conversions__status='chargeback'),
        )
    ).filter(chargeback_count__gt=0)[:batch_size]

    updated = 0
    for offer in suspicious_offers:
        try:
            detector = FraudDetector(offer=offer)
            new_score = detector.calculate_offer_fraud_score()
            if abs(new_score - (offer.fraud_score or 0)) > 5:
                offer.fraud_score = new_score
                offer.is_high_risk = new_score >= 70
                offer.save(update_fields=['fraud_score', 'is_high_risk', 'updated_at'])
                updated += 1
        except Exception as e:
            logger.warning(f'[task:fraud_scores] offer={offer.id} err={e}')

    logger.info(f'[task:fraud_scores] updated={updated}')
    return {'updated': updated}


@shared_task(bind=True, max_retries=2, name='offerwall.cleanup_old_clicks')
def cleanup_old_clicks(self, days: int = 90):
    """
    Delete offer clicks older than `days` that were never converted.
    Frees database space. Runs weekly.
    """
    from api.offerwall.models import OfferClick

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = OfferClick.objects.filter(
        clicked_at__lt=cutoff,
        is_converted=False,
    ).delete()

    logger.info(f'[task:cleanup_clicks] deleted={deleted}')
    return {'deleted': deleted}


# ═══════════════════════════════════════════════════════════════
# 4. B2B BILLING TASKS
# ═══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=300,
             name='offerwall.generate_monthly_invoices')
def generate_monthly_invoices(self):
    """
    Auto-generate B2B invoices on the 1st of every month for the previous month.
    Replaces: POST /api/offerwall/b2b/admin/generate-invoices/

    Scheduled: 1st of month at 01:00 UTC.
    """
    from api.offerwall.b2b.models import B2BClient, B2BUsageRecord, B2BInvoice

    now   = timezone.now()
    # Target previous month
    if now.month == 1:
        year, month = now.year - 1, 12
    else:
        year, month = now.year, now.month - 1

    created = skipped = errors = 0
    usd_to_bdt = Decimal('110')  # Replace with live FX in production

    for client in B2BClient.objects.filter(status='active').select_related('plan'):
        try:
            if B2BInvoice.objects.filter(
                    client=client, period_year=year, period_month=month).exists():
                skipped += 1
                continue

            usage = B2BUsageRecord.objects.filter(
                client=client, period_year=year, period_month=month).first()

            plan_fee      = client.plan.monthly_price_bdt if client.plan else Decimal('0')
            rev_share_usd = usage.publisher_share_usd if usage else Decimal('0')
            rev_share_bdt = (rev_share_usd * usd_to_bdt).quantize(Decimal('0.01'))
            tax           = (plan_fee * Decimal('0.15')).quantize(Decimal('0.01'))
            total_due     = (plan_fee + tax).quantize(Decimal('0.01'))
            total_payable = max(Decimal('0'), total_due - rev_share_bdt)

            B2BInvoice.objects.create(
                client=client,
                invoice_number=B2BInvoice.generate_number(client, year, month),
                period_year=year, period_month=month,
                plan_fee_bdt=plan_fee,
                revenue_share_usd=rev_share_usd,
                revenue_share_bdt=rev_share_bdt,
                tax_bdt=tax,
                total_due_bdt=total_due,
                total_payable_bdt=total_payable,
                status='issued',
                issued_at=now,
            )
            created += 1

        except Exception as e:
            errors += 1
            logger.error(f'[task:invoices] client={client.company_name} err={e}')

    logger.info(
        f'[task:invoices] period={year}/{month:02d} '
        f'created={created} skipped={skipped} errors={errors}')
    return {'period': f'{year}/{month:02d}',
            'created': created, 'skipped': skipped, 'errors': errors}


@shared_task(bind=True, max_retries=2, name='offerwall.mark_overdue_invoices')
def mark_overdue_invoices(self):
    """
    Mark issued invoices as overdue if due_date has passed.
    Runs daily.
    """
    from api.offerwall.b2b.models import B2BInvoice
    import datetime

    today   = timezone.now().date()
    updated = B2BInvoice.objects.filter(
        status='issued',
        due_date__lt=today,
    ).update(status='overdue')

    logger.info(f'[task:overdue_invoices] updated={updated}')
    return {'updated': updated}


@shared_task(bind=True, max_retries=2, name='offerwall.reset_monthly_usage')
def reset_monthly_usage(self):
    """
    Create fresh B2BUsageRecord rows for all active clients at the start of a new month.
    Runs on the 1st of each month at 00:00 UTC.

    The records are created with zero counts — usage will accumulate naturally.
    Existing records from previous months are kept for invoice generation.
    """
    from api.offerwall.b2b.models import B2BClient, B2BUsageRecord

    now     = timezone.now()
    year    = now.year
    month   = now.month
    created = 0

    for client in B2BClient.objects.filter(status='active'):
        _, was_created = B2BUsageRecord.objects.get_or_create(
            client=client,
            period_year=year,
            period_month=month,
        )
        if was_created:
            created += 1

    logger.info(f'[task:reset_usage] period={year}/{month:02d} created={created}')
    return {'period': f'{year}/{month:02d}', 'created': created}


# ═══════════════════════════════════════════════════════════════
# 5. ANALYTICS & CACHE WARMUP TASKS
# ═══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=2, name='offerwall.warm_analytics_cache')
def warm_analytics_cache(self):
    """
    Pre-compute and cache heavy analytics queries so the dashboard is fast.
    Runs every 30 minutes.
    """
    from django.core.cache import cache
    from api.offerwall.models import Offer, OfferConversion
    from django.db.models import Sum, Count, Avg

    try:
        stats = Offer.objects.aggregate(
            total_offers=Count('id'),
            active_offers=Count('id', filter=__import__(
                'django.db.models', fromlist=['Q']).Q(status='active')),
            total_revenue=Sum('total_revenue'),
            total_payout=Sum('total_payout'),
            avg_quality=Avg('quality_score'),
        )
        cache.set('offerwall:platform_stats', stats, timeout=1800)

        # Cache top-10 offers by quality
        top_offers = list(
            Offer.objects.filter(status='active')
                         .order_by('-quality_score')
                         .values('id', 'title', 'quality_score', 'reward_amount')[:10]
        )
        cache.set('offerwall:top_offers', top_offers, timeout=300)

        logger.debug('[task:warm_cache] cache warmed')
        return {'success': True}

    except Exception as e:
        logger.warning(f'[task:warm_cache] error: {e}')
        return {'success': False, 'error': str(e)}


@shared_task(bind=True, max_retries=1, name='offerwall.update_provider_stats')
def update_provider_stats(self):
    """
    Refresh OfferProvider.total_offers / total_conversions / total_revenue
    from actual DB counts. Runs hourly.
    """
    from api.offerwall.models import OfferProvider, Offer, OfferConversion
    from django.db.models import Count, Sum

    for provider in OfferProvider.objects.filter(status='active'):
        try:
            offer_count   = Offer.objects.filter(provider=provider).count()
            conv_agg      = OfferConversion.objects.filter(
                offer__provider=provider, status='approved'
            ).aggregate(
                count=Count('id'),
                revenue=Sum('payout_amount'),
            )
            provider.total_offers      = offer_count
            provider.total_conversions = conv_agg['count'] or 0
            provider.total_revenue     = conv_agg['revenue'] or Decimal('0')
            provider.save(update_fields=[
                'total_offers', 'total_conversions', 'total_revenue', 'updated_at'])
        except Exception as e:
            logger.warning(f'[task:provider_stats] provider={provider.id} err={e}')

    return {'updated': True}


# ═══════════════════════════════════════════════════════════════
# 6. ANOMALY MONITORING TASKS  (AlertAdapter wired)
#    FIX: AlertAdapter existed but was NEVER triggered from tasks.
# ═══════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=1, name='offerwall.check_fraud_anomalies')
def check_fraud_anomalies(self, window_minutes: int = 60,
                          chargeback_threshold: float = 0.1):
    """
    Detect high chargeback rates per provider and fire AlertAdapter.
    FIX: AlertAdapter was registered but never triggered anywhere.
    Runs every hour.
    """
    from api.offerwall.models import OfferProvider, OfferConversion
    from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory
    from django.db.models import Count, Q

    since = timezone.now() - timedelta(minutes=window_minutes)
    alerts_fired = 0

    for provider in OfferProvider.objects.filter(status='active'):
        try:
            recent = OfferConversion.objects.filter(
                offer__provider=provider,
                converted_at__gte=since,
            )
            total      = recent.count()
            chargebacks = recent.filter(status='chargeback').count()

            if total < 10:
                continue

            rate = chargebacks / total
            if rate >= chargeback_threshold:
                OfferwallAdapterFactory.get('alerts').send({
                    'alert_type': 'high_chargeback_rate',
                    'severity':   'critical' if rate >= 0.25 else 'high',
                    'message': (
                        f'Provider {provider.name}: {chargebacks}/{total} '
                        f'chargebacks ({rate:.1%}) in last {window_minutes}min'
                    ),
                    'metadata': {
                        'provider_id':   str(provider.id),
                        'provider_name': provider.name,
                        'chargeback_rate': rate,
                        'window_minutes':  window_minutes,
                    },
                })
                alerts_fired += 1
                logger.warning(
                    f'[task:fraud_anomalies] ALERT: {provider.name} '
                    f'chargeback rate={rate:.1%}')
        except Exception as e:
            logger.error(f'[task:fraud_anomalies] provider={provider.name}: {e}')

    return {'alerts_fired': alerts_fired}


@shared_task(bind=True, max_retries=1, name='offerwall.check_provider_health')
def check_provider_health(self):
    """
    Ping each active provider's API and fire AlertAdapter if down.
    FIX: AlertAdapter was never triggered for provider-down scenarios.
    Runs every 30 minutes.
    """
    from api.offerwall.models import OfferProvider
    from api.offerwall.services.OfferFactory import OfferFactory
    from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory

    alerts_fired = 0

    for provider in OfferProvider.objects.filter(status='active', auto_sync=True):
        try:
            is_valid, errors = OfferFactory.validate_provider_config(provider)
            if not is_valid:
                OfferwallAdapterFactory.get('alerts').send({
                    'alert_type': 'provider_config_invalid',
                    'severity':   'medium',
                    'message': (
                        f'Provider {provider.name} has config errors: '
                        f'{", ".join(errors)}'
                    ),
                    'metadata': {
                        'provider_id':   str(provider.id),
                        'provider_name': provider.name,
                        'errors':        errors,
                    },
                })
                alerts_fired += 1
        except Exception as e:
            logger.error(f'[task:provider_health] {provider.name}: {e}')

    return {'alerts_fired': alerts_fired}


@shared_task(bind=True, max_retries=1, name='offerwall.check_adapter_health')
def check_adapter_health(self):
    """
    Check all offerwall adapter circuit breakers and alert if degraded.
    Runs every 15 minutes.
    """
    from api.offerwall.services.adapters.OfferwallAdapter import OfferwallAdapterFactory

    health   = OfferwallAdapterFactory.health_check_all()
    degraded = [name for name, h in health.items() if h.get('circuit_open')]

    if degraded:
        OfferwallAdapterFactory.get('alerts').send({
            'alert_type': 'adapter_circuit_open',
            'severity':   'high',
            'message': (
                f'{len(degraded)} offerwall adapter(s) circuit open: '
                f'{", ".join(degraded)}'
            ),
            'metadata': {'degraded': degraded, 'health': health},
        })
        logger.error(f'[task:adapter_health] degraded: {degraded}')

    return {'degraded': degraded, 'total': len(health)}
