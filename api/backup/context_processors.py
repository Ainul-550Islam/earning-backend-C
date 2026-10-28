"""
Backup Module Context Processors
Django context processors for injecting backup data into templates.
"""

import logging
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_KEY_BACKUP_SUMMARY = "backup_module_context_summary"
CACHE_TIMEOUT = 300  # 5 minutes


def backup_status_context(request):
    """
    Inject backup system status into every template context.
    Only adds data for authenticated staff users to avoid unnecessary DB hits.
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    if not request.user.is_staff:
        return {}

    cached = cache.get(CACHE_KEY_BACKUP_SUMMARY)
    if cached is not None:
        return {"backup_context": cached}

    try:
        from api.backup.repositories import BackupRepository
        repo = BackupRepository()
        counts = repo.count_by_status()
        total = sum(counts.values())
        context = {
            "backup_total": total,
            "backup_running": counts.get("running", 0),
            "backup_failed_recent": counts.get("failed", 0),
            "backup_system_healthy": counts.get("failed", 0) == 0,
        }
        cache.set(CACHE_KEY_BACKUP_SUMMARY, context, CACHE_TIMEOUT)
        return {"backup_context": context}
    except Exception as exc:
        logger.warning("backup_status_context error: %s", exc)
        return {}


def backup_feature_flags_context(request):
    """Inject active feature flags into template context"""
    from api.backup.feature_flags import flag_is_active
    return {
        "backup_flags": {
            "encryption_enabled": flag_is_active("backup_encryption"),
            "compression_enabled": flag_is_active("backup_compression"),
            "gcs_enabled": flag_is_active("gcs_storage"),
            "azure_enabled": flag_is_active("azure_storage"),
        }
    }
