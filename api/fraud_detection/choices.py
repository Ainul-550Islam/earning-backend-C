# =============================================================================
# fraud_detection/choices.py
#
# All TextChoices / IntegerChoices enums used across models, serializers,
# views, and admin. Single source of truth — import from here everywhere.
# =============================================================================
from __future__ import annotations

from django.db import models


# ---------------------------------------------------------------------------
# FraudRule
# ---------------------------------------------------------------------------

class RuleType(models.TextChoices):
    VELOCITY         = 'velocity',         'Velocity Check'
    PATTERN          = 'pattern',          'Pattern Match'
    ML_MODEL         = 'ml_model',         'ML Model'
    BEHAVIORAL       = 'behavioral',       'Behavioral Analysis'
    GEOGRAPHIC       = 'geographic',       'Geographic Check'
    DEVICE           = 'device',           'Device Fingerprint'
    NETWORK          = 'network',          'Network Analysis'
    CUSTOM           = 'custom',           'Custom Rule'


class SeverityLevel(models.TextChoices):
    LOW      = 'low',      'Low'
    MEDIUM   = 'medium',   'Medium'
    HIGH     = 'high',     'High'
    CRITICAL = 'critical', 'Critical'


class ActionOnTrigger(models.TextChoices):
    FLAG    = 'flag',    'Flag for Review'
    BLOCK   = 'block',   'Block Action'
    BAN     = 'ban',     'Ban User'
    ALERT   = 'alert',   'Send Alert'
    LOG     = 'log',     'Log Only'


class RunFrequency(models.TextChoices):
    REAL_TIME = 'real_time', 'Real-Time'
    HOURLY    = 'hourly',    'Hourly'
    DAILY     = 'daily',     'Daily'
    WEEKLY    = 'weekly',    'Weekly'


# ---------------------------------------------------------------------------
# FraudAttempt
# ---------------------------------------------------------------------------

class AttemptType(models.TextChoices):
    ACCOUNT_TAKEOVER    = 'account_takeover',    'Account Takeover'
    PAYMENT_FRAUD       = 'payment_fraud',        'Payment Fraud'
    IDENTITY_THEFT      = 'identity_theft',       'Identity Theft'
    BONUS_ABUSE         = 'bonus_abuse',           'Bonus Abuse'
    CLICK_FRAUD         = 'click_fraud',           'Click Fraud'
    REFERRAL_FRAUD      = 'referral_fraud',        'Referral Fraud'
    MULTI_ACCOUNT       = 'multi_account',         'Multiple Accounts'
    CHARGEBACK_FRAUD    = 'chargeback_fraud',      'Chargeback Fraud'
    PROMO_ABUSE         = 'promo_abuse',           'Promo Abuse'
    DEVICE_FRAUD        = 'device_fraud',          'Device Fraud'
    OTHER               = 'other',                 'Other'


class AttemptStatus(models.TextChoices):
    PENDING     = 'pending',     'Pending Review'
    CONFIRMED   = 'confirmed',   'Confirmed Fraud'
    DISMISSED   = 'dismissed',   'Dismissed'
    INVESTIGATING = 'investigating', 'Under Investigation'
    RESOLVED    = 'resolved',    'Resolved'


class DetectedBy(models.TextChoices):
    ML_MODEL  = 'ml_model',  'ML Model'
    RULE      = 'rule',      'Rule Engine'
    MANUAL    = 'manual',    'Manual Review'
    SYSTEM    = 'system',    'System Auto-Detect'


# ---------------------------------------------------------------------------
# FraudPattern
# ---------------------------------------------------------------------------

class PatternType(models.TextChoices):
    VELOCITY   = 'velocity',   'Velocity Pattern'
    BEHAVIORAL = 'behavioral', 'Behavioral Pattern'
    NETWORK    = 'network',    'Network Pattern'
    DEVICE     = 'device',     'Device Pattern'
    GEOGRAPHIC = 'geographic', 'Geographic Pattern'
    TEMPORAL   = 'temporal',   'Temporal Pattern'
    CUSTOM     = 'custom',     'Custom Pattern'


# ---------------------------------------------------------------------------
# UserRiskProfile
# ---------------------------------------------------------------------------

class MonitoringLevel(models.TextChoices):
    NORMAL    = 'normal',    'Normal'
    ELEVATED  = 'elevated',  'Elevated'
    HIGH      = 'high',      'High'
    CRITICAL  = 'critical',  'Critical'


# ---------------------------------------------------------------------------
# FraudAlert  (exported as FraudAlertType & AlertPriority for serializers)
# ---------------------------------------------------------------------------

class FraudAlertType(models.TextChoices):
    FRAUD_DETECTED        = 'fraud_detected',        'Fraud Detected'
    HIGH_RISK_ACTIVITY    = 'high_risk_activity',     'High-Risk Activity'
    SUSPICIOUS_LOGIN      = 'suspicious_login',       'Suspicious Login'
    MULTIPLE_ACCOUNTS     = 'multiple_accounts',      'Multiple Accounts'
    UNUSUAL_TRANSACTION   = 'unusual_transaction',    'Unusual Transaction'
    DEVICE_ANOMALY        = 'device_anomaly',         'Device Anomaly'
    LOCATION_ANOMALY      = 'location_anomaly',       'Location Anomaly'
    VELOCITY_BREACH       = 'velocity_breach',        'Velocity Limit Breach'
    PATTERN_MATCH         = 'pattern_match',          'Pattern Match'
    MANUAL_FLAG           = 'manual_flag',            'Manually Flagged'


