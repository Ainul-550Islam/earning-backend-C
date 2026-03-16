# =============================================================================
# version_control/receivers.py
# =============================================================================
"""
Signal receivers for the version_control application.
Connected in AppConfig.ready(). Every receiver is wrapped in try/except.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import AppUpdatePolicy, MaintenanceSchedule, PlatformRedirect
from .signals import (
    maintenance_ended,
    maintenance_started,
    redirect_url_changed,
    update_policy_activated,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AppUpdatePolicy: emit signal on activation
# ---------------------------------------------------------------------------

@receiver(post_save, sender=AppUpdatePolicy)
def on_policy_saved(
    sender, instance: AppUpdatePolicy, created: bool, **kwargs: Any
) -> None:
    """Emit update_policy_activated whenever a policy becomes ACTIVE."""
    try:
        from .choices import PolicyStatus
        if instance.status == PolicyStatus.ACTIVE:
            update_policy_activated.send(
                sender=AppUpdatePolicy, policy=instance
            )
    except Exception:
        logger.exception("on_policy_saved.error pk=%s", instance.pk)


# ---------------------------------------------------------------------------
# MaintenanceSchedule: emit signals on status change
# ---------------------------------------------------------------------------

@receiver(post_save, sender=MaintenanceSchedule)
def on_maintenance_saved(
    sender, instance: MaintenanceSchedule, created: bool, **kwargs: Any
) -> None:
    """Emit maintenance_started / maintenance_ended on status transitions."""
    try:
        from .choices import MaintenanceStatus
        if instance.status == MaintenanceStatus.ACTIVE:
            maintenance_started.send(
                sender=MaintenanceSchedule, schedule=instance
            )
        elif instance.status == MaintenanceStatus.COMPLETED:
            maintenance_ended.send(
                sender=MaintenanceSchedule, schedule=instance
            )
    except Exception:
        logger.exception("on_maintenance_saved.error pk=%s", instance.pk)


# ---------------------------------------------------------------------------
# PlatformRedirect: cache invalidation + signal on URL change
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=PlatformRedirect)
def on_redirect_pre_save(
    sender, instance: PlatformRedirect, **kwargs: Any
) -> None:
    """
    Capture the old URL before the save so we can emit redirect_url_changed
    in post_save if the URL actually changed.
    """
    try:
        if instance.pk:
            old = PlatformRedirect.objects.get(pk=instance.pk)
            instance._old_url = old.url   # type: ignore[attr-defined]
        else:
            instance._old_url = ""        # type: ignore[attr-defined]
    except PlatformRedirect.DoesNotExist:
        instance._old_url = ""            # type: ignore[attr-defined]
    except Exception:
        logger.exception("on_redirect_pre_save.error pk=%s", instance.pk)


@receiver(post_save, sender=PlatformRedirect)
def on_redirect_saved(
    sender, instance: PlatformRedirect, created: bool, **kwargs: Any
) -> None:
    """Invalidate redirect cache and emit signal when URL changes."""
    try:
        old_url = getattr(instance, "_old_url", "")

        # Invalidate cache unconditionally on any save
        from django.core.cache import cache
        from .constants import CACHE_KEY_REDIRECT
        cache.delete(CACHE_KEY_REDIRECT.format(platform=instance.platform))

        if not created and old_url and old_url != instance.url:
            redirect_url_changed.send(
                sender=PlatformRedirect,
                redirect=instance,
                old_url=old_url,
            )
            logger.info(
                "redirect_url_changed platform=%s old=%s new=%s",
                instance.platform, old_url, instance.url,
            )
    except Exception:
        logger.exception("on_redirect_saved.error pk=%s", instance.pk)
