"""
SmartLink Conversion Signal
============================
Fires when a Click is marked as converted (is_converted=True, payout>0).

Actions on conversion:
  1. EPC recalculation for the SmartLink (async Celery)
  2. Publisher wallet credit (async via BillingService)
  3. Outbound webhook dispatch (async Celery)
  4. Ad-network conversion integrations:
       GA4 Measurement Protocol
       TikTok Events API
       Snapchat Conversions API
       Facebook Pixel (CAPI)
       Google Ads conversion
       Twitter/X Ads CAPI

Integration calls are only fired when:
  - The publisher's SmartLink has that integration enabled (integrations JSON)
  - The integration has a valid access token / pixel ID configured
  - The call is wrapped in try/except so a failing integration never
    blocks the conversion credit or webhook.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from api.smartlink.models import Click

logger = logging.getLogger('smartlink.signals.conversion')


@receiver(post_save, sender=Click)
def on_conversion(sender, instance, created, **kwargs):
    """
    When a click is marked as converted:
    1. EPC recalculation
    2. Publisher wallet credit
    3. Webhook dispatch
    4. Ad-network integrations (GA4, TikTok, Snapchat, Facebook, Google Ads, Twitter)
    5. SubPublisher commission chain
    """
    if not created and instance.is_converted and float(instance.payout) > 0:

        # ── 1. EPC recalculation ──────────────────────────────────────────────
        try:
            from ..tasks.epc_update_tasks import update_epc_for_smartlink
            update_epc_for_smartlink.delay(instance.smartlink_id)
        except Exception as exc:
            logger.warning(f"Conversion signal EPC update failed: {exc}")

        # ── 2. Publisher wallet credit ────────────────────────────────────────
        try:
            from ..services.billing.BillingService import BillingService
            publisher = instance.smartlink.publisher
            BillingService().credit_conversion(
                publisher=publisher,
                amount_usd=float(instance.payout),
                smartlink_id=instance.smartlink_id,
                offer_id=instance.offer_id,
                click_id=instance.pk,
            )
        except Exception as exc:
            logger.error(
                f"Conversion signal wallet credit FAILED click={instance.pk}: {exc}",
                exc_info=True,
            )

        # ── 3. Webhook dispatch ───────────────────────────────────────────────
        try:
            from ..tasks.webhook_tasks import deliver_webhook_event
            publisher = instance.smartlink.publisher
            deliver_webhook_event.delay(
                event='conversion',
                publisher_id=publisher.pk,
                smartlink_id=instance.smartlink_id,
                offer_id=str(instance.offer_id) if instance.offer_id else None,
                click_id=instance.pk,
                payout=str(instance.payout),
                country=instance.country,
                device_type=instance.device_type,
            )
        except Exception as exc:
            logger.warning(f"Conversion signal webhook dispatch failed: {exc}")

        # ── 4. Ad-network integrations ────────────────────────────────────────
        _fire_integrations(instance)

        # ── 5. SubPublisher commission chain ──────────────────────────────────
        _credit_sub_publisher_commission(instance)


def _fire_integrations(click: Click):
    """
    Fire ad-network conversion events for every enabled integration
    on the SmartLink. Each network is isolated in its own try/except.

    Integrations config is stored in SmartLink.integrations JSONField:
      {
        "ga4": {"measurement_id": "G-XXXXX", "api_secret": "...", "is_active": true},
        "tiktok": {"pixel_id": "...", "access_token": "...", "is_active": true},
        "snapchat": {"pixel_id": "...", "access_token": "...", "is_active": true},
        "facebook": {"pixel_id": "...", "access_token": "...", "is_active": true},
        "google_ads": {"conversion_label": "...", "is_active": true},
        "twitter": {"pixel_id": "...", "access_token": "...", "is_active": true},
      }
    """
    try:
        integrations = getattr(click.smartlink, 'integrations', None) or {}
    except Exception:
        return  # SmartLink not loaded — skip integrations silently

    if not integrations:
        return

    # Build shared conversion context
    context = {
        'ip':         click.ip,
        'user_agent': click.user_agent,
        'country':    click.country,
        'device_type': click.device_type,
        'payout':     float(click.payout),
        'offer_id':   click.offer_id,
        'click_id':   click.pk,
    }

    # ── GA4 Measurement Protocol ──────────────────────────────────────────────
    ga4_cfg = integrations.get('ga4', {})
    if ga4_cfg.get('is_active') and ga4_cfg.get('measurement_id') and ga4_cfg.get('api_secret'):
        try:
            from ..integrations.google_analytics.GA4MeasurementProtocol import (
                GA4MeasurementProtocol,
            )
            GA4MeasurementProtocol().fire_purchase(
                measurement_id=ga4_cfg['measurement_id'],
                api_secret=ga4_cfg['api_secret'],
                context={
                    **context,
                    'currency': ga4_cfg.get('currency', 'USD'),
                    'value':    context['payout'],
                    'transaction_id': str(click.pk),
                },
            )
            logger.debug(f"GA4 conversion fired: click={click.pk}")
        except Exception as exc:
            logger.warning(f"GA4 integration failed for click={click.pk}: {exc}")

    # ── TikTok Events API ─────────────────────────────────────────────────────
    tiktok_cfg = integrations.get('tiktok', {})
    if tiktok_cfg.get('is_active') and tiktok_cfg.get('pixel_id') and tiktok_cfg.get('access_token'):
        try:
            from ..integrations.tiktok.TikTokEventsAPI import TikTokEventsAPI
            TikTokEventsAPI().fire_conversion_event(
                pixel_id=tiktok_cfg['pixel_id'],
                access_token=tiktok_cfg['access_token'],
                context={
                    **context,
                    'value':    context['payout'],
                    'currency': tiktok_cfg.get('currency', 'USD'),
                    'event_id': str(click.pk),
                },
            )
            logger.debug(f"TikTok conversion fired: click={click.pk}")
        except Exception as exc:
            logger.warning(f"TikTok integration failed for click={click.pk}: {exc}")

    # ── Snapchat Conversions API ──────────────────────────────────────────────
    snap_cfg = integrations.get('snapchat', {})
    if snap_cfg.get('is_active') and snap_cfg.get('pixel_id') and snap_cfg.get('access_token'):
        try:
            from ..integrations.snapchat.SnapchatConversionsAPI import SnapchatConversionsAPI
            SnapchatConversionsAPI().fire_purchase(
                pixel_id=snap_cfg['pixel_id'],
                token=snap_cfg['access_token'],
                context=context,
                value=context['payout'],
            )
            logger.debug(f"Snapchat conversion fired: click={click.pk}")
        except Exception as exc:
            logger.warning(f"Snapchat integration failed for click={click.pk}: {exc}")

    # ── Facebook Pixel (CAPI) ─────────────────────────────────────────────────
    fb_cfg = integrations.get('facebook', {})
    if fb_cfg.get('is_active') and fb_cfg.get('pixel_id') and fb_cfg.get('access_token'):
        try:
            from ..integrations.traffic_sources.FacebookPixelService import FacebookPixelService
            FacebookPixelService().fire_purchase_event(
                pixel_id=fb_cfg['pixel_id'],
                access_token=fb_cfg['access_token'],
                event_data={
                    **context,
                    'value':    context['payout'],
                    'currency': fb_cfg.get('currency', 'USD'),
                    'order_id': str(click.pk),
                    'event_source_url': getattr(click, 'referrer', ''),
                },
            )
            logger.debug(f"Facebook conversion fired: click={click.pk}")
        except Exception as exc:
            logger.warning(f"Facebook integration failed for click={click.pk}: {exc}")

    # ── Google Ads Conversion ─────────────────────────────────────────────────
    gads_cfg = integrations.get('google_ads', {})
    if gads_cfg.get('is_active') and gads_cfg.get('conversion_label'):
        try:
            from ..integrations.traffic_sources.GoogleAdsService import GoogleAdsConversionService
            GoogleAdsConversionService().fire_conversion({
                'gclid':            context.get('gclid', ''),
                'conversion_label': gads_cfg['conversion_label'],
                'conversion_value': context['payout'],
                'currency':         gads_cfg.get('currency', 'USD'),
                'order_id':         str(click.pk),
                **context,
            })
            logger.debug(f"Google Ads conversion fired: click={click.pk}")
        except Exception as exc:
            logger.warning(f"Google Ads integration failed for click={click.pk}: {exc}")

    # ── Twitter/X Ads CAPI ────────────────────────────────────────────────────
    twitter_cfg = integrations.get('twitter', {})
    if twitter_cfg.get('is_active') and twitter_cfg.get('pixel_id') and twitter_cfg.get('access_token'):
        try:
            from ..integrations.twitter.TwitterAdsConversionAPI import TwitterAdsConversionAPI
            TwitterAdsConversionAPI().fire_conversion(
                pixel_id=twitter_cfg['pixel_id'],
                access_token=twitter_cfg['access_token'],
                context={
                    **context,
                    'value':    context['payout'],
                    'currency': twitter_cfg.get('currency', 'USD'),
                    'event_id': str(click.pk),
                },
            )
            logger.debug(f"Twitter conversion fired: click={click.pk}")
        except Exception as exc:
            logger.warning(f"Twitter integration failed for click={click.pk}: {exc}")


def _credit_sub_publisher_commission(click: Click):
    """
    Credit the parent publisher commission if this click's publisher
    was referred by a parent via the SubPublisher referral chain.

    SubPublisher.calculate_commission(child_net_payout) handles
    both percentage and flat commission_type.
    """
    try:
        from api.smartlink.models.publisher import SubPublisher
        from ..services.billing.BillingService import BillingService

        publisher = click.smartlink.publisher
        net_payout = float(click.payout)

        # Find if this publisher has a parent in the referral chain
        sub_rel = SubPublisher.objects.select_related('parent_publisher').filter(
            child_publisher=publisher,
            is_active=True,
        ).first()

        if not sub_rel:
            return  # Not a referred publisher — nothing to do

        commission = sub_rel.calculate_commission(net_payout)
        if commission <= 0:
            return

        # Credit parent wallet with commission
        BillingService().credit_conversion(
            publisher=sub_rel.parent_publisher,
            amount_usd=commission,
            smartlink_id=click.smartlink_id,
            offer_id=click.offer_id,
            click_id=click.pk,
        )

        # Update lifetime commission tracker
        from decimal import Decimal
        from django.db.models import F
        SubPublisher.objects.filter(pk=sub_rel.pk).update(
            lifetime_earned=F('lifetime_earned') + Decimal(str(commission))
        )

        logger.info(
            f"SubPublisher commission credited: "
            f"parent={sub_rel.parent_publisher.username} "
            f"child={publisher.username} "
            f"commission=${commission:.4f} (from ${net_payout:.4f} payout)"
        )

    except Exception as exc:
        logger.warning(
            f"SubPublisher commission credit failed for click={click.pk}: {exc}"
        )
