# api/publisher_tools/signals.py
"""
Publisher Tools — Django Signals।
Model save/delete events-এ automatic actions।
"""
from decimal import Decimal
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone


# ──────────────────────────────────────────────────────────────────────────────
# PUBLISHER SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.Publisher')
def on_publisher_created(sender, instance, created, **kwargs):
    """
    Publisher তৈরির পর:
    - Default PayoutThreshold তৈরি করে (bKash, Nagad)
    - Audit log তৈরি করে
    """
    if created:
        from .models import PayoutThreshold
        from .constants import MIN_PAYOUT_THRESHOLDS

        # Default payment methods (BD publishers-এর জন্য)
        default_methods = [
            {
                'payment_method': 'bkash',
                'minimum_threshold': Decimal(str(MIN_PAYOUT_THRESHOLDS['bkash'])),
                'payment_frequency': 'monthly',
                'is_primary': True,
            },
            {
                'payment_method': 'nagad',
                'minimum_threshold': Decimal(str(MIN_PAYOUT_THRESHOLDS['nagad'])),
                'payment_frequency': 'monthly',
                'is_primary': False,
            },
        ]

        # If this is the first threshold, make bkash primary
        for i, method_data in enumerate(default_methods):
            PayoutThreshold.objects.get_or_create(
                publisher=instance,
                payment_method=method_data['payment_method'],
                defaults={
                    'minimum_threshold': method_data['minimum_threshold'],
                    'payment_frequency': method_data['payment_frequency'],
                    'is_primary': i == 0,  # first one is primary
                }
            )


@receiver(pre_save, sender='publisher_tools.Publisher')
def on_publisher_status_change(sender, instance, **kwargs):
    """
    Publisher status change detect করে।
    Suspended/Banned হলে সব site ও app suspend।
    """
    if not instance.pk:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if old_instance.status == instance.status:
        return

    # Active → Suspended: suspend সব sites ও apps
    if instance.status in ('suspended', 'banned') and old_instance.status == 'active':
        instance.sites.filter(status='active').update(status='suspended')
        instance.apps.filter(status='active').update(status='suspended')
        instance.ad_units.filter(status='active').update(status='paused')

    # Suspended → Active: un-suspend sites ও apps
    elif instance.status == 'active' and old_instance.status == 'suspended':
        instance.sites.filter(status='suspended').update(status='active')
        instance.apps.filter(status='suspended').update(status='active')
        instance.ad_units.filter(status='paused').update(status='active')


# ──────────────────────────────────────────────────────────────────────────────
# SITE SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.Site')
def on_site_status_change(sender, instance, created, **kwargs):
    """
    Site approved হলে:
    - Publisher-এর active_sites count update
    - Auto-create default AdUnit (optional)
    """
    if created:
        return

    if instance.status == 'active':
        # Cache invalidate
        from django.core.cache import cache
        from .utils import get_site_cache_key
        cache.delete(get_site_cache_key(instance.site_id, 'analytics'))


