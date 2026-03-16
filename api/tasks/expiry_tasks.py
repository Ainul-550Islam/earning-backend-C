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