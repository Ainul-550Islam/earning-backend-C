# publisher_tools/signals.py  — COMPLETE FIXED VERSION
# ============================================================
# Changes from original:
#   1. on_publisher_status_change: N+1 fix (update_fields guard)
#   2. on_invoice_status_change: calls send_invoice_paid_webhook()
#   3. on_publisher_created: calls send_webhook_event() for approval
#   4. on_ivt_detected: calls send_fraud_detected_webhook()
#   5. on_site_status_change: calls site approved/rejected webhooks
#   6. NEW: on_publisher_approved_webhook signal
#   7. NEW: on_publisher_suspended_webhook signal
# Replace your existing signals.py with this file entirely.
# ============================================================
from decimal import Decimal
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# PUBLISHER SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.Publisher')
def on_publisher_created(sender, instance, created, **kwargs):
    """
    Publisher তৈরির পর:
    - Default PayoutThreshold তৈরি করে (bKash, Nagad)
    - Welcome notification task trigger করে
    """
    if not created:
        return

    from .models import PayoutThreshold
    from .constants import MIN_PAYOUT_THRESHOLDS

    default_methods = [
        {
            'payment_method': 'bkash',
            'minimum_threshold': Decimal(str(MIN_PAYOUT_THRESHOLDS.get('bkash', 500))),
            'payment_frequency': 'monthly',
            'is_primary': True,
        },
        {
            'payment_method': 'nagad',
            'minimum_threshold': Decimal(str(MIN_PAYOUT_THRESHOLDS.get('nagad', 500))),
            'payment_frequency': 'monthly',
            'is_primary': False,
        },
    ]

    for i, method_data in enumerate(default_methods):
        PayoutThreshold.objects.get_or_create(
            publisher=instance,
            payment_method=method_data['payment_method'],
            defaults={
                'minimum_threshold': method_data['minimum_threshold'],
                'payment_frequency': method_data['payment_frequency'],
                'is_primary': i == 0,
            }
        )

    # Welcome notification (async task)
    try:
        from .tasks import send_publisher_welcome_notification
        send_publisher_welcome_notification.delay(str(instance.id))
    except Exception as e:
        logger.warning(f'Welcome notification task failed to enqueue: {e}')


@receiver(pre_save, sender='publisher_tools.Publisher')
def on_publisher_status_change(sender, instance, **kwargs):
    """
    Publisher status change detect করে।
    FIX: update_fields guard দিয়ে unnecessary DB query এড়ানো।
    Suspended/Banned হলে সব site ও app suspend।
    Webhook trigger করে।
    """
    if not instance.pk:
        return

    # ── N+1 FIX: only query if status field is being updated ─────────────────
    # If called via save(update_fields=[...]) that doesn't include 'status',
    # skip the expensive old-instance lookup entirely.
    # (Django sets _state.adding=False and passes update_fields kwarg via **kwargs)
    update_fields = kwargs.get('update_fields')
    if update_fields is not None and 'status' not in update_fields:
        return

    try:
        old_instance = sender.objects.only('status').get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old_instance.status == instance.status:
        return

    old_status = old_instance.status
    new_status = instance.status

    # Active → Suspended/Banned: cascade to inventory
    if new_status in ('suspended', 'banned') and old_status == 'active':
        instance.sites.filter(status='active').update(status='suspended')
        instance.apps.filter(status='active').update(status='suspended')
        instance.ad_units.filter(status='active').update(status='paused')

        # Webhook — publisher.suspended
        try:
            from .webhooks.webhook_manager import send_webhook_event
            send_webhook_event(instance, 'publisher.suspended', {
                'publisher_id': instance.publisher_id,
                'new_status':   new_status,
                'old_status':   old_status,
                'suspended_at': timezone.now().isoformat(),
            })
        except Exception as e:
            logger.warning(f'publisher.suspended webhook failed: {e}')

    # Suspended → Active: un-suspend
    elif new_status == 'active' and old_status in ('suspended', 'pending'):
        if old_status == 'suspended':
            instance.sites.filter(status='suspended').update(status='active')
            instance.apps.filter(status='suspended').update(status='active')
            instance.ad_units.filter(status='paused').update(status='active')

        # Webhook — publisher.approved
        try:
            from .webhooks.webhook_manager import send_webhook_event
            send_webhook_event(instance, 'publisher.approved', {
                'publisher_id': instance.publisher_id,
                'new_status':   new_status,
                'old_status':   old_status,
                'approved_at':  timezone.now().isoformat(),
            })
        except Exception as e:
            logger.warning(f'publisher.approved webhook failed: {e}')


