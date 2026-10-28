# =============================================================================
# auto_mod/signals.py
# =============================================================================

from django.dispatch import Signal

# Fired after ModerationService makes an auto-decision
# kwargs: submission (SuspiciousSubmission), decision (str)
moderation_decision_made = Signal()

# Fired when a submission is escalated
# kwargs: submission, escalated_to (User)
submission_escalated = Signal()

# Fired when an AutoApprovalRule fires for the first time today
# kwargs: rule (AutoApprovalRule), submission (SuspiciousSubmission)
rule_matched = Signal()

# Fired when a TaskBot changes status
# kwargs: bot (TaskBot), old_status (str), new_status (str)
bot_status_changed = Signal()

# Fired when an ML model is retrained and deployed
# kwargs: model_name (str), version (str)
model_retrained = Signal()

# =============================================================================
# New signals for enhanced moderation system
# =============================================================================

# Queue Management Signals
# Fired when a submission is added to the moderation queue
# kwargs: queue_item (ModerationQueue), priority (str)
queue_item_added = Signal()

# Fired when a queue item is assigned to a moderator
# kwargs: queue_item (ModerationQueue), assigned_to (User), assigned_by (User)
queue_item_assigned = Signal()

# Fired when a queue item is escalated
# kwargs: queue_item (ModerationQueue), old_level (int), new_level (int), reason (str)
queue_item_escalated = Signal()

# Fired when a queue item becomes overdue
# kwargs: queue_item (ModerationQueue), overdue_hours (int)
queue_item_overdue = Signal()

# Decision Management Signals
# Fired when a moderation decision is created
# kwargs: decision (ModerationDecision), submission (SuspiciousSubmission), decider (User/None)
decision_created = Signal()

# Fired when a decision is overridden
# kwargs: old_decision (ModerationDecision), new_decision (ModerationDecision), reason (str)
decision_overridden = Signal()

# Fired when an automated decision is reviewed by human
# kwargs: decision (ModerationDecision), reviewer (User), review_result (str)
decision_reviewed = Signal()

# Appeal Management Signals
# Fired when an appeal is created
# kwargs: appeal (ModerationAppeal), original_decision (ModerationDecision), appellant (User)
appeal_created = Signal()

# Fired when an appeal is assigned to a reviewer
# kwargs: appeal (ModerationAppeal), reviewer (User), assigned_by (User)
appeal_assigned = Signal()

# Fired when an appeal is resolved
# kwargs: appeal (ModerationAppeal), final_decision (str), reviewer (User)
appeal_resolved = Signal()

# Fired when an appeal is escalated to higher authority
# kwargs: appeal (ModerationAppeal), escalated_to (User), reason (str)
appeal_escalated = Signal()

# ML Model Management Signals
# Fired when an ML model version is created
# kwargs: model_version (MLModelVersion), model_type (str), version (str)
model_version_created = Signal()

# Fired when an ML model version training starts
# kwargs: model_version (MLModelVersion), training_config (dict)
model_training_started = Signal()

# Fired when an ML model version training completes
# kwargs: model_version (MLModelVersion), performance_metrics (dict)
model_training_completed = Signal()

# Fired when an ML model version is deployed
# kwargs: model_version (MLModelVersion), previous_version (MLModelVersion/None), deployed_by (User)
model_deployed = Signal()

# Fired when an ML model version is retired
# kwargs: model_version (MLModelVersion), retirement_reason (str), retired_by (User)
model_retired = Signal()

# Content Signal Management Signals
# Fired when a content signal is detected
# kwargs: signal (ContentSignal), submission (SuspiciousSubmission), signal_type (str)
signal_detected = Signal()

# Fired when multiple signals are aggregated for a submission
# kwargs: submission (SuspiciousSubmission), signals (list[ContentSignal]), aggregate_score (float)
signals_aggregated = Signal()

# Fired when signals are processed in decision making
# kwargs: submission (SuspiciousSubmission), processed_signals (list[ContentSignal]), decision (ModerationDecision)
signals_processed = Signal()

# System Integration Signals
# Fired when moderation workflow completes (all steps done)
# kwargs: submission (SuspiciousSubmission), final_decision (ModerationDecision), workflow_duration (timedelta)
workflow_completed = Signal()

# Fired when moderation metrics are calculated
# kwargs: metrics (dict), period_start (datetime), period_end (datetime)
metrics_calculated = Signal()

# Fired when system performance thresholds are exceeded
# kwargs: metric_name (str), current_value (float), threshold (float), severity (str)
performance_threshold_exceeded = Signal()

# Compliance and Audit Signals
# Fired when moderation action requires compliance review
# kwargs: submission (SuspiciousSubmission), action (str), compliance_flags (list[str])
compliance_review_required = Signal()

# Fired when audit trail entry is created
# kwargs: model_name (str), instance_id (str), action (str), user (User), metadata (dict)
audit_trail_created = Signal()

# Notification Signals
# Fired when moderator notification is needed
# kwargs: recipient (User), notification_type (str), context (dict), priority (str)
moderator_notification = Signal()

# Fired when user notification about moderation decision is needed
# kwargs: recipient (User), decision (ModerationDecision), submission (SuspiciousSubmission)
user_notification = Signal()

# Fired when system alert needs to be sent
# kwargs: alert_type (str), severity (str), message (str), context (dict), recipients (list[User])
system_alert = Signal()

queue_item_completed = Signal()

# Additional signals
submission_created = Signal()
submission_status_changed = Signal()
bot_started = Signal()
bot_stopped = Signal()
bot_failed = Signal()
site_approved = Signal()
site_rejected = Signal()
postback_received = Signal()
