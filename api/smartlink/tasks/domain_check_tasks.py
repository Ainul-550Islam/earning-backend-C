import logging
from celery import shared_task

logger = logging.getLogger('smartlink.tasks.domain')


@shared_task(name='smartlink.verify_pending_domains', queue='default')
def verify_pending_domains():
    """Every 6 hours: attempt to verify all pending custom domains."""
    from ..models.publisher import PublisherDomain
    from ..choices import DomainVerificationStatus
    from ..services.core.DomainService import DomainService

    svc = DomainService()
    pending = PublisherDomain.objects.filter(
        verification_status__in=[
            DomainVerificationStatus.PENDING,
            DomainVerificationStatus.FAILED,
        ]
    )

    verified = 0
    failed = 0
    for domain_obj in pending:
        try:
            svc.verify(domain_obj)
            verified += 1
        except Exception:
            failed += 1

    logger.info(f"Domain verify task: {verified} verified, {failed} failed")
    return {'verified': verified, 'failed': failed}


@shared_task(name='smartlink.check_ssl_expiry', queue='default')
def check_ssl_expiry():
    """Daily: Check SSL certificate expiry for all verified domains."""
    import datetime
    from django.utils import timezone
    from ..models.publisher import PublisherDomain
    from ..choices import DomainVerificationStatus
    from ..services.core.DomainService import DomainService

    svc = DomainService()
    verified_domains = PublisherDomain.objects.filter(
        verification_status=DomainVerificationStatus.VERIFIED,
        ssl_enabled=True,
    )

    expiring_soon = []
    for domain_obj in verified_domains:
        try:
            result = svc.check_ssl(domain_obj)
            if result.get('expires_at'):
                days_left = (result['expires_at'] - timezone.now()).days
                if days_left <= 30:
                    expiring_soon.append({'domain': domain_obj.domain, 'days_left': days_left})
                    logger.warning(f"SSL expiring in {days_left} days: {domain_obj.domain}")
        except Exception as e:
            logger.warning(f"SSL check failed for {domain_obj.domain}: {e}")

    return {'expiring_soon': expiring_soon}
