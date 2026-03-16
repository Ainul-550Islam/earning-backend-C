# =============================================================================
# auto_mod/receivers.py
# =============================================================================

from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import AutoApprovalRule, SuspiciousSubmission, TaskBot
from .signals import bot_status_changed, moderation_decision_made, submission_escalated

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SuspiciousSubmission: emit decision signal on status change
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=SuspiciousSubmission)
def on_submission_pre_save(sender, instance: SuspiciousSubmission, **kwargs: Any) -> None:
    """Capture old status before save for change detection."""
    try:
        if instance.pk:
            old = SuspiciousSubmission.objects.get(pk=instance.pk)
            instance._old_status = old.status
        else:
            instance._old_status = ""
    except SuspiciousSubmission.DoesNotExist:
        instance._old_status = ""
    except Exception:
        instance._old_status = ""


@receiver(post_save, sender=SuspiciousSubmission)
def on_submission_saved(
    sender, instance: SuspiciousSubmission, created: bool, **kwargs: Any
) -> None:
    """Emit moderation_decision_made when status changes to a terminal state."""
    try:
        from .choices import ModerationStatus
        TERMINAL = {
            ModerationStatus.AUTO_APPROVED,
            ModerationStatus.AUTO_REJECTED,
            ModerationStatus.HUMAN_APPROVED,
            ModerationStatus.HUMAN_REJECTED,
            ModerationStatus.ESCALATED,
        }
        old_status = getattr(instance, "_old_status", "")
        if instance.status in TERMINAL and instance.status != old_status:
            moderation_decision_made.send(
                sender=SuspiciousSubmission,
                submission=instance,
                decision=instance.status,
            )
            logger.info(
                "receiver.decision_made pk=%s decision=%s",
                instance.pk, instance.status,
            )

        if instance.status == ModerationStatus.ESCALATED and instance.status != old_status:
            submission_escalated.send(
                sender=SuspiciousSubmission,
                submission=instance,
                escalated_to=instance.escalated_to,
            )
    except Exception:
        logger.exception("on_submission_saved.error pk=%s", instance.pk)


# ---------------------------------------------------------------------------
# AutoApprovalRule: invalidate rule cache on save/delete
# ---------------------------------------------------------------------------

@receiver(post_save, sender=AutoApprovalRule)
def on_rule_saved(
    sender, instance: AutoApprovalRule, created: bool, **kwargs: Any
) -> None:
    try:
        from django.core.cache import cache
        from .constants import CACHE_KEY_ACTIVE_RULES
        cache.delete(CACHE_KEY_ACTIVE_RULES.format(submission_type=instance.submission_type))
        logger.debug("rule_cache.invalidated submission_type=%s", instance.submission_type)
    except Exception:
        logger.exception("on_rule_saved.cache_invalidation_failed pk=%s", instance.pk)


# ---------------------------------------------------------------------------
# TaskBot: emit status change signal
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=TaskBot)
def on_bot_pre_save(sender, instance: TaskBot, **kwargs: Any) -> None:
    try:
        if instance.pk:
            old = TaskBot.objects.get(pk=instance.pk)
            instance._old_bot_status = old.status
        else:
            instance._old_bot_status = ""
    except TaskBot.DoesNotExist:
        instance._old_bot_status = ""
    except Exception:
        instance._old_bot_status = ""


@receiver(post_save, sender=TaskBot)
def on_bot_saved(
    sender, instance: TaskBot, created: bool, **kwargs: Any
) -> None:
    try:
        old_status = getattr(instance, "_old_bot_status", "")
        if instance.status != old_status and old_status:
            bot_status_changed.send(
                sender=TaskBot,
                bot=instance,
                old_status=old_status,
                new_status=instance.status,
            )
            logger.info(
                "bot.status_changed pk=%s %s→%s",
                instance.pk, old_status, instance.status,
            )
    except Exception:
        logger.exception("on_bot_saved.error pk=%s", instance.pk)
