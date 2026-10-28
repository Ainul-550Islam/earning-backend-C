# api/admin_panel/services/MaintenanceModeService.py
"""Service for enabling/disabling maintenance mode and notifying users."""
import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class MaintenanceModeService:

    @classmethod
    def enable(cls, message: str = '', user=None, duration_minutes: int = 60) -> bool:
        """Enable maintenance mode immediately."""
        try:
            from ..models.config import MaintenanceWindow
            from datetime import timedelta
            window = MaintenanceWindow.objects.create(
                title='Emergency Maintenance',
                message=message or "We're currently performing maintenance. Please check back soon.",
                maintenance_type='emergency',
                start_at=timezone.now(),
                end_at=timezone.now() + timedelta(minutes=duration_minutes),
                is_active=True,
                created_by=user,
            )
            cache.set('admin_panel:maintenance_mode_active', True, duration_minutes * 60 + 120)
            cache.set('admin_panel:maintenance_message', window.message, 86400)
            logger.warning(f"Maintenance mode ENABLED by {user} for {duration_minutes} minutes.")
            return True
        except Exception as e:
            logger.error(f"MaintenanceModeService.enable error: {e}")
            return False

    @classmethod
    def disable(cls, user=None) -> bool:
        """Disable all active maintenance windows."""
        try:
            from ..models.config import MaintenanceWindow
            MaintenanceWindow.objects.filter(is_active=True).update(is_active=False)
            cache.delete('admin_panel:maintenance_mode_active')
            logger.info(f"Maintenance mode DISABLED by {user}.")
            return True
        except Exception as e:
            logger.error(f"MaintenanceModeService.disable error: {e}")
            return False

    @classmethod
    def is_active(cls) -> bool:
        """Check if maintenance mode is currently active."""
        return bool(cache.get('admin_panel:maintenance_mode_active', False))

    @classmethod
    def get_message(cls) -> str:
        """Get the current maintenance message."""
        return cache.get(
            'admin_panel:maintenance_message',
            "We're currently performing maintenance. Please check back soon."
        )