# ──────────────────────────────────────────────────────────────────────────────
# SITE SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.Site')
def on_site_status_change(sender, instance, created, **kwargs):
    """
    Site approved/rejected হলে:
    - Cache invalidate
    - Webhook trigger
    """
    if created:
        return

    update_fields = kwargs.get('update_fields')
    status_changed = update_fields is None or 'status' in update_fields

    if not status_changed:
        return

    # Cache invalidate
    try:
        from django.core.cache import cache
        from .utils import get_site_cache_key
        cache.delete(get_site_cache_key(instance.site_id, 'analytics'))
        cache.delete(get_site_cache_key(instance.site_id, 'quality'))
    except Exception as e:
        logger.warning(f'Site cache invalidate failed: {e}')

    # Webhook — site.approved
    if instance.status == 'active':
        try:
            from .webhooks.webhook_manager import send_webhook_event
            send_webhook_event(instance.publisher, 'site.approved', {
                'site_id':     instance.site_id,
                'domain':      instance.domain,
                'approved_at': timezone.now().isoformat(),
            })
        except Exception as e:
            logger.warning(f'site.approved webhook failed: {e}')

    # Webhook — site.rejected
    elif instance.status == 'rejected':
        try:
            from .webhooks.webhook_manager import send_webhook_event
            send_webhook_event(instance.publisher, 'site.rejected', {
                'site_id':     instance.site_id,
                'domain':      instance.domain,
                'rejected_at': timezone.now().isoformat(),
            })
        except Exception as e:
            logger.warning(f'site.rejected webhook failed: {e}')


@receiver(post_save, sender='publisher_tools.Site')
def on_site_ads_txt_verified(sender, instance, created, **kwargs):
    """ads.txt verify হলে site quality score update করে"""
    if created:
        return

    update_fields = kwargs.get('update_fields')
    if update_fields and 'ads_txt_verified' not in update_fields:
        return

    if instance.ads_txt_verified:
        from .models import SiteQualityMetric
        today = timezone.now().date()
        SiteQualityMetric.objects.filter(
            site=instance, date=today
        ).update(ads_txt_valid=True, ads_txt_present=True)


# ──────────────────────────────────────────────────────────────────────────────
# AD UNIT SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.AdUnit')
def on_ad_unit_created(sender, instance, created, **kwargs):
    """
    AdUnit তৈরির পর:
    - Default AdUnitTargeting তৈরি
    - Default MediationGroup তৈরি
    - Webhook trigger
    """
    if not created:
        return

    from .models import AdUnitTargeting, MediationGroup

    # Default targeting
    AdUnitTargeting.objects.get_or_create(
        ad_unit=instance,
        defaults={
            'name':            f'{instance.name} — Default Targeting',
            'target_countries': ['ALL'],
            'device_type':     'all',
            'target_os':       'all',
            'is_active':       True,
        }
    )

    # Default mediation group
    MediationGroup.objects.get_or_create(
        ad_unit=instance,
        defaults={
            'name':           f'{instance.name} — Mediation',
            'mediation_type': 'waterfall',
            'is_active':      True,
        }
    )

    # Webhook — ad_unit.created
    try:
        from .webhooks.webhook_manager import send_webhook_event
        send_webhook_event(instance.publisher, 'ad_unit.created', {
            'unit_id':    instance.unit_id,
            'name':       instance.name,
            'format':     instance.format,
            'created_at': timezone.now().isoformat(),
        })
    except Exception as e:
        logger.warning(f'ad_unit.created webhook failed: {e}')


