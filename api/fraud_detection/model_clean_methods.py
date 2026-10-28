# =============================================================================
# model_clean_methods.py
# GAP 1 FIX — clean() validation methods for all 14 models
#
# HOW TO APPLY:
#   The patch_models() function below monkey-patches clean() onto each model
#   class at startup.  Import and call it from AppConfig.ready() in apps.py:
#
#       from .model_clean_methods import patch_models
#       patch_models()
#
#   This avoids editing every migration and keeps models.py minimal while
#   enforcing invariants at the ORM layer (bypassing serializer-only guards).
# =============================================================================
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils import timezone


# ---------------------------------------------------------------------------
# FraudSettings
# ---------------------------------------------------------------------------
def _fraud_settings_clean(self):
    errors = {}
    if not (0 <= self.global_risk_threshold <= 100):
        errors['global_risk_threshold'] = (
            'Risk threshold must be between 0 and 100.'
        )
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# FraudRule
# ---------------------------------------------------------------------------
def _fraud_rule_clean(self):
    errors = {}
    if self.weight is not None and not (1 <= self.weight <= 100):
        errors['weight'] = 'Weight must be between 1 and 100.'
    if self.threshold is not None and not (1 <= self.threshold <= 100):
        errors['threshold'] = 'Threshold must be between 1 and 100.'
    if self.name and len(self.name.strip()) == 0:
        errors['name'] = 'Rule name cannot be blank whitespace.'
    if self.last_triggered and self.created_at and self.last_triggered < self.created_at:
        errors['last_triggered'] = (
            'last_triggered cannot be before the rule was created.'
        )
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# FraudAttempt
# ---------------------------------------------------------------------------
def _fraud_attempt_clean(self):
    errors = {}
    if self.fraud_score is not None and not (0 <= self.fraud_score <= 100):
        errors['fraud_score'] = 'Fraud score must be between 0 and 100.'
    if self.confidence_score is not None and not (0 <= self.confidence_score <= 100):
        errors['confidence_score'] = 'Confidence score must be between 0 and 100.'
    if self.amount_involved is not None and self.amount_involved < 0:
        errors['amount_involved'] = 'Amount involved cannot be negative.'
    if self.is_resolved and not self.resolved_at:
        errors['resolved_at'] = (
            'resolved_at must be set when is_resolved is True.'
        )
    if self.resolved_at and self.created_at and self.resolved_at < self.created_at:
        errors['resolved_at'] = (
            'resolved_at cannot be before the attempt was created.'
        )
    valid_statuses = {s[0] for s in self.STATUS_CHOICES}
    if self.status and self.status not in valid_statuses:
        errors['status'] = f'Invalid status "{self.status}".'
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# FraudPattern
# ---------------------------------------------------------------------------
def _fraud_pattern_clean(self):
    errors = {}
    if self.accuracy_rate is not None and not (0.0 <= self.accuracy_rate <= 1.0):
        errors['accuracy_rate'] = 'Accuracy rate must be between 0.0 and 1.0.'
    if self.occurrence_count is not None and self.occurrence_count < 0:
        errors['occurrence_count'] = 'Occurrence count cannot be negative.'
    if self.is_trained and not self.last_trained:
        errors['last_trained'] = (
            'last_trained must be set when the pattern is marked as trained.'
        )
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# UserRiskProfile
# ---------------------------------------------------------------------------
def _user_risk_profile_clean(self):
    errors = {}
    score_fields = [
        ('risk_score', self.risk_score),
        ('account_risk_score', self.account_risk_score),
        ('payment_risk_score', self.payment_risk_score),
        ('behavior_risk_score', self.behavior_risk_score),
    ]
    for field_name, value in score_fields:
        if value is not None and not (0 <= value <= 100):
            errors[field_name] = f'{field_name} must be between 0 and 100.'
    if self.confirmed_fraud_attempts is not None and self.total_fraud_attempts is not None:
        if self.confirmed_fraud_attempts > self.total_fraud_attempts:
            errors['confirmed_fraud_attempts'] = (
                'Confirmed fraud attempts cannot exceed total fraud attempts.'
            )
    if self.next_assessment_due and self.last_risk_assessment:
        if self.next_assessment_due <= self.last_risk_assessment:
            errors['next_assessment_due'] = (
                'next_assessment_due must be after last_risk_assessment.'
            )
    valid_levels = {'normal', 'enhanced', 'strict'}
    if self.monitoring_level and self.monitoring_level not in valid_levels:
        errors['monitoring_level'] = (
            f'Invalid monitoring level "{self.monitoring_level}".'
        )
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# DeviceFingerprint
# ---------------------------------------------------------------------------
def _device_fingerprint_clean(self):
    errors = {}
    if self.trust_score is not None and not (0 <= self.trust_score <= 100):
        errors['trust_score'] = 'Trust score must be between 0 and 100.'
    if self.cpu_cores is not None and self.cpu_cores < 0:
        errors['cpu_cores'] = 'cpu_cores cannot be negative.'
    if self.device_memory is not None and self.device_memory < 0:
        errors['device_memory'] = 'device_memory cannot be negative.'
    if self.is_bot and self.trust_score is not None and self.trust_score > 20:
        errors['trust_score'] = (
            'A device flagged as bot should have trust_score ≤ 20.'
        )
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# IPReputation
# ---------------------------------------------------------------------------
def _ip_reputation_clean(self):
    errors = {}
    score_fields = [
        ('fraud_score', self.fraud_score),
        ('spam_score', self.spam_score),
        ('malware_score', self.malware_score),
    ]
    for field_name, value in score_fields:
        if value is not None and not (0 <= value <= 100):
            errors[field_name] = f'{field_name} must be between 0 and 100.'
    if self.fraud_attempts is not None and self.total_requests is not None:
        if self.fraud_attempts > self.total_requests:
            errors['fraud_attempts'] = (
                'fraud_attempts cannot exceed total_requests.'
            )
    if self.unique_users is not None and self.unique_users < 0:
        errors['unique_users'] = 'unique_users cannot be negative.'
    if self.is_blacklisted and not self.blacklist_reason:
        errors['blacklist_reason'] = (
            'blacklist_reason must be provided when IP is blacklisted.'
        )
    if self.blacklisted_at and self.created_at and self.blacklisted_at < self.created_at:
        errors['blacklisted_at'] = (
            'blacklisted_at cannot be before the record was created.'
        )
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# FraudAlert
# ---------------------------------------------------------------------------
def _fraud_alert_clean(self):
    errors = {}
    valid_priorities = {p[0] for p in self.PRIORITY_LEVELS}
    if self.priority and self.priority not in valid_priorities:
        errors['priority'] = f'Invalid priority "{self.priority}".'
    valid_types = {t[0] for t in self.ALERT_TYPES}
    if self.alert_type and self.alert_type not in valid_types:
        errors['alert_type'] = f'Invalid alert_type "{self.alert_type}".'
    if self.is_resolved and not self.resolved_at:
        errors['resolved_at'] = (
            'resolved_at must be set when the alert is marked resolved.'
        )
    if self.resolved_at and self.created_at and self.resolved_at < self.created_at:
        errors['resolved_at'] = (
            'resolved_at cannot be before the alert was created.'
        )
    if not self.title or not self.title.strip():
        errors['title'] = 'Alert title cannot be empty.'
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# OfferCompletion
# ---------------------------------------------------------------------------
def _offer_completion_clean(self):
    errors = {}
    if self.reward_amount is not None and self.reward_amount < 0:
        errors['reward_amount'] = 'Reward amount cannot be negative.'
    if self.is_fraud and not self.fraud_reason:
        errors['fraud_reason'] = (
            'fraud_reason must be provided when is_fraud is True.'
        )
    if self.status == 'completed' and not self.completed_at:
        errors['completed_at'] = (
            'completed_at must be set when status is "completed".'
        )
    if self.completed_at and self.tracked_at and self.completed_at < self.tracked_at:
        errors['completed_at'] = (
            'completed_at cannot be before tracked_at.'
        )
    if self.reviewed_at and self.tracked_at and self.reviewed_at < self.tracked_at:
        errors['reviewed_at'] = (
            'reviewed_at cannot be before tracked_at.'
        )
    valid_statuses = {s[0] for s in self.STATUS_CHOICES}
    if self.status not in valid_statuses:
        errors['status'] = f'Invalid status "{self.status}".'
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# FraudCase
# ---------------------------------------------------------------------------
_VALID_CASE_STATUS_TRANSITIONS = {
    'open':        {'open', 'in_progress', 'escalated', 'closed', 'resolved'},
    'in_progress': {'in_progress', 'escalated', 'closed', 'resolved', 'open'},
    'escalated':   {'escalated', 'in_progress', 'closed', 'resolved'},
    'resolved':    {'resolved', 'closed'},
    'closed':      {'closed'},
}