class AlertPriority(models.TextChoices):
    LOW      = 'low',      'Low'
    MEDIUM   = 'medium',   'Medium'
    HIGH     = 'high',     'High'
    CRITICAL = 'critical', 'Critical'


# ---------------------------------------------------------------------------
# FraudCase
# ---------------------------------------------------------------------------

class CaseStatus(models.TextChoices):
    OPEN          = 'open',          'Open'
    INVESTIGATING = 'investigating', 'Under Investigation'
    PENDING       = 'pending',       'Pending Decision'
    RESOLVED      = 'resolved',      'Resolved'
    CLOSED        = 'closed',        'Closed'
    DISMISSED     = 'dismissed',     'Dismissed'
    ESCALATED     = 'escalated',     'Escalated'


class CasePriority(models.TextChoices):
    LOW      = 'low',      'Low'
    MEDIUM   = 'medium',   'Medium'
    HIGH     = 'high',     'High'
    CRITICAL = 'critical', 'Critical'


# ---------------------------------------------------------------------------
# FraudCaseEvidence
# ---------------------------------------------------------------------------

class EvidenceType(models.TextChoices):
    SCREENSHOT       = 'screenshot',       'Screenshot'
    LOG              = 'log',              'Log Entry'
    TRANSACTION      = 'transaction',      'Transaction Record'
    DEVICE_DATA      = 'device_data',      'Device Data'
    IP_DATA          = 'ip_data',          'IP Data'
    USER_ACTIVITY    = 'user_activity',    'User Activity'
    COMMUNICATION    = 'communication',    'Communication'
    THIRD_PARTY      = 'third_party',      'Third-Party Data'
    OTHER            = 'other',            'Other'


# ---------------------------------------------------------------------------
# FraudCaseAction
# ---------------------------------------------------------------------------

class ActionType(models.TextChoices):
    FLAGGED         = 'flagged',          'Flagged'
    INVESTIGATED    = 'investigated',     'Investigated'
    ESCALATED       = 'escalated',        'Escalated'
    RESOLVED        = 'resolved',         'Resolved'
    BANNED          = 'banned',           'User Banned'
    SUSPENDED       = 'suspended',        'User Suspended'
    RESTRICTED      = 'restricted',       'User Restricted'
    CLEARED         = 'cleared',          'Cleared / Dismissed'
    NOTE_ADDED      = 'note_added',       'Note Added'
    EVIDENCE_ADDED  = 'evidence_added',   'Evidence Added'
    ASSIGNED        = 'assigned',         'Assigned to Reviewer'
    REOPENED        = 'reopened',         'Reopened'


# ---------------------------------------------------------------------------
# FraudWhitelist
# ---------------------------------------------------------------------------

class EntityType(models.TextChoices):
    USER       = 'user',       'User'
    IP_ADDRESS = 'ip_address', 'IP Address'
    DEVICE     = 'device',     'Device'
    EMAIL      = 'email',      'Email'
    DOMAIN     = 'domain',     'Domain'
    PHONE      = 'phone',      'Phone Number'


# ---------------------------------------------------------------------------
# FraudNotification  (exported as NotificationType)
# ---------------------------------------------------------------------------

class NotificationType(models.TextChoices):
    FRAUD_DETECTED    = 'fraud_detected',    'Fraud Detected'
    ACCOUNT_SUSPENDED = 'account_suspended', 'Account Suspended'
    REVIEW_REQUIRED   = 'review_required',   'Review Required'
    RISK_UPDATE       = 'risk_update',       'Risk Score Updated'
    CASE_UPDATE       = 'case_update',       'Case Status Updated'
    ALERT             = 'alert',             'General Alert'
    SYSTEM            = 'system',            'System Notification'


class NotificationChannel(models.TextChoices):
    EMAIL     = 'email',     'Email'
    SMS       = 'sms',       'SMS'
    PUSH      = 'push',      'Push Notification'
    WEBSOCKET = 'websocket', 'WebSocket'
    IN_APP    = 'in_app',    'In-App'


# ---------------------------------------------------------------------------
# OfferCompletion
# ---------------------------------------------------------------------------

class CompletionStatus(models.TextChoices):
    PENDING   = 'pending',   'Pending Verification'
    APPROVED  = 'approved',  'Approved'
    REJECTED  = 'rejected',  'Rejected'
    FRAUD     = 'fraud',     'Marked as Fraud'
    PAID      = 'paid',      'Reward Paid'
    REVERSED  = 'reversed',  'Reversed'


FraudAttemptType = AttemptType
FraudAttemptStatus = AttemptStatus
WhitelistType = EntityType
