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
