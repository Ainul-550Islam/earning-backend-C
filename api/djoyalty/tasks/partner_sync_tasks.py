# api/djoyalty/tasks/partner_sync_tasks.py
"""
Celery task: Partner merchant sync।
Schedule: Every 60 minutes।
"""
import logging

try:
    from celery import shared_task
except ImportError:
    def shared_task(func=None, **kwargs):
        if func:
            return func
        def decorator(f):
            return f
        return decorator

logger = logging.getLogger(__name__)


@shared_task(name='djoyalty.sync_partners', bind=True, max_retries=3)
def sync_partners_task(self):
    """
    সব active partner merchants sync করো।
    last_sync_at update করে।
    Returns: count of synced partners
    """
    try:
        from django.utils import timezone
        from ..models.campaigns import PartnerMerchant

        partners = PartnerMerchant.objects.filter(is_active=True)
        count = partners.update(last_sync_at=timezone.now())
        logger.info('[djoyalty] Partners synced: %d', count)
        return count

    except Exception as exc:
        logger.error('[djoyalty] sync_partners error: %s', exc)
        raise self.retry(exc=exc, countdown=120) if hasattr(self, 'retry') else exc


@shared_task(name='djoyalty.check_partner_webhooks', bind=True, max_retries=3)
def check_partner_webhooks_task(self):
    """
    Partner এর webhook URLs check করো — alive কিনা।
    Returns: dict with active/failed counts
    """
    try:
        from ..models.campaigns import PartnerMerchant
        import urllib.request

        partners = PartnerMerchant.objects.filter(is_active=True, webhook_url__isnull=False).exclude(webhook_url='')
        active = 0
        failed = 0

        for partner in partners:
            try:
                req = urllib.request.Request(
                    partner.webhook_url, method='HEAD',
                    headers={'User-Agent': 'DjoyaltyHealthCheck/1.0'},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status < 400:
                        active += 1
                    else:
                        failed += 1
                        logger.warning('[djoyalty] Partner webhook down: %s (status=%d)', partner.name, resp.status)
            except Exception:
                failed += 1
                logger.warning('[djoyalty] Partner webhook unreachable: %s', partner.name)

        logger.info('[djoyalty] Partner webhook check: %d active, %d failed', active, failed)
        return {'active': active, 'failed': failed}

    except Exception as exc:
        logger.error('[djoyalty] check_partner_webhooks error: %s', exc)
        raise self.retry(exc=exc, countdown=300) if hasattr(self, 'retry') else exc
