# =============================================================================
# auto_mod/receivers.py
# =============================================================================

from __future__ import annotations

import logging
from typing import Any

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import (
    AutoApprovalRule, ContentSignal, MLModelVersion, 
    ModerationAppeal, ModerationDecision, ModerationQueue, 
    SuspiciousSubmission, TaskBot
)
from .signals import (
    bot_status_changed, moderation_decision_made, submission_escalated,
    # New signals
    queue_item_added, queue_item_assigned, queue_item_escalated, queue_item_overdue,
    decision_created, decision_overridden, decision_reviewed,
    appeal_created, appeal_assigned, appeal_resolved, appeal_escalated,
    model_version_created, model_training_started, model_training_completed, model_deployed, model_retired,
    signal_detected, signals_aggregated, signals_processed,
    workflow_completed, metrics_calculated, performance_threshold_exceeded,
    compliance_review_required, audit_trail_created,
    moderator_notification, user_notification, system_alert
)

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


# =============================================================================
# New Signal Handlers for Enhanced Moderation System
# =============================================================================

# ---------------------------------------------------------------------------
# ModerationQueue Signal Handlers
# ---------------------------------------------------------------------------

@receiver(post_save, sender=ModerationQueue)
def on_queue_item_created(
    sender, instance: ModerationQueue, created: bool, **kwargs: Any
) -> None:
    """Handle queue item creation."""
    if created:
        try:
            queue_item_added.send(
                sender=ModerationQueue,
                queue_item=instance,
                priority=instance.priority
            )
            logger.info(f"queue_item_added pk={instance.pk} priority={instance.priority}")
        except Exception:
            logger.exception("on_queue_item_created.error pk=%s", instance.pk)


@receiver(queue_item_assigned)
def on_queue_item_assigned(sender, **kwargs: Any) -> None:
    """Handle queue item assignment."""
    try:
        queue_item = kwargs.get("queue_item")
        assigned_to = kwargs.get("assigned_to")
        assigned_by = kwargs.get("assigned_by")
        
        logger.info(
            f"queue_item_assigned queue={queue_item.pk} "
            f"to={assigned_to.username if assigned_to else 'None'} "
            f"by={assigned_by.username if assigned_by else 'None'}"
        )
        
        # Send notification to assigned moderator
        if assigned_to:
            moderator_notification.send(
                sender=ModerationQueue,
                recipient=assigned_to,
                notification_type="queue_assignment",
                context={
                    "queue_item_id": str(queue_item.pk),
                    "submission_id": str(queue_item.submission.pk),
                    "priority": queue_item.priority
                },
                priority="normal"
            )
    except Exception:
        logger.exception("on_queue_item_assigned.error")


@receiver(queue_item_escalated)
def on_queue_item_escalated(sender, **kwargs: Any) -> None:
    """Handle queue item escalation."""
    try:
        queue_item = kwargs.get("queue_item")
        old_level = kwargs.get("old_level")
        new_level = kwargs.get("new_level")
        reason = kwargs.get("reason")
        
        logger.info(
            f"queue_item_escalated queue={queue_item.pk} "
            f"level={old_level}→{new_level} reason={reason}"
        )
        
        # Send system alert for high escalations
        if new_level >= 3:
            system_alert.send(
                sender=ModerationQueue,
                alert_type="queue_escalation",
                severity="high",
                message=f"Queue item escalated to level {new_level}",
                context={
                    "queue_item_id": str(queue_item.pk),
                    "escalation_level": new_level,
                    "reason": reason
                },
                recipients=[]  # resolved via adapter
                )
    except Exception:
        logger.exception("on_queue_item_escalated.error")


# ---------------------------------------------------------------------------
# ModerationDecision Signal Handlers
# ---------------------------------------------------------------------------

