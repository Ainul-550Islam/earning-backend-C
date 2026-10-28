"""
api/support/constants_extended.py
FIXED — Extended constants for World #1 upgrade.
Merge into existing constants.py
"""
from django.db import models


class TicketPriority:
    """Priority constants with SLA hours"""
    URGENT = 'urgent'
    HIGH   = 'high'
    MEDIUM = 'medium'
    LOW    = 'low'

    CHOICES = [
        (URGENT, '🚨 Urgent'),
        (HIGH,   '⚠️ High'),
        (MEDIUM, '📢 Medium'),
        (LOW,    'ℹ️ Low'),
    ]

    # SLA hours per priority (resolution target)
    SLA_HOURS = {
        URGENT: 4,
        HIGH:   24,
        MEDIUM: 48,
        LOW:    72,
    }

    # First response hours per priority
    FIRST_RESPONSE_HOURS = {
        URGENT: 1,
        HIGH:   4,
        MEDIUM: 8,
        LOW:    24,
    }


class TicketStatus:
    OPEN         = 'open'
    IN_PROGRESS  = 'in_progress'
    WAITING_USER = 'waiting_user'
    RESOLVED     = 'resolved'
    CLOSED       = 'closed'
    SPAM         = 'spam'

    CHOICES = [
        (OPEN,         '🟡 Open'),
        (IN_PROGRESS,  '🔵 In Progress'),
        (WAITING_USER, '🟠 Waiting for User'),
        (RESOLVED,     '✅ Resolved'),
        (CLOSED,       '⛔ Closed'),
        (SPAM,         '🚫 Spam'),
    ]

    ACTIVE = [OPEN, IN_PROGRESS, WAITING_USER]
    CLOSED_STATUSES = [RESOLVED, CLOSED]


class TicketCategory:
    PAYMENT    = 'payment'
    WITHDRAWAL = 'withdrawal'
    COINS      = 'coins'
    ACCOUNT    = 'account'
    FRAUD      = 'fraud'
    KYC        = 'kyc'
    TECHNICAL  = 'technical'
    REFERRAL   = 'referral'
    OFFER      = 'offer'
    OTHER      = 'other'

    CHOICES = [
        (PAYMENT,    '💰 Payment'),
        (WITHDRAWAL, '💸 Withdrawal'),
        (COINS,      '🪙 Coins'),
        (ACCOUNT,    '👤 Account'),
        (FRAUD,      '🔒 Fraud'),
        (KYC,        '📋 KYC'),
        (TECHNICAL,  '🔧 Technical'),
        (REFERRAL,   '🤝 Referral'),
        (OFFER,      '📢 Offer'),
        (OTHER,      '❓ Other'),
    ]

    # Default priority per category
    DEFAULT_PRIORITY = {
        PAYMENT:    TicketPriority.HIGH,
        WITHDRAWAL: TicketPriority.HIGH,
        FRAUD:      TicketPriority.URGENT,
        KYC:        TicketPriority.MEDIUM,
        COINS:      TicketPriority.MEDIUM,
        ACCOUNT:    TicketPriority.MEDIUM,
        TECHNICAL:  TicketPriority.MEDIUM,
        REFERRAL:   TicketPriority.LOW,
        OFFER:      TicketPriority.LOW,
        OTHER:      TicketPriority.LOW,
    }


# For backward compatibility with choices.py
CATEGORY_PRIORITY_MAP = TicketCategory.DEFAULT_PRIORITY


class NotificationChannel:
    EMAIL    = 'email'
    SMS      = 'sms'
    PUSH     = 'push'
    TELEGRAM = 'telegram'
    WHATSAPP = 'whatsapp'
    SLACK    = 'slack'

    CHOICES = [
        (EMAIL,    'Email'),
        (SMS,      'SMS'),
        (PUSH,     'Push Notification'),
        (TELEGRAM, 'Telegram'),
        (WHATSAPP, 'WhatsApp'),
        (SLACK,    'Slack'),
    ]


class SLAHealth:
    OK       = 'ok'
    WARNING  = 'warning'
    CRITICAL = 'critical'
    BREACHED = 'breached'

    COLORS = {
        OK:       '#16a34a',
        WARNING:  '#ca8a04',
        CRITICAL: '#ea580c',
        BREACHED: '#dc2626',
    }