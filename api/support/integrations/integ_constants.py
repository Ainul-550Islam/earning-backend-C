# api/support/integrations/integ_constants.py  — WORLD #1
"""
Integration system-wide constants.
তোমার project-এর সব apps-এর সাথে support system-এর connection constants।
"""

# ── App Labels ────────────────────────────────────────
APP_WALLET         = 'wallet'
APP_NOTIFICATIONS  = 'notifications'
APP_POSTBACK       = 'postback'
APP_OFFERWALL      = 'offerwall'
APP_FRAUD          = 'fraud_detection'
APP_KYC            = 'kyc'
APP_PAYMENT        = 'payment_gateways'
APP_REFERRAL       = 'referral'
APP_USERS          = 'users'
APP_TENANTS        = 'tenants'
APP_ANALYTICS      = 'analytics'
APP_GAMIFICATION   = 'gamification'
APP_AUDIT          = 'audit_logs'

# ── Integration Event Types ───────────────────────────
# Ticket events
EVT_TICKET_CREATED       = 'support.ticket.created'
EVT_TICKET_REPLIED       = 'support.ticket.replied'
EVT_TICKET_RESOLVED      = 'support.ticket.resolved'
EVT_TICKET_CLOSED        = 'support.ticket.closed'
EVT_TICKET_ESCALATED     = 'support.ticket.escalated'
EVT_TICKET_RATED         = 'support.ticket.rated'
EVT_TICKET_SLA_BREACH    = 'support.ticket.sla_breach'
EVT_TICKET_SLA_WARNING   = 'support.ticket.sla_warning'

# Dispute events
EVT_OFFER_DISPUTE_CREATED   = 'support.dispute.offer.created'
EVT_OFFER_DISPUTE_APPROVED  = 'support.dispute.offer.approved'
EVT_OFFER_DISPUTE_REJECTED  = 'support.dispute.offer.rejected'
EVT_WITHDRAWAL_DISPUTE      = 'support.dispute.withdrawal.created'
EVT_KYC_APPEAL_CREATED      = 'support.dispute.kyc.created'

# Wallet events (incoming from wallet app)
EVT_WALLET_CREDITED         = 'wallet.credited'
EVT_WALLET_FROZEN           = 'wallet.frozen'
EVT_WALLET_WITHDRAWAL       = 'wallet.withdrawal.requested'

# Fraud events (incoming from fraud_detection app)
EVT_FRAUD_FLAG_USER         = 'fraud.user.flagged'
EVT_FRAUD_ALERT_HIGH        = 'fraud.alert.high'
EVT_FRAUD_ALERT_CRITICAL    = 'fraud.alert.critical'

# Offer events (incoming from offerwall)
EVT_OFFER_COMPLETED         = 'offerwall.offer.completed'
EVT_OFFER_REJECTED          = 'offerwall.offer.rejected'
EVT_POSTBACK_RECEIVED       = 'postback.received'

# KYC events
EVT_KYC_SUBMITTED           = 'kyc.submitted'
EVT_KYC_APPROVED            = 'kyc.approved'
EVT_KYC_REJECTED            = 'kyc.rejected'

# Chat events
EVT_CHAT_STARTED            = 'support.chat.started'
EVT_CHAT_ENDED              = 'support.chat.ended'
EVT_CHAT_AGENT_ASSIGNED     = 'support.chat.agent_assigned'

# ── Integration Actions ───────────────────────────────
# What support can DO to other apps
ACTION_CREDIT_WALLET        = 'credit_wallet'           # Credit coins to user
ACTION_FREEZE_WALLET        = 'freeze_wallet'           # Freeze during investigation
ACTION_UNFREEZE_WALLET      = 'unfreeze_wallet'         # Release after resolution
ACTION_SEND_NOTIFICATION    = 'send_notification'       # Via notifications app
ACTION_CHECK_FRAUD_SCORE    = 'check_fraud_score'       # Query fraud risk
ACTION_FLAG_USER            = 'flag_user'               # Flag suspicious user
ACTION_CHECK_POSTBACK       = 'check_postback'          # Verify offer completion
ACTION_CHECK_KYC_STATUS     = 'check_kyc_status'        # Verify user identity
ACTION_CHECK_OFFER_STATUS   = 'check_offer_status'      # Verify offer exists
ACTION_ADD_AUDIT_LOG        = 'add_audit_log'           # Log to audit system
ACTION_CHECK_REFERRAL       = 'check_referral'          # Verify referral chain