def _fraud_case_clean(self):
    errors = {}
    if self.risk_score is not None and not (0 <= self.risk_score <= 100):
        errors['risk_score'] = 'Risk score must be between 0 and 100.'
    if self.is_resolved if hasattr(self, 'is_resolved') else False:
        pass
    if self.resolved_at and self.opened_at and self.resolved_at < self.opened_at:
        errors['resolved_at'] = (
            'resolved_at cannot be before opened_at.'
        )
    if self.pk:
        try:
            original = self.__class__.objects.get(pk=self.pk)
            allowed = _VALID_CASE_STATUS_TRANSITIONS.get(original.status, set())
            if self.status not in allowed:
                errors['status'] = (
                    f'Cannot transition case from "{original.status}" '
                    f'to "{self.status}".'
                )
        except self.__class__.DoesNotExist:
            pass
    if not self.title or not self.title.strip():
        errors['title'] = 'Case title cannot be empty.'
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# FraudCaseEvidence
# ---------------------------------------------------------------------------
def _fraud_case_evidence_clean(self):
    errors = {}
    valid_types = {
        'screenshot', 'log', 'transaction', 'device_data',
        'ip_data', 'user_report', 'system_flag', 'other',
    }
    if self.evidence_type and self.evidence_type not in valid_types:
        errors['evidence_type'] = (
            f'Invalid evidence_type "{self.evidence_type}". '
            f'Valid: {sorted(valid_types)}'
        )
    if not isinstance(self.data, dict):
        errors['data'] = 'Evidence data must be a JSON object (dict).'
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# FraudCaseAction
# ---------------------------------------------------------------------------
def _fraud_case_action_clean(self):
    errors = {}
    valid_types = {
        'note', 'status_change', 'assignment', 'evidence_added',
        'escalation', 'resolution', 'ban', 'restriction', 'other',
    }
    if self.action_type and self.action_type not in valid_types:
        errors['action_type'] = (
            f'Invalid action_type "{self.action_type}". '
            f'Valid: {sorted(valid_types)}'
        )
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# FraudWhitelist
# ---------------------------------------------------------------------------
def _fraud_whitelist_clean(self):
    errors = {}
    if self.expires_at and self.expires_at <= timezone.now():
        errors['expires_at'] = 'expires_at must be a future datetime.'
    if not self.reason or not self.reason.strip():
        errors['reason'] = 'Whitelist reason cannot be empty.'
    if not self.entity_value or not self.entity_value.strip():
        errors['entity_value'] = 'entity_value cannot be empty.'
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# FraudNotification
# ---------------------------------------------------------------------------
def _fraud_notification_clean(self):
    errors = {}
    if self.is_sent and not self.sent_at:
        errors['sent_at'] = (
            'sent_at must be set when is_sent is True.'
        )
    if self.sent_at and self.created_at and self.sent_at < self.created_at:
        errors['sent_at'] = 'sent_at cannot be before the notification was created.'
    if self.read_at and self.sent_at and self.read_at < self.sent_at:
        errors['read_at'] = 'read_at cannot be before sent_at.'
    if not self.message or not self.message.strip():
        errors['message'] = 'Notification message cannot be empty.'
    if errors:
        raise ValidationError(errors)


