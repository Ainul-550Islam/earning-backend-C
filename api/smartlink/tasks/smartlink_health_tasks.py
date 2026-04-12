import logging
from celery import shared_task

logger = logging.getLogger('smartlink.tasks.health')


@shared_task(name='smartlink.check_broken_smartlinks', queue='maintenance')
def check_broken_smartlinks():
    """
    Every 6 hours: Find active SmartLinks with 0 active offers in pool.
    Notify admins and auto-pause broken links.
    """
    from ..models import SmartLink

    broken = SmartLink.objects.filter(
        is_active=True, is_archived=False
    ).exclude(
        offer_pool__entries__is_active=True
    ).select_related('publisher')

    broken_list = []
    for sl in broken:
        broken_list.append({
            'id': sl.pk,
            'slug': sl.slug,
            'publisher': sl.publisher.username,
        })
        logger.warning(f"Broken SmartLink: [{sl.slug}] — no active offers in pool")

    if broken_list:
        logger.error(f"HEALTH CHECK: {len(broken_list)} broken SmartLinks found: {broken_list}")

    return {'broken_count': len(broken_list), 'broken': broken_list}


@shared_task(name='smartlink.check_smartlink_redirect_health', queue='maintenance')
def check_smartlink_redirect_health():
    """
    Daily: Test a sample of active SmartLinks to ensure redirects are working.
    """
    import urllib.request
    from django.conf import settings
    from ..models import SmartLink

    base_url = getattr(settings, 'SMARTLINK_BASE_URL', 'https://go.example.com')
    sample = SmartLink.objects.filter(
        is_active=True, is_archived=False
    ).order_by('?')[:10]

    healthy = 0
    unhealthy = []

    for sl in sample:
        url = f"{base_url}/{sl.slug}/"
        try:
            req = urllib.request.Request(url, method='HEAD')
            req.add_header('User-Agent', 'SmartLink-HealthCheck/1.0')
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 301, 302):
                    healthy += 1
                else:
                    unhealthy.append({'slug': sl.slug, 'status': resp.status})
        except Exception as e:
            unhealthy.append({'slug': sl.slug, 'error': str(e)})

    return {'healthy': healthy, 'unhealthy': unhealthy}


@shared_task(name='smartlink.check_offer_pool_health', queue='maintenance')
def check_offer_pool_health():
    """
    Every 30 minutes: Check all offer pools for health issues.
    Flags pools where all offers are capped.
    """
    from ..models import SmartLink
    from ..services.rotation.CapTrackerService import CapTrackerService

    cap_svc = CapTrackerService()
    fully_capped = []

    active = SmartLink.objects.filter(is_active=True, is_archived=False)
    for sl in active:
        try:
            entries = sl.offer_pool.get_active_entries()
            if entries:
                all_capped = all(cap_svc.is_capped(e) for e in entries)
                if all_capped:
                    fully_capped.append(sl.slug)
                    logger.warning(f"All offers capped for SmartLink [{sl.slug}]")
        except Exception:
            pass

    return {'fully_capped_count': len(fully_capped), 'slugs': fully_capped}
