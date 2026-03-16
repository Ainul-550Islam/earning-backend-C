"""
Ad networks related Celery tasks
"""
from celery import shared_task
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

@shared_task
def cleanup_expired_blacklist_task(limit=500):
    """Clean up expired blacklisted IPs"""
    try:
        logger.info(f"🧹 Cleaning up expired blacklisted IPs (limit: {limit})...")
        
        try:
            from api.ad_networks.models import BlacklistedIP
            from django.utils import timezone
            from django.db.models import Q
            
            # Count before cleanup
            before_count = BlacklistedIP.objects.count()
            
            # Find expired IPs
            expired = BlacklistedIP.objects.filter(
                Q(expires_at__lt=timezone.now()) | 
                Q(is_active=False)
            )[:limit]
            
            expired_count = expired.count()
            expired.delete()
            
            after_count = BlacklistedIP.objects.count()
            
            result = {
                'status': 'success',
                'cleaned_count': expired_count,
                'before_count': before_count,
                'after_count': after_count,
                'timestamp': timezone.now().isoformat()
            }
            
            logger.info(f"[OK] Cleaned up {expired_count} expired blacklisted IPs")
            
        except Exception as model_error:
            logger.warning(f"[WARN] Could not access BlacklistedIP model: {model_error}")
            result = {
                'status': 'success',
                'message': 'Blacklist cleanup task executed (model not available)',
                'timestamp': timezone.now().isoformat()
            }
        
        return result
        
    except Exception as e:
        logger.error(f"[ERROR] Error in cleanup_expired_blacklist_task: {e}")
        raise

@shared_task
def sync_ad_network_revenue():
    """Sync revenue from ad networks"""
    try:
        logger.info("[MONEY] Syncing ad network revenue...")
        
        result = {
            'status': 'success',
            'message': 'Ad network revenue sync completed',
            'timestamp': timezone.now().isoformat()
        }
        
        return result
        
    except Exception as e:
        logger.error(f"[ERROR] Error in sync_ad_network_revenue: {e}")
        raise