@receiver(post_save, sender=ModerationDecision)
def on_decision_created(
    sender, instance: ModerationDecision, created: bool, **kwargs: Any
) -> None:
    """Handle decision creation."""
    if created:
        try:
            decision_created.send(
                sender=ModerationDecision,
                decision=instance,
                submission=instance.submission,
                decider=instance.decided_by
            )
            logger.info(
                f"decision_created pk={instance.pk} type={instance.decision_type} "
                f"automated={instance.is_automated}"
            )
            
            # Send user notification for automated decisions
            if instance.is_automated and instance.submission.submitted_by:
                user_notification.send(
                    sender=ModerationDecision,
                    recipient=instance.submission.submitted_by,
                    decision=instance,
                    submission=instance.submission
                )
        except Exception:
            logger.exception("on_decision_created.error pk=%s", instance.pk)


@receiver(decision_overridden)
def on_decision_overridden(sender, **kwargs: Any) -> None:
    """Handle decision override."""
    try:
        old_decision = kwargs.get("old_decision")
        new_decision = kwargs.get("new_decision")
        reason = kwargs.get("reason")
        
        logger.info(
            f"decision_overridden old={old_decision.pk} new={new_decision.pk} "
            f"reason={reason}"
        )
        
        # Create audit trail
        audit_trail_created.send(
            sender=ModerationDecision,
            model_name="ModerationDecision",
            instance_id=str(new_decision.pk),
            action="override",
            user=new_decision.decided_by,
            metadata={
                "old_decision_id": str(old_decision.pk),
                "new_decision_id": str(new_decision.pk),
                "reason": reason
            }
        )
    except Exception:
        logger.exception("on_decision_overridden.error")


# ---------------------------------------------------------------------------
# ModerationAppeal Signal Handlers
# ---------------------------------------------------------------------------

@receiver(post_save, sender=ModerationAppeal)
def on_appeal_created(
    sender, instance: ModerationAppeal, created: bool, **kwargs: Any
) -> None:
    """Handle appeal creation."""
    if created:
        try:
            appeal_created.send(
                sender=ModerationAppeal,
                appeal=instance,
                original_decision=instance.original_decision,
                appellant=instance.user
            )
            logger.info(
                f"appeal_created pk={instance.pk} decision={instance.original_decision.pk} "
                f"user={instance.user.username}"
            )
            
            # Send notification to original decider if different from appellant
            if (instance.original_decision.decided_by and 
                instance.original_decision.decided_by != instance.user):
                moderator_notification.send(
                    sender=ModerationAppeal,
                    recipient=instance.original_decision.decided_by,
                    notification_type="appeal_created",
                    context={
                        "appeal_id": str(instance.pk),
                        "original_decision_id": str(instance.original_decision.pk),
                        "appellant": instance.user.username
                    },
                    priority="high"
                )
        except Exception:
            logger.exception("on_appeal_created.error pk=%s", instance.pk)


@receiver(appeal_resolved)
def on_appeal_resolved(sender, **kwargs: Any) -> None:
    """Handle appeal resolution."""
    try:
        appeal = kwargs.get("appeal")
        final_decision = kwargs.get("final_decision")
        reviewer = kwargs.get("reviewer")
        
        logger.info(
            f"appeal_resolved pk={appeal.pk} final={final_decision} "
            f"reviewer={reviewer.username if reviewer else 'None'}"
        )
        
        # Send user notification about appeal result
        user_notification.send(
            sender=ModerationAppeal,
            recipient=appeal.user,
            decision=appeal.original_decision,
            submission=appeal.submission
        )
        
        # Create audit trail
        audit_trail_created.send(
            sender=ModerationAppeal,
            model_name="ModerationAppeal",
            instance_id=str(appeal.pk),
            action="resolve",
            user=reviewer,
            metadata={
                "appeal_id": str(appeal.pk),
                "final_decision": final_decision,
                "was_successful": appeal.was_successful
            }
        )
    except Exception:
        logger.exception("on_appeal_resolved.error")


# ---------------------------------------------------------------------------
# MLModelVersion Signal Handlers
# ---------------------------------------------------------------------------