# ── Auto-Resolve Thresholds ───────────────────────────
AUTO_APPROVE_CONFIDENCE     = 0.85   # If verification confidence ≥ 85% → auto approve
FRAUD_RISK_HIGH_THRESHOLD   = 70     # Risk score ≥ 70 → high risk
FRAUD_RISK_CRITICAL         = 90     # Risk score ≥ 90 → auto-reject

# ── Dispute Limits ────────────────────────────────────
MAX_OFFER_DISPUTES_PER_WEEK    = 5   # Max offer disputes per user per week
MAX_WITHDRAWAL_DISPUTES_MONTH  = 3   # Max withdrawal disputes per month
MIN_DISPUTE_AMOUNT             = 10  # Minimum dispute amount (coins)

# ── Publisher Tiers (CPA) ─────────────────────────────
TIER_VIP      = 'vip'
TIER_GOLD     = 'gold'
TIER_SILVER   = 'silver'
TIER_STANDARD = 'standard'
TIER_NEW      = 'new'

# Tier → SLA first_response hours (faster for VIP)
TIER_SLA_HOURS = {
    TIER_VIP:      1,   # 1 hour
    TIER_GOLD:     2,   # 2 hours
    TIER_SILVER:   4,   # 4 hours
    TIER_STANDARD: 8,   # 8 hours
    TIER_NEW:      24,  # 24 hours
}

# ── Message Queue Config ──────────────────────────────
QUEUE_SUPPORT_EVENTS        = 'support_events'
QUEUE_DISPUTE_VERIFICATION  = 'dispute_verification'
QUEUE_NOTIFICATIONS         = 'support_notifications'
QUEUE_SLA_CHECKS            = 'sla_checks'

QUEUE_MAX_RETRIES           = 3
QUEUE_RETRY_DELAY_SECONDS   = 60   # 1 min between retries
QUEUE_HIGH_PRIORITY         = 10
QUEUE_NORMAL_PRIORITY       = 5
QUEUE_LOW_PRIORITY          = 1

# ── Cache Keys ────────────────────────────────────────
CACHE_PREFIX                = 'support_integ'
CACHE_TTL_USER_RISK         = 300    # 5 min — fraud score cache
CACHE_TTL_OFFER_STATUS      = 60     # 1 min — offer status cache
CACHE_TTL_KYC_STATUS        = 600    # 10 min — KYC status cache
CACHE_TTL_WALLET_BALANCE    = 30     # 30 sec — wallet balance
CACHE_TTL_HEALTH            = 120    # 2 min — health check results

# ── Performance Thresholds ────────────────────────────
PERF_RESPONSE_WARN_MS       = 500    # Warn if integration call > 500ms
PERF_RESPONSE_CRITICAL_MS   = 2000  # Critical if > 2s
PERF_SLOW_QUERY_WARN        = 100   # ms threshold for DB queries

# ── Health Check ──────────────────────────────────────
HEALTH_CHECK_TIMEOUT        = 5      # seconds
HEALTH_CHECK_INTERVAL       = 60     # seconds between checks

# ── Webhook ──────────────────────────────────────────
WEBHOOK_TIMEOUT_SECONDS     = 10
WEBHOOK_MAX_PAYLOAD_KB      = 256

# ── Audit ─────────────────────────────────────────────
AUDIT_RETENTION_DAYS        = 365    # Keep audit logs for 1 year
AUDIT_SENSITIVE_FIELDS      = ['amount', 'balance', 'fraud_score', 'status']

# ── Additional event constants (added for project_specific) ──
EVT_TICKET_REPLIED      = 'support.ticket.replied'
EVT_CHAT_STARTED        = 'support.chat.started'
EVT_CHAT_AGENT_ASSIGNED = 'support.chat.agent_assigned'

# ── Messaging integration ─────────────────────────────────────
MESSAGING_SYNC_ENABLED  = True   # sync tickets to messaging.SupportThread

# ── AI Engine ─────────────────────────────────────────────────
AI_ENGINE_ENABLED       = True   # use ai_engine for NLP
AI_SENTIMENT_ESCALATE   = -0.7   # escalate if sentiment score below this
AI_SPAM_CONFIDENCE      = 0.85   # mark spam if ai says >85% spam

# ── Auto Mod ──────────────────────────────────────────────────
AUTO_MOD_ENABLED        = True   # use auto_mod for dispute rules

# ── Security ──────────────────────────────────────────────────
VPN_CHECK_ENABLED       = True   # check VPN on dispute submissions
MAX_DISPUTES_PER_IP_24H = 10     # max disputes from same IP per 24h