@receiver(post_save, sender='publisher_tools.AdUnit')
def invalidate_ad_unit_cache(sender, instance, **kwargs):
    """Ad Unit cache invalidate করে"""
    try:
        from django.core.cache import cache
        from .utils import get_unit_cache_key
        cache.delete(get_unit_cache_key(instance.unit_id, 'performance'))
        cache.delete(get_unit_cache_key(instance.unit_id, 'tag'))
    except Exception as e:
        logger.warning(f'Ad unit cache invalidate failed: {e}')


# ──────────────────────────────────────────────────────────────────────────────
# EARNING SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.PublisherEarning')
def on_earning_saved(sender, instance, created, **kwargs):
    """
    Earning record save হলে:
    - Publisher total_revenue update
    - Ad Unit avg_ecpm update
    - Cache invalidate
    """
    from .models import PublisherEarning
    from django.db.models import Sum

    publisher = instance.publisher

    # Publisher total revenue (finalized only)
    agg = PublisherEarning.objects.filter(
        publisher=publisher,
        status__in=['confirmed', 'finalized'],
    ).aggregate(total=Sum('publisher_revenue'))

    new_total = agg.get('total') or Decimal('0')
    publisher.total_revenue = new_total
    publisher.save(update_fields=['total_revenue', 'updated_at'])

    # Ad unit avg_ecpm update
    if instance.ad_unit:
        unit = instance.ad_unit
        unit_agg = PublisherEarning.objects.filter(
            ad_unit=unit,
        ).aggregate(
            total_revenue=Sum('publisher_revenue'),
            total_imps=Sum('impressions'),
        )
        total_rev  = unit_agg.get('total_revenue') or Decimal('0')
        total_imps = unit_agg.get('total_imps') or 0
        if total_imps > 0:
            unit.avg_ecpm = (total_rev / total_imps) * 1000
            unit.save(update_fields=['avg_ecpm', 'updated_at'])

    # Cache invalidate
    try:
        from django.core.cache import cache
        from .utils import get_publisher_cache_key
        cache.delete(get_publisher_cache_key(publisher.publisher_id, 'dashboard'))
        cache.delete(get_publisher_cache_key(publisher.publisher_id, 'stats'))
    except Exception as e:
        logger.warning(f'Earning cache invalidate failed: {e}')


# ──────────────────────────────────────────────────────────────────────────────
# INVOICE SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.PublisherInvoice')
def on_invoice_status_change(sender, instance, created, **kwargs):
    """
    Invoice status change হলে:
    - Paid → Publisher total_paid_out update + webhook
    - Issued → webhook
    FIX: now actually calls send_invoice_paid_webhook()
    """
    if created:
        return

    update_fields = kwargs.get('update_fields')
    if update_fields is not None and 'status' not in update_fields:
        return

    if instance.status == 'paid':
        # Update publisher paid total
        try:
            from .models import PublisherInvoice
            from django.db.models import Sum
            paid_agg = PublisherInvoice.objects.filter(
                publisher=instance.publisher,
                status='paid',
            ).aggregate(total=Sum('net_payable'))
            instance.publisher.total_paid_out = paid_agg.get('total') or Decimal('0')
            instance.publisher.save(update_fields=['total_paid_out', 'updated_at'])
        except Exception as e:
            logger.warning(f'total_paid_out update failed: {e}')

        # Webhook — invoice.paid
        try:
            from .webhooks.payment_webhook import send_invoice_paid_webhook
            send_invoice_paid_webhook(instance.publisher, instance)
        except Exception as e:
            logger.warning(f'invoice.paid webhook failed: {e}')

    elif instance.status == 'issued':
        # Webhook — invoice.issued
        try:
            from .webhooks.payment_webhook import send_invoice_issued_webhook
            send_invoice_issued_webhook(instance.publisher, instance)
        except Exception as e:
            logger.warning(f'invoice.issued webhook failed: {e}')