@receiver(post_save, sender=MLModelVersion)
def on_model_version_created(
    sender, instance: MLModelVersion, created: bool, **kwargs: Any
) -> None:
    """Handle model version creation."""
    if created:
        try:
            model_version_created.send(
                sender=MLModelVersion,
                model_version=instance,
                model_type=instance.model_type,
                version=instance.version
            )
            logger.info(
                f"model_version_created pk={instance.pk} type={instance.model_type} "
                f"version={instance.version}"
            )
        except Exception:
            logger.exception("on_model_version_created.error pk=%s", instance.pk)


@receiver(model_deployed)
def on_model_deployed(sender, **kwargs: Any) -> None:
    """Handle model deployment."""
    try:
        model_version = kwargs.get("model_version")
        previous_version = kwargs.get("previous_version")
        deployed_by = kwargs.get("deployed_by")
        
        logger.info(
            f"model_deployed model={model_version.pk} version={model_version.version} "
            f"previous={previous_version.pk if previous_version else 'None'}"
        )
        
        # Send system alert for model deployment
        system_alert.send(
            sender=MLModelVersion,
            alert_type="model_deployment",
            severity="info",
            message=f"ML model {model_version.model_type} v{model_version.version} deployed",
            context={
                "model_version_id": str(model_version.pk),
                "model_type": model_version.model_type,
                "version": model_version.version,
                "accuracy": model_version.accuracy
            },
            recipients=[]
                )
    except Exception:
        logger.exception("on_model_deployed.error")


# ---------------------------------------------------------------------------
# ContentSignal Signal Handlers
# ---------------------------------------------------------------------------

@receiver(post_save, sender=ContentSignal)
def on_signal_detected(
    sender, instance: ContentSignal, created: bool, **kwargs: Any
) -> None:
    """Handle signal detection."""
    if created:
        try:
            signal_detected.send(
                sender=ContentSignal,
                signal=instance,
                submission=instance.submission,
                signal_type=instance.signal_type
            )
            logger.info(
                f"signal_detected pk={instance.pk} type={instance.signal_type} "
                f"submission={instance.submission.pk}"
            )
            
            # Check if this signal requires immediate attention
            if instance.weight >= 5.0 or instance.severity == "critical":
                system_alert.send(
                    sender=ContentSignal,
                    alert_type="high_impact_signal",
                    severity="high",
                    message=f"High impact signal detected: {instance.signal_type}",
                    context={
                        "signal_id": str(instance.pk),
                        "signal_type": instance.signal_type,
                        "weight": instance.weight,
                        "severity": instance.severity,
                        "submission_id": str(instance.submission.pk)
                    },
                    recipients=[]  # Moderator recipients resolved via adapter
                )
        except Exception:
            logger.exception("on_signal_detected.error pk=%s", instance.pk)


@receiver(signals_aggregated)
def on_signals_aggregated(sender, **kwargs: Any) -> None:
    """Handle signal aggregation."""
    try:
        submission = kwargs.get("submission")
        signals = kwargs.get("signals")
        aggregate_score = kwargs.get("aggregate_score")
        
        logger.info(
            f"signals_aggregated submission={submission.pk} "
            f"signals={len(signals)} score={aggregate_score}"
        )
        
        # Check compliance requirements
        if aggregate_score >= 8.0:
            compliance_review_required.send(
                sender=ContentSignal,
                submission=submission,
                action="high_risk_content",
                compliance_flags=["high_aggregate_score", "multiple_signals"]
            )
    except Exception:
        logger.exception("on_signals_aggregated.error")


# ---------------------------------------------------------------------------
# System Integration Signal Handlers
# ---------------------------------------------------------------------------

