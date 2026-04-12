import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger('smartlink.tasks.click')


@shared_task(name='smartlink.process_click_async', bind=True, max_retries=3,
             default_retry_delay=5, queue='clicks')
def process_click_async(self, smartlink_id: int, offer_id: int = None, **context):
    """
    Async click recording task.
    Fired immediately after redirect to avoid blocking the HTTP response.
    Retries up to 3 times on failure.
    """
    try:
        from ..services.click.ClickTrackingService import ClickTrackingService
        service = ClickTrackingService()
        click = service.record(
            smartlink_id=smartlink_id,
            offer_id=offer_id,
            context=context,
        )
        logger.debug(f"Click recorded async: sl#{smartlink_id} offer#{offer_id} → click#{click.pk if click else None}")
        return {'click_id': click.pk if click else None}
    except Exception as exc:
        logger.error(f"process_click_async failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(name='smartlink.record_bot_click', queue='clicks')
def record_bot_click(smartlink_id: int, ip: str, user_agent: str,
                     bot_type: str = '', country: str = ''):
    """Record bot click to BotClick table for reporting."""
    try:
        from ..models import SmartLink, BotClick
        sl = SmartLink.objects.get(pk=smartlink_id)
        BotClick.objects.create(
            smartlink=sl,
            ip=ip,
            user_agent=user_agent,
            bot_type=bot_type,
            detection_method='ua_pattern',
            country=country,
        )
    except Exception as e:
        logger.error(f"record_bot_click failed: {e}")


@shared_task(name='smartlink.log_redirect_async', queue='clicks')
def log_redirect_async(slug: str, result: dict):
    """Async redirect log creation."""
    try:
        from ..models import SmartLink, RedirectLog
        sl = SmartLink.objects.get(slug=slug)
        RedirectLog.objects.create(
            smartlink=sl,
            offer_id=result.get('offer_id'),
            ip=result.get('ip', ''),
            country=result.get('country', ''),
            device_type=result.get('device_type', ''),
            redirect_type=result.get('redirect_type', '302'),
            destination_url=result.get('url', ''),
            status_code=302,
            response_time_ms=result.get('response_time_ms', 0),
            was_cached=result.get('was_cached', False),
            was_fallback=result.get('was_fallback', False),
        )
    except Exception as e:
        logger.error(f"log_redirect_async failed: {e}")


@shared_task(name='smartlink.update_cap_tracker_db', queue='default')
def update_cap_tracker_db(pool_entry_id: int):
    """Persist cap counter increment to DB from Redis."""
    try:
        from ..models import OfferPoolEntry, OfferCapTracker
        from ..choices import CapPeriod
        entry = OfferPoolEntry.objects.get(pk=pool_entry_id)
        today = timezone.now().date()

        if entry.cap_per_day:
            tracker, _ = OfferCapTracker.objects.get_or_create(
                pool_entry=entry,
                period=CapPeriod.DAILY,
                period_date=today,
                defaults={'cap_limit': entry.cap_per_day, 'clicks_count': 0},
            )
            from django.db.models import F
            OfferCapTracker.objects.filter(pk=tracker.pk).update(clicks_count=F('clicks_count') + 1)
            tracker.refresh_from_db()
            if tracker.clicks_count >= entry.cap_per_day:
                OfferCapTracker.objects.filter(pk=tracker.pk).update(is_capped=True)
    except Exception as e:
        logger.error(f"update_cap_tracker_db failed: {e}")


@shared_task(name='smartlink.attribute_conversion', queue='conversions')
def attribute_conversion(offer_id: int, sub1: str = '', ip: str = '',
                          payout: float = 0.0, transaction_id: str = ''):
    """Process an incoming conversion postback and attribute it to a click."""
    try:
        from ..services.click.ClickAttributionService import ClickAttributionService
        svc = ClickAttributionService()
        click = svc.attribute(
            offer_id=offer_id, sub1=sub1, ip=ip,
            payout=payout, transaction_id=transaction_id,
        )
        if click:
            from ..services.redirect.TrackingPixelService import TrackingPixelService
            try:
    from api.offer_inventory.models import Offer
except ImportError:
    Offer = None
            offer = Offer.objects.get(pk=offer_id)
            TrackingPixelService().fire_postback(offer, click.pk, payout)
        return {'attributed': click is not None, 'click_id': click.pk if click else None}
    except Exception as e:
        logger.error(f"attribute_conversion failed: {e}")
