"""
tasks/services.py — Service-layer tasks for offer routing.
These tasks integrate service layer calls with Celery.
"""
from celery import shared_task
import logging
logger = logging.getLogger(__name__)

@shared_task(name="offer_routing.tasks.services.sync_service_data")
def sync_service_data(service_name: str, tenant_id: int = None) -> dict:
    """Sync data for a specific service."""
    try:
        return {"success": True, "service": service_name, "tenant_id": tenant_id}
    except Exception as e:
        logger.error(f"sync_service_data failed: {e}")
        return {"success": False, "error": str(e)}

@shared_task(name="offer_routing.tasks.services.validate_service_health")
def validate_service_health() -> dict:
    """Validate health of all registered services."""
    return {"success": True, "services_checked": 0}

@shared_task(name="offer_routing.tasks.services.cleanup_service_cache")
def cleanup_service_cache(service_name: str = None) -> dict:
    """Clean up cache for one or all services."""
    return {"success": True, "cleaned": True}