@receiver(workflow_completed)
def on_workflow_completed(sender, **kwargs: Any) -> None:
    """Handle workflow completion."""
    try:
        submission = kwargs.get("submission")
        final_decision = kwargs.get("final_decision")
        workflow_duration = kwargs.get("workflow_duration")
        
        logger.info(
            f"workflow_completed submission={submission.pk} "
            f"decision={final_decision.decision_type} "
            f"duration={workflow_duration.total_seconds():.2f}s"
        )
        
        # Create audit trail
        audit_trail_created.send(
            sender=None,
            model_name="SuspiciousSubmission",
            instance_id=str(submission.pk),
            action="workflow_completed",
            user=final_decision.decided_by,
            metadata={
                "submission_id": str(submission.pk),
                "final_decision_id": str(final_decision.pk),
                "workflow_duration_seconds": workflow_duration.total_seconds(),
                "decision_type": final_decision.decision_type
            }
        )
    except Exception:
        logger.exception("on_workflow_completed.error")


@receiver(metrics_calculated)
def on_metrics_calculated(sender, **kwargs: Any) -> None:
    """Handle metrics calculation."""
    try:
        metrics = kwargs.get("metrics")
        period_start = kwargs.get("period_start")
        period_end = kwargs.get("period_end")
        
        logger.info(
            f"metrics_calculated period={period_start}→{period_end} "
            f"submissions={metrics.get('total_submissions', 0)} "
            f"decisions={metrics.get('total_decisions', 0)}"
        )
        
        # Check performance thresholds
        avg_confidence = metrics.get("avg_confidence", 0)
        if avg_confidence < 0.7:
            performance_threshold_exceeded.send(
                sender=None,
                metric_name="avg_confidence",
                current_value=avg_confidence,
                threshold=0.7,
                severity="medium"
            )
    except Exception:
        logger.exception("on_metrics_calculated.error")


@receiver(performance_threshold_exceeded)
def on_performance_threshold_exceeded(sender, **kwargs: Any) -> None:
    """Handle performance threshold breaches."""
    try:
        metric_name = kwargs.get("metric_name")
        current_value = kwargs.get("current_value")
        threshold = kwargs.get("threshold")
        severity = kwargs.get("severity")
        
        logger.warning(
            f"performance_threshold_exceeded metric={metric_name} "
            f"value={current_value} threshold={threshold} severity={severity}"
        )
        
        # Send system alert
        system_alert.send(
            sender=None,
            alert_type="performance_threshold",
            severity=severity,
            message=f"Performance threshold exceeded: {metric_name}",
            context={
                "metric_name": metric_name,
                "current_value": current_value,
                "threshold": threshold,
                "severity": severity
            },
            recipients=[]
                )
    except Exception:
        logger.exception("on_performance_threshold_exceeded.error")


# ---------------------------------------------------------------------------
# Compliance and Audit Signal Handlers
# ---------------------------------------------------------------------------

@receiver(compliance_review_required)
def on_compliance_review_required(sender, **kwargs: Any) -> None:
    """Handle compliance review requirements."""
    try:
        submission = kwargs.get("submission")
        action = kwargs.get("action")
        compliance_flags = kwargs.get("compliance_flags")
        
        logger.info(
            f"compliance_review_required submission={submission.pk} "
            f"action={action} flags={compliance_flags}"
        )
        
        # Send high priority alert to compliance team
        system_alert.send(
            sender=None,
            alert_type="compliance_review",
            severity="high",
            message=f"Compliance review required: {action}",
            context={
                "submission_id": str(submission.pk),
                "action": action,
                "compliance_flags": compliance_flags
            },
            recipients=[]  # Compliance team resolved via adapter
        )
    except Exception:
        logger.exception("on_compliance_review_required.error")


@receiver(audit_trail_created)
def on_audit_trail_created(sender, **kwargs: Any) -> None:
    """Handle audit trail creation."""
    try:
        model_name = kwargs.get("model_name")
        instance_id = kwargs.get("instance_id")
        action = kwargs.get("action")
        user = kwargs.get("user")
        metadata = kwargs.get("metadata")
        
        logger.info(
            f"audit_trail_created model={model_name} instance={instance_id} "
            f"action={action} user={user.username if user else 'None'}"
        )
    except Exception:
        logger.exception("on_audit_trail_created.error")


