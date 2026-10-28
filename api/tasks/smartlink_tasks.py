"""
tasks/smartlink_tasks.py
Smartlink / offer-wall related Celery tasks:
  - recalculate_epc         – recalculate Earnings Per Click
  - reset_daily_caps        – reset offer daily click/conversion caps
  - sync_smartlink_stats    – pull fresh stats from ad-network APIs
  - cleanup_expired_offers  – deactivate expired smartlink offers
"""
from django.db import models
import logging
from decimal import Decimal
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# recalculate_epc
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='tasks.smartlink_tasks.recalculate_epc',
)
def recalculate_epc(self, offer_ids: list = None) -> dict:
    """
    Recalculate EPC (Earnings Per Click) for smartlink offers.
    EPC = total_revenue / total_clicks (over a rolling 7-day window).
    If offer_ids is provided, only recalculate those offers.
    """
    try:
        from datetime import timedelta
        logger.info(f"📊 Recalculating EPC (offer_ids={offer_ids or 'all'})...")

        updated = 0
        errors  = 0
        window  = timezone.now() - timedelta(days=7)

        try:
            from ad_networks.models import SmartlinkOffer, SmartlinkClick
            from django.db.models import Sum, Count

            qs = SmartlinkOffer.objects.filter(is_active=True)
            if offer_ids:
                qs = qs.filter(id__in=offer_ids)

            for offer in qs.iterator(chunk_size=50):
                try:
                    with transaction.atomic():
                        clicks = SmartlinkClick.objects.filter(
                            offer=offer, created_at__gte=window
                        ).aggregate(
                            total_clicks=Count('id'),
                            total_revenue=Sum('revenue'),
                        )
                        total_clicks  = clicks['total_clicks'] or 0
                        total_revenue = Decimal(str(clicks['total_revenue'] or 0))

                        epc = (total_revenue / total_clicks) if total_clicks > 0 else Decimal('0')
                        offer.epc = epc
                        offer.epc_calculated_at = timezone.now()
                        offer.save(update_fields=['epc', 'epc_calculated_at'])
                        updated += 1

                except Exception as row_err:
                    logger.error(f"[ERROR] EPC calc for offer {offer.pk}: {row_err}")
                    errors += 1

        except ImportError as e:
            logger.warning(f"[WARN] Smartlink models not available: {e}")

        result = {
            'status': 'success',
            'updated': updated,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] EPC recalculation done: {result}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] recalculate_epc failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# reset_daily_caps
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name='tasks.smartlink_tasks.reset_daily_caps',
)
def reset_daily_caps(self) -> dict:
    """
    Reset daily click/conversion caps for all active smartlink offers.
    Typically runs at midnight UTC via Celery Beat.
    """
    try:
        logger.info("🔄 Resetting daily caps for smartlink offers...")
        reset_count = 0

        try:
            from ad_networks.models import SmartlinkOffer

            with transaction.atomic():
                reset_count = SmartlinkOffer.objects.filter(
                    is_active=True,
                    daily_cap__isnull=False,
                ).update(
                    daily_clicks_used=0,
                    daily_conversions_used=0,
                    cap_reset_at=timezone.now(),
                )

        except ImportError as e:
            logger.warning(f"[WARN] Smartlink models not available: {e}")

        result = {
            'status': 'success',
            'reset_count': reset_count,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Daily caps reset: {reset_count} offers.")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] reset_daily_caps failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# sync_smartlink_stats
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    name='tasks.smartlink_tasks.sync_smartlink_stats',
)
def sync_smartlink_stats(self, network_ids: list = None) -> dict:
    """
    Pull fresh click / conversion / revenue stats from configured
    ad-network APIs and update local smartlink offer stats.
    Supports CPAlead, AdGate, Offertoro, etc.
    """
    try:
        logger.info(f"🌐 Syncing smartlink stats (networks={network_ids or 'all'})...")
        synced  = 0
        errors  = 0

        try:
            from ad_networks.models import AdNetwork, SmartlinkOffer
            from ad_networks.services import AdNetworkAPIClient

            networks = AdNetwork.objects.filter(is_active=True)
            if network_ids:
                networks = networks.filter(id__in=network_ids)

            for network in networks:
                try:
                    client = AdNetworkAPIClient(network)
                    stats  = client.fetch_stats()

                    for offer_data in stats.get('offers', []):
                        SmartlinkOffer.objects.filter(
                            external_id=offer_data.get('id'),
                            network=network,
                        ).update(
                            total_clicks=offer_data.get('clicks', 0),
                            total_conversions=offer_data.get('conversions', 0),
                            total_revenue=Decimal(str(offer_data.get('revenue', 0))),
                            last_synced_at=timezone.now(),
                        )
                        synced += 1

                except Exception as net_err:
                    logger.error(f"[ERROR] Network {network.name} sync: {net_err}")
                    errors += 1

        except ImportError as e:
            logger.warning(f"[WARN] AdNetwork models not available: {e}")

        result = {
            'status': 'success',
            'synced': synced,
            'errors': errors,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Smartlink stats sync done: {result}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] sync_smartlink_stats failed: {exc}")
        raise self.retry(exc=exc)


# ─────────────────────────────────────────────
# cleanup_expired_offers
# ─────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    name='tasks.smartlink_tasks.cleanup_expired_offers',
)
def cleanup_expired_offers(self) -> dict:
    """
    Deactivate smartlink offers whose expiry date has passed
    or whose budget has been fully consumed.
    """
    try:
        logger.info("🧹 Cleaning up expired smartlink offers...")
        expired_by_date   = 0
        expired_by_budget = 0

        try:
            from ad_networks.models import SmartlinkOffer

            # Expired by date
            now    = timezone.now()
            by_date = SmartlinkOffer.objects.filter(
                is_active=True,
                expires_at__lt=now,
            )
            expired_by_date = by_date.count()
            by_date.update(is_active=False, deactivated_at=now, deactivation_reason='expired')

            # Expired by budget
            by_budget = SmartlinkOffer.objects.filter(
                is_active=True,
                budget__isnull=False,
                total_revenue__gte=models.F('budget'),
            )
            expired_by_budget = by_budget.count()
            by_budget.update(is_active=False, deactivated_at=now, deactivation_reason='budget_exhausted')

        except ImportError as e:
            logger.warning(f"[WARN] Smartlink models not available: {e}")

        result = {
            'status': 'success',
            'expired_by_date': expired_by_date,
            'expired_by_budget': expired_by_budget,
            'total_expired': expired_by_date + expired_by_budget,
            'timestamp': timezone.now().isoformat(),
        }
        logger.info(f"[OK] Offer cleanup done: {result}")
        return result

    except Exception as exc:
        logger.error(f"[ERROR] cleanup_expired_offers failed: {exc}")
        raise self.retry(exc=exc)
