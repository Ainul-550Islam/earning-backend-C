# api/tasks/expiry_tasks.py

import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

logger = logging.getLogger(__name__)

@shared_task
def cleanup_expired_ips_task():
    """
    এক্সপায়ার্ড KnownBadIP রেকর্ডগুলো মুছে ফেলা
    """
    try:
        from api.ad_networks.models import KnownBadIP
        
        current_time = timezone.now()
        
        # এক্সপায়ার্ড আইপি খুঁজুন (expires_at অতীতের সময়ে আছে)
        expired_ips = KnownBadIP.objects.filter(
            Q(expires_at__lt=current_time) & Q(expires_at__isnull=False)
        )
        
        count = expired_ips.count()
        
        if count > 0:
            with transaction.atomic():
                deleted, _ = expired_ips.delete()
            
            logger.info(f"[OK] Cleaned up {deleted} expired IPs from KnownBadIP")
            
            # আরও সেফটির জন্য, is_active ফ্লাগ আপডেট করুন
            # তাহলে ডিলিট না করেও ডিসেবল করতে পারবেন
            KnownBadIP.objects.filter(
                Q(expires_at__lt=current_time) & Q(expires_at__isnull=False)
            ).update(is_active=False)
            
            return f"Successfully cleaned up {deleted} expired IPs"
        else:
            logger.info("[OK] No expired IPs found")
            return "No expired IPs found"
            
    except Exception as e:
        logger.error(f"[ERROR] Error in cleanup_expired_ips_task: {e}")
        raise

@shared_task
def deactivate_old_ips_task(days_old=30):
    """
    ৩০ দিনের বেশি পুরনো আইপিগুলোকে ডিসেবল করা (ডিলিট না করে)
    """
    try:
        from api.ad_networks.models import KnownBadIP
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        old_ips = KnownBadIP.objects.filter(
            last_seen__lt=cutoff_date,
            is_active=True
        )
        
        count = old_ips.count()
        
        if count > 0:
            old_ips.update(is_active=False)
            logger.info(f"[OK] Deactivated {count} old IPs (older than {days_old} days)")
            return f"Deactivated {count} old IPs"
        else:
            logger.info(f"[OK] No IPs older than {days_old} days")
            return "No old IPs found"
            
    except Exception as e:
        logger.error(f"[ERROR] Error in deactivate_old_ips_task: {e}")
        raise

# ── Extended expiry tasks ─────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.expiry_tasks.expire_kyc_verifications')
def expire_kyc_verifications(self) -> dict:
    """Mark KYC verifications as expired after their validity period."""
    try:
        from datetime import timedelta
        from django.utils import timezone as tz
        expired = 0
        cutoff  = tz.now() - timedelta(days=365)  # KYC valid for 1 year
        try:
            from users.models import KYCVerification
            expired = KYCVerification.objects.filter(
                status='approved', approved_at__lt=cutoff
            ).update(status='expired')
        except ImportError:
            pass
        return {'status': 'success', 'expired': expired,
                'timestamp': tz.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name='tasks.expiry_tasks.expire_promotional_codes')
def expire_promotional_codes(self) -> dict:
    """Expire promo codes past their validity date."""
    try:
        from django.utils import timezone as tz
        expired = 0
        try:
            from promotions.models import PromoCode
            expired = PromoCode.objects.filter(
                is_active=True, expires_at__lt=tz.now()
            ).update(is_active=False)
        except ImportError:
            pass
        return {'status': 'success', 'expired': expired,
                'timestamp': tz.now().isoformat()}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=30,
             name='tasks.expiry_tasks.expire_download_tokens')
def expire_download_tokens(self) -> dict:
    """Remove expired file download tokens from cache."""
    from django.core.cache import cache as _c
    from django.utils import timezone as tz
    # Download tokens auto-expire via Redis TTL
    # This task just logs the cleanup cycle
    return {'status': 'success', 'message': 'Download tokens auto-expire via Redis TTL',
            'timestamp': tz.now().isoformat()}