# ---------------------------------------------------------------------------
# Notification Signal Handlers
# ---------------------------------------------------------------------------

@receiver(moderator_notification)
def on_moderator_notification(sender, **kwargs: Any) -> None:
    """Handle moderator notifications."""
    try:
        recipient = kwargs.get("recipient")
        notification_type = kwargs.get("notification_type")
        context = kwargs.get("context")
        priority = kwargs.get("priority")
        
        logger.info(
            f"moderator_notification recipient={recipient.username} "
            f"type={notification_type} priority={priority}"
        )
        
        # This could integrate with email, SMS, push notifications, etc.
        
    except Exception:
        logger.exception("on_moderator_notification.error")


@receiver(user_notification)
def on_user_notification(sender, **kwargs: Any) -> None:
    """Handle user notifications."""
    try:
        recipient = kwargs.get("recipient")
        decision = kwargs.get("decision")
        submission = kwargs.get("submission")
        
        logger.info(
            f"user_notification recipient={recipient.username} "
            f"decision={decision.decision_type} submission={submission.pk}"
        )
        
        
    except Exception:
        logger.exception("on_user_notification.error")


@receiver(system_alert)
def on_system_alert(sender, **kwargs: Any) -> None:
    """Handle system alerts."""
    try:
        alert_type = kwargs.get("alert_type")
        severity = kwargs.get("severity")
        message = kwargs.get("message")
        context = kwargs.get("context")
        recipients = kwargs.get("recipients")
        
        logger.warning(
            f"system_alert type={alert_type} severity={severity} "
            f"message={message} recipients={len(recipients)}"
        )
        
        # This could integrate with monitoring systems, Slack, etc.
        
    except Exception:
        logger.exception("on_system_alert.error")

# =============================================================================
# Additional signal receivers (auto-generated for completeness)
# =============================================================================

from .signals import (
    submission_created, submission_status_changed,
    bot_started, bot_stopped,
)


@receiver(submission_created)
def on_submission_created(sender, submission, **kwargs):
    """Handle new submission creation — start SLA timer, record risk history."""
    try:
        from .missing_components import SLATracker, RiskScoreHistory
        SLATracker.start("submission", str(submission.pk))
        if submission.risk_score:
            RiskScoreHistory.record("submission", str(submission.pk),
                                    float(submission.risk_score))
        logger.debug("on_submission_created: pk=%s", submission.pk)
    except Exception as exc:
        logger.exception("on_submission_created.error")


@receiver(submission_status_changed)
def on_submission_status_changed(sender, submission, old_status, new_status, **kwargs):
    """Handle status change — track analytics, complete SLA if resolved."""
    try:
        from .missing_components import SLATracker
        FINAL = {"auto_approved","auto_rejected","human_approved","human_rejected"}
        if new_status in FINAL:
            SLATracker.complete("submission", str(submission.pk))
        from .adapters import AdapterRegistry
        AdapterRegistry.analytics.track_event(
            "auto_mod.status_changed",
            {"submission_id": str(submission.pk),
             "old_status": old_status, "new_status": new_status}
        )
    except Exception as exc:
        logger.exception("on_submission_status_changed.error")


@receiver(bot_started)
def on_bot_started(sender, bot, **kwargs):
    """Handle bot start — notify alerts, update dashboard."""
    try:
        from .adapters import AdapterRegistry
        AdapterRegistry.alerts.send_alert(
            title=f"Bot Started: {bot.name}",
            message=f"Bot {bot.name} ({bot.bot_type}) started.",
            severity="info",
        )
    except Exception as exc:
        logger.exception("on_bot_started.error")


@receiver(bot_stopped)
def on_bot_stopped(sender, bot, **kwargs):
    """Handle bot stop — log event."""
    try:
        logger.info("bot.stopped name=%r type=%r", bot.name, bot.bot_type)
    except Exception as exc:
        logger.exception("on_bot_stopped.error")