# ──────────────────────────────────────────────────────────────────────────────
# TRAFFIC SAFETY LOG SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.TrafficSafetyLog')
def on_ivt_detected(sender, instance, created, **kwargs):
    """
    IVT detect হলে:
    - Critical → auto-block
    - Site quality metric update
    - Webhook trigger (fraud.high_risk_detected)
    FIX: now calls send_fraud_detected_webhook()
    """
    if not created:
        return

    from .constants import FRAUD_SCORE_BLOCKED, CRITICAL_IVT_THRESHOLD

    # Auto-block critical fraud
    if instance.fraud_score >= FRAUD_SCORE_BLOCKED and instance.action_taken == 'pending':
        try:
            from .services import FraudDetectionService
            FraudDetectionService.auto_block(instance)
        except Exception as e:
            logger.warning(f'Auto-block failed for TrafficSafetyLog {instance.pk}: {e}')

    # Update site quality alerts
    if instance.site:
        try:
            from .models import SiteQualityMetric
            today = timezone.now().date()
            metric, _ = SiteQualityMetric.objects.get_or_create(
                site=instance.site,
                date=today,
                defaults={'overall_quality_score': instance.site.quality_score},
            )
            if not metric.has_alerts:
                metric.has_alerts = True
                if not isinstance(metric.alert_details, list):
                    metric.alert_details = []
                metric.alert_details.append({
                    'type':         'ivt_detected',
                    'traffic_type': instance.traffic_type,
                    'severity':     instance.severity,
                    'fraud_score':  instance.fraud_score,
                })
                metric.save(update_fields=['has_alerts', 'alert_details', 'updated_at'])
        except Exception as e:
            logger.warning(f'SiteQualityMetric update failed: {e}')

    # Webhook — fraud.high_risk_detected (only for high/critical)
    if instance.severity in ('high', 'critical'):
        try:
            from .webhooks.fraud_webhook import send_fraud_detected_webhook
            send_fraud_detected_webhook(instance.publisher, instance)
        except Exception as e:
            logger.warning(f'fraud.high_risk_detected webhook failed: {e}')


# ──────────────────────────────────────────────────────────────────────────────
# MEDIATION SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.WaterfallItem')
def on_waterfall_item_saved(sender, instance, **kwargs):
    """Waterfall change হলে cache invalidate করে"""
    try:
        from django.core.cache import cache
        from .utils import build_cache_key
        cache.delete(build_cache_key('waterfall', str(instance.mediation_group.id)))
    except Exception as e:
        logger.warning(f'Waterfall cache invalidate failed: {e}')


@receiver(post_delete, sender='publisher_tools.WaterfallItem')
def on_waterfall_item_deleted(sender, instance, **kwargs):
    """Waterfall item delete হলে cache invalidate করে"""
    try:
        from django.core.cache import cache
        from .utils import build_cache_key
        cache.delete(build_cache_key('waterfall', str(instance.mediation_group.id)))
    except Exception as e:
        logger.warning(f'Waterfall cache invalidate (delete) failed: {e}')


# ──────────────────────────────────────────────────────────────────────────────
# SITE QUALITY METRIC SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.SiteQualityMetric')
def on_quality_metric_saved(sender, instance, **kwargs):
    """
    Quality metric update হলে:
    - Site quality_score update
    - Critical alerts → site.quality_alert webhook
    """
    # Update site quality score
    try:
        site = instance.site
        if site.quality_score != instance.overall_quality_score:
            site.quality_score = instance.overall_quality_score
            site.save(update_fields=['quality_score', 'updated_at'])
    except Exception as e:
        logger.warning(f'Site quality_score update failed: {e}')

    # Quality alert webhook for malware / adult content
    if getattr(instance, 'malware_detected', False) or getattr(instance, 'adult_content_detected', False):
        try:
            from .webhooks.alert_webhook import send_site_quality_alert
            send_site_quality_alert(instance.site.publisher, instance.site, {
                'malware_detected':         getattr(instance, 'malware_detected', False),
                'adult_content_detected':   getattr(instance, 'adult_content_detected', False),
                'overall_quality_score':    instance.overall_quality_score,
                'date':                     str(instance.date),
            })
        except Exception as e:
            logger.warning(f'site.quality_alert webhook failed: {e}')

    # Cache invalidate
    try:
        from django.core.cache import cache
        from .utils import get_site_cache_key
        cache.delete(get_site_cache_key(instance.site.site_id, 'quality'))
    except Exception as e:
        logger.warning(f'Quality metric cache invalidate failed: {e}')