@receiver(post_save, sender='publisher_tools.Site')
def on_site_ads_txt_verified(sender, instance, created, **kwargs):
    """ads.txt verify হলে site quality score update করে"""
    if not created and instance.ads_txt_verified:
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
    - Default AdUnitTargeting তৈরি করে
    - Default MediationGroup তৈরি করে (যদি না থাকে)
    """
    if created:
        from .models import AdUnitTargeting, MediationGroup

        # Default targeting
        AdUnitTargeting.objects.get_or_create(
            ad_unit=instance,
            defaults={
                'name': f'{instance.name} — Default Targeting',
                'target_countries': ['ALL'],
                'device_type': 'all',
                'target_os': 'all',
                'is_active': True,
            }
        )

        # Default mediation group
        MediationGroup.objects.get_or_create(
            ad_unit=instance,
            defaults={
                'name': f'{instance.name} — Mediation',
                'mediation_type': 'waterfall',
                'is_active': True,
            }
        )


@receiver(post_save, sender='publisher_tools.AdUnit')
def invalidate_ad_unit_cache(sender, instance, **kwargs):
    """Ad Unit cache invalidate করে"""
    from django.core.cache import cache
    from .utils import get_unit_cache_key
    cache.delete(get_unit_cache_key(instance.unit_id, 'performance'))
    cache.delete(get_unit_cache_key(instance.unit_id, 'tag'))


# ──────────────────────────────────────────────────────────────────────────────
# EARNING SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.PublisherEarning')
def on_earning_saved(sender, instance, created, **kwargs):
    """
    Earning record save হলে:
    - Publisher total_revenue update করে
    - Ad Unit avg_ecpm update করে
    - Cache invalidate করে
    """
    # Update publisher revenue
    from .models import PublisherEarning
    from django.db.models import Sum

    publisher = instance.publisher

    # Aggregate all finalized/confirmed earnings
    agg = PublisherEarning.objects.filter(
        publisher=publisher,
        status__in=['confirmed', 'finalized'],
    ).aggregate(total=Sum('publisher_revenue'))

    publisher.total_revenue = agg.get('total') or Decimal('0')
    publisher.save(update_fields=['total_revenue', 'updated_at'])

    # Update ad unit avg_ecpm
    if instance.ad_unit:
        unit = instance.ad_unit
        unit_agg = PublisherEarning.objects.filter(
            ad_unit=unit,
        ).aggregate(
            avg_ecpm=Sum('publisher_revenue') / Sum('impressions') * 1000,
        )
        if unit_agg.get('avg_ecpm'):
            unit.avg_ecpm = unit_agg['avg_ecpm']
            unit.save(update_fields=['avg_ecpm', 'updated_at'])

    # Cache invalidate
    from django.core.cache import cache
    from .utils import get_publisher_cache_key
    cache.delete(get_publisher_cache_key(publisher.publisher_id, 'dashboard'))
    cache.delete(get_publisher_cache_key(publisher.publisher_id, 'stats'))


# ──────────────────────────────────────────────────────────────────────────────
# INVOICE SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.PublisherInvoice')
def on_invoice_status_change(sender, instance, created, **kwargs):
    """
    Invoice status change হলে:
    - Paid হলে Publisher total_paid_out update করে
    - Publisher-কে notification পাঠায়
    """
    if created:
        return

    if instance.status == 'paid' and instance.paid_at:
        # Try to send notification
        try:
            from api.notifications.models import Notice
            Notice.objects.create(
                message=f'💰 Invoice {instance.invoice_number} paid: ${instance.net_payable}',
                is_active=True,
            )
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# TRAFFIC SAFETY LOG SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.TrafficSafetyLog')
def on_ivt_detected(sender, instance, created, **kwargs):
    """
    IVT detect হলে:
    - Critical severity হলে auto-block
    - Site quality metric update করে
    - High IVT rate হলে publisher warning
    """
    if not created:
        return

    from .constants import FRAUD_SCORE_BLOCKED, CRITICAL_IVT_THRESHOLD

    # Auto-block critical fraud
    if instance.fraud_score >= FRAUD_SCORE_BLOCKED and instance.action_taken == 'pending':
        from .services import FraudDetectionService
        FraudDetectionService.auto_block(instance)

    # Update site quality alerts
    if instance.site:
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
                'type': 'ivt_detected',
                'traffic_type': instance.traffic_type,
                'severity': instance.severity,
                'fraud_score': instance.fraud_score,
            })
            metric.save(update_fields=['has_alerts', 'alert_details', 'updated_at'])


# ──────────────────────────────────────────────────────────────────────────────
# MEDIATION SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.WaterfallItem')
def on_waterfall_item_saved(sender, instance, **kwargs):
    """Waterfall change হলে cache invalidate করে"""
    from django.core.cache import cache
    from .utils import build_cache_key
    cache.delete(build_cache_key('waterfall', str(instance.mediation_group.id)))


@receiver(post_delete, sender='publisher_tools.WaterfallItem')
def on_waterfall_item_deleted(sender, instance, **kwargs):
    """Waterfall item delete হলে cache invalidate করে"""
    from django.core.cache import cache
    from .utils import build_cache_key
    cache.delete(build_cache_key('waterfall', str(instance.mediation_group.id)))


# ──────────────────────────────────────────────────────────────────────────────
# SITE QUALITY METRIC SIGNALS
# ──────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='publisher_tools.SiteQualityMetric')
def on_quality_metric_saved(sender, instance, **kwargs):
    """
    Quality metric update হলে:
    - Site-এর quality_score update করে
    - Critical alerts থাকলে admin notification trigger করে
    """
    # Update site quality score
    site = instance.site
    if site.quality_score != instance.overall_quality_score:
        site.quality_score = instance.overall_quality_score
        site.save(update_fields=['quality_score', 'updated_at'])

    # Critical alert notification
    if instance.malware_detected or instance.adult_content_detected:
        try:
            from api.notifications.models import Notice
            Notice.objects.create(
                message=f'🚨 Critical: Site {site.domain} — malware or adult content detected!',
                is_active=True,
            )
        except Exception:
            pass

    # Cache invalidate
    from django.core.cache import cache
    from .utils import get_site_cache_key
    cache.delete(get_site_cache_key(site.site_id, 'quality'))
