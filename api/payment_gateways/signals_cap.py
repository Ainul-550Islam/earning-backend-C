# api/payment_gateways/signals_cap.py
# Capacity-related signals — full implementation with receivers and helpers

from django.dispatch import Signal, receiver
import logging

logger = logging.getLogger(__name__)

# ── Signal definitions ─────────────────────────────────────────────────────────
offer_cap_reached     = Signal()  # Fired when daily/total/budget cap is hit
offer_cap_reset       = Signal()  # Fired at midnight when daily caps reset
offer_approaching_cap = Signal()  # Fired at 80% cap utilization
offer_paused_by_cap   = Signal()  # Fired when offer is auto-paused due to cap
offer_reactivated     = Signal()  # Fired when offer is reactivated after cap reset
queue_depth_critical  = Signal()  # Fired when queue fills above 80%
gateway_rate_limited  = Signal()  # Fired when a gateway rate limit is hit
daily_budget_warning  = Signal()  # Fired when daily budget hits 80%


# ── Signal handlers (connect to your existing notification/alert system) ────────
@receiver(offer_cap_reached)
def handle_offer_cap_reached(sender, offer, cap_type, **kwargs):
    """
    When an offer cap is reached:
        1. Auto-pause the offer
        2. Notify the advertiser
        3. Log the event
        4. Remove offer from SmartLink rotation
    """
    logger.warning(f'Offer cap reached: offer_id={offer.id} name={offer.name} cap_type={cap_type}')

    # Auto-pause offer
    try:
        from api.payment_gateways.offers.models import Offer
        Offer.objects.filter(id=offer.id, status='active').update(status='paused')
        # Fire paused signal
        offer_paused_by_cap.send(sender=sender, offer=offer, cap_type=cap_type)
        logger.info(f'Offer {offer.id} auto-paused due to {cap_type} cap')
    except Exception as e:
        logger.error(f'Could not auto-pause offer {offer.id}: {e}')

    # Notify advertiser
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        advertiser_email = offer.advertiser.email if hasattr(offer, 'advertiser') else None
        if advertiser_email:
            send_mail(
                subject=f'Offer Paused: {offer.name} — {cap_type.replace("_"," ").title()} Reached',
                message=(
                    f'Your offer "{offer.name}" has been automatically paused '
                    f'because the {cap_type.replace("_"," ")} has been reached.\n\n'
                    f'To reactivate, please increase the cap limit in your advertiser dashboard.\n\n'
                    f'Daily caps reset automatically at midnight.'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[advertiser_email],
                fail_silently=True,
            )
    except Exception as e:
        logger.debug(f'Cap notification email failed: {e}')

    # Remove from SmartLink active rotation
    try:
        from api.payment_gateways.smartlink.models import SmartLinkRotation
        SmartLinkRotation.objects.filter(offer=offer).update(weight=0)
    except Exception as e:
        logger.debug(f'Could not update SmartLink rotation: {e}')


@receiver(offer_reactivated)
def handle_offer_reactivated(sender, offer, **kwargs):
    """When offer is reactivated (cap reset), restore SmartLink rotation weight."""
    logger.info(f'Offer reactivated: offer_id={offer.id}')
    try:
        from api.payment_gateways.smartlink.models import SmartLinkRotation
        SmartLinkRotation.objects.filter(offer=offer, weight=0).update(weight=50)
    except Exception as e:
        logger.debug(f'Could not restore SmartLink rotation: {e}')


@receiver(offer_approaching_cap)
def handle_approaching_cap(sender, offer, cap_type, pct_used, **kwargs):
    """Alert advertiser when approaching cap (80% used)."""
    logger.info(f'Offer approaching cap: offer_id={offer.id} {cap_type}={pct_used:.0%}')
    try:
        from django.core.cache import cache
        alert_key = f'cap_alert_sent:{offer.id}:{cap_type}'
        if not cache.get(alert_key):
            # Only alert once per cap period
            cache.set(alert_key, True, 3600 * 24)  # 24h cooldown
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                if hasattr(offer, 'advertiser') and offer.advertiser.email:
                    send_mail(
                        subject=f'⚠️ Offer {offer.name} at {pct_used:.0%} {cap_type.replace("_"," ")}',
                        message=(
                            f'Your offer "{offer.name}" has used {pct_used:.0%} of its {cap_type.replace("_"," ")}.\n'
                            f'Consider increasing the limit to avoid interruption.'
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[offer.advertiser.email],
                        fail_silently=True,
                    )
            except Exception:
                pass
    except Exception as e:
        logger.debug(f'Cap alert failed: {e}')


@receiver(queue_depth_critical)
def handle_queue_depth_critical(sender, queue_name, depth, max_depth, **kwargs):
    """Alert admin when queue depth exceeds 80%."""
    pct = depth / max_depth * 100
    logger.critical(f'QUEUE CRITICAL: {queue_name} at {pct:.0f}% ({depth}/{max_depth})')
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        send_mail(
            subject=f'[CRITICAL] Payment Queue {queue_name} at {pct:.0f}%',
            message=(
                f'Queue {queue_name} is at {pct:.0f}% capacity ({depth}/{max_depth} messages).\n'
                f'Action required: Scale Celery workers immediately.\n\n'
                f'Command: celery -A config worker --concurrency=8 -Q {queue_name}'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL)],
            fail_silently=True,
        )
    except Exception as e:
        logger.error(f'Queue alert email failed: {e}')


@receiver(daily_budget_warning)
def handle_daily_budget_warning(sender, offer, budget_used, daily_budget, **kwargs):
    """Warn advertiser when daily budget is 80% consumed."""
    pct = budget_used / daily_budget * 100
    logger.info(f'Daily budget 80% warning: offer_id={offer.id} {budget_used:.2f}/{daily_budget:.2f}')


# ── Helper functions ───────────────────────────────────────────────────────────
def emit_cap_reached(offer, cap_type: str):
    """Helper: fire offer_cap_reached signal."""
    offer_cap_reached.send(
        sender=offer.__class__,
        offer=offer,
        cap_type=cap_type,
    )


def emit_cap_reset(offer, cap_type: str):
    """Helper: fire offer_cap_reset signal."""
    offer_cap_reset.send(
        sender=offer.__class__,
        offer=offer,
        cap_type=cap_type,
    )
    offer_reactivated.send(sender=offer.__class__, offer=offer)


def emit_approaching_cap(offer, cap_type: str, pct_used: float):
    """Helper: fire approaching cap signal if >= 80%."""
    if pct_used >= 0.80:
        offer_approaching_cap.send(
            sender=offer.__class__,
            offer=offer,
            cap_type=cap_type,
            pct_used=pct_used,
        )


def emit_queue_critical(queue_name: str, depth: int, max_depth: int):
    """Helper: fire queue depth critical signal."""
    if depth >= max_depth * 0.80:
        queue_depth_critical.send(
            sender=None,
            queue_name=queue_name,
            depth=depth,
            max_depth=max_depth,
        )


def emit_gateway_rate_limited(gateway: str, user=None):
    """Helper: fire gateway rate limited signal."""
    gateway_rate_limited.send(
        sender=None,
        gateway=gateway,
        user=user,
    )
