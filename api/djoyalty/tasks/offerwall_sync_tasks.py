# api/djoyalty/tasks/offerwall_sync_tasks.py
"""
OfferWall Sync Celery Tasks।
Sync offers from CPAlead/Tapjoy, cleanup expired, process pending postbacks।
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name='djoyalty.sync_cpalead_offers')
def sync_cpalead_offers_task(offer_wall_id: int):
    """Sync offers from CPAlead API into local DB।"""
    try:
        from ..models.offerwall import OfferWall, Offer
        from ..integrations.cpalead import CPALeadIntegration

        wall = OfferWall.objects.get(id=offer_wall_id, provider='cpalead')
        cpalead = CPALeadIntegration()

        if not CPALeadIntegration.is_configured():
            return {'skipped': True, 'reason': 'CPAlead not configured'}

        external_offers = cpalead.get_offers(limit=100)
        synced = 0

        for offer_data in external_offers:
            ext_id = str(offer_data.get('id', ''))
            if not ext_id:
                continue

            Offer.objects.update_or_create(
                offer_wall=wall,
                external_offer_id=ext_id,
                defaults={
                    'title': offer_data.get('name', '')[:300],
                    'description': offer_data.get('description', ''),
                    'offer_type': 'app_install',
                    'points_reward': wall.currency_ratio * float(offer_data.get('payout', 0)),
                    'advertiser_payout': offer_data.get('payout', 0),
                    'offer_url': offer_data.get('url', ''),
                    'status': 'active',
                },
            )
            synced += 1

        logger.info('sync_cpalead_offers_task: synced %d offers for wall #%d', synced, offer_wall_id)
        return {'synced': synced}
    except Exception as exc:
        logger.error('sync_cpalead_offers_task error: %s', exc)
        return {'error': str(exc)}


@shared_task(name='djoyalty.cleanup_expired_offers')
def cleanup_expired_offers_task():
    """Mark expired offers as ended।"""
    try:
        from django.utils import timezone
        from ..models.offerwall import Offer

        expired = Offer.objects.filter(
            status='active',
            valid_until__lt=timezone.now(),
        ).update(status='ended')

        logger.info('cleanup_expired_offers_task: ended %d offers', expired)
        return {'ended': expired}
    except Exception as exc:
        logger.error('cleanup_expired_offers_task error: %s', exc)
        return {'error': str(exc)}


@shared_task(name='djoyalty.retry_pending_postbacks')
def retry_pending_postbacks_task():
    """Retry unprocessed postbacks that failed earlier।"""
    try:
        from ..models.offerwall import OfferPostbackLog
        from ..services.OfferWallService import OfferWallService
        from django.utils import timezone
        from datetime import timedelta

        # Pending logs older than 5 min but less than 24h
        cutoff = timezone.now() - timedelta(minutes=5)
        max_age = timezone.now() - timedelta(hours=24)

        pending = OfferPostbackLog.objects.filter(
            processed=False,
            received_at__lt=cutoff,
            received_at__gte=max_age,
            signature_valid=True,
        )[:50]

        retried = 0
        for log in pending:
            try:
                if log.offer_wall_id:
                    OfferWallService.process_postback(
                        offer_wall_id=log.offer_wall_id,
                        raw_data=log.raw_data,
                        ip_address=log.ip_address or '',
                    )
                    retried += 1
            except Exception as e:
                logger.debug('retry postback #%d failed: %s', log.id, e)

        logger.info('retry_pending_postbacks_task: retried %d', retried)
        return {'retried': retried}
    except Exception as exc:
        logger.error('retry_pending_postbacks_task error: %s', exc)
        return {'error': str(exc)}