# ---------------------------------------------------------------------------
# Patch registry
# ---------------------------------------------------------------------------
_PATCHES = [
    ('FraudSettings',      _fraud_settings_clean),
    ('FraudRule',          _fraud_rule_clean),
    ('FraudAttempt',       _fraud_attempt_clean),
    ('FraudPattern',       _fraud_pattern_clean),
    ('UserRiskProfile',    _user_risk_profile_clean),
    ('DeviceFingerprint',  _device_fingerprint_clean),
    ('IPReputation',       _ip_reputation_clean),
    ('FraudAlert',         _fraud_alert_clean),
    ('OfferCompletion',    _offer_completion_clean),
    ('FraudCase',          _fraud_case_clean),
    ('FraudCaseEvidence',  _fraud_case_evidence_clean),
    ('FraudCaseAction',    _fraud_case_action_clean),
    ('FraudWhitelist',     _fraud_whitelist_clean),
    ('FraudNotification',  _fraud_notification_clean),
]


def patch_models():
    """
    Attach clean() to every fraud model.
    Call from AppConfig.ready() — models are loaded by then.
    """
    from django.apps import apps

    for model_name, clean_fn in _PATCHES:
        try:
            model = apps.get_model('fraud_detection', model_name)
            model.clean = clean_fn
        except LookupError:
            pass  # model not registered yet in test isolation
