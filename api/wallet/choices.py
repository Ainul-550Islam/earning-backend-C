# api/wallet/choices.py
from django.db import models

class TransactionType(models.TextChoices):
    EARNING        = "earning",        "Earning"
    REWARD         = "reward",         "Reward"
    REFERRAL       = "referral",       "Referral Commission"
    BONUS          = "bonus",          "Bonus"
    CASHBACK       = "cashback",       "Cashback"
    WITHDRAWAL     = "withdrawal",     "Withdrawal"
    WITHDRAWAL_FEE = "withdrawal_fee", "Withdrawal Fee"
    ADMIN_CREDIT   = "admin_credit",   "Admin Credit"
    ADMIN_DEBIT    = "admin_debit",    "Admin Debit"
    FREEZE         = "freeze",         "Freeze"
    UNFREEZE       = "unfreeze",       "Unfreeze"
    REVERSAL       = "reversal",       "Reversal"
    TRANSFER       = "transfer",       "Transfer"
    PENALTY        = "penalty",        "Penalty"
    REFUND         = "refund",         "Refund"
    CONTEST_PRIZE  = "contest_prize",  "Contest Prize"
    SURVEY         = "survey",         "Survey Reward"
    OFFER_WALL     = "offer_wall",     "Offer Wall"
    CPI            = "cpi",            "Cost Per Install"
    CPA            = "cpa",            "Cost Per Action"
    CPC            = "cpc",            "Cost Per Click"

class TransactionStatus(models.TextChoices):
    PENDING    = "pending",    "Pending"
    PROCESSING = "processing", "Processing"
    APPROVED   = "approved",   "Approved"
    COMPLETED  = "completed",  "Completed"
    REJECTED   = "rejected",   "Rejected"
    REVERSED   = "reversed",   "Reversed"
    FAILED     = "failed",     "Failed"
    CANCELLED  = "cancelled",  "Cancelled"
    ON_HOLD    = "on_hold",    "On Hold"

class WithdrawalStatus(models.TextChoices):
    PENDING    = "pending",    "Pending"
    APPROVED   = "approved",   "Approved"
    PROCESSING = "processing", "Processing"
    COMPLETED  = "completed",  "Completed"
    REJECTED   = "rejected",   "Rejected"
    FAILED     = "failed",     "Failed"
    CANCELLED  = "cancelled",  "Cancelled"
    BATCHED    = "batched",    "Batched"

class GatewayType(models.TextChoices):
    BKASH      = "bkash",      "bKash"
    NAGAD      = "nagad",      "Nagad"
    ROCKET     = "rocket",     "Rocket"
    UPAY       = "upay",       "Upay"
    BANK       = "bank",       "Bank Account"
    CARD       = "card",       "Debit/Credit Card"
    USDT_TRC20 = "usdt_trc20", "USDT TRC-20"
    USDT_ERC20 = "usdt_erc20", "USDT ERC-20"
    PAYPAL     = "paypal",     "PayPal"
    PAYONEER   = "payoneer",   "Payoneer"
    WISE       = "wise",       "Wise"

class UserTier(models.TextChoices):
    FREE     = "FREE",     "Free"
    BRONZE   = "BRONZE",   "Bronze"
    SILVER   = "SILVER",   "Silver"
    GOLD     = "GOLD",     "Gold"
    PLATINUM = "PLATINUM", "Platinum"
    DIAMOND  = "DIAMOND",  "Diamond"

class BalanceType(models.TextChoices):
    CURRENT  = "current",  "Current Balance"
    PENDING  = "pending",  "Pending Balance"
    FROZEN   = "frozen",   "Frozen Balance"
    BONUS    = "bonus",    "Bonus Balance"
    RESERVED = "reserved", "Reserved Balance"

class EarningSourceType(models.TextChoices):
    TASK         = "task",         "Task"
    OFFER        = "offer",        "Offer"
    CPA          = "cpa",          "CPA"
    CPI          = "cpi",          "CPI"
    CPC          = "cpc",          "CPC"
    REFERRAL     = "referral",     "Referral"
    BONUS        = "bonus",        "Bonus"
    SURVEY       = "survey",       "Survey"
    DAILY_REWARD = "daily_reward", "Daily Reward"
    STREAK       = "streak",       "Streak"
    CONTEST      = "contest",      "Contest"
    ADMIN        = "admin",        "Admin"
    CASHBACK     = "cashback",     "Cashback"
    OFFER_WALL   = "offer_wall",   "Offer Wall"
    CONTENT_LOCK = "content_lock", "Content Lock"

class WithdrawalBlockReason(models.TextChoices):
    FRAUD      = "fraud",      "Fraud Detected"
    KYC        = "kyc",        "KYC Not Verified"
    AML        = "aml",        "AML Compliance"
    VELOCITY   = "velocity",   "Velocity Limit"
    DISPUTE    = "dispute",    "Dispute"
    ADMIN      = "admin",      "Admin Hold"
    CHARGEBACK = "chargeback", "Chargeback"

class LedgerEntryType(models.TextChoices):
    DEBIT  = "debit",  "Debit"
    CREDIT = "credit", "Credit"

class FeeType(models.TextChoices):
    FLAT    = "flat",    "Flat Fee"
    PERCENT = "percent", "Percentage Fee"
    HYBRID  = "hybrid",  "Flat + Percentage"

class AlertType(models.TextChoices):
    LOW_BALANCE   = "low_balance",   "Low Balance"
    HIGH_BALANCE  = "high_balance",  "High Balance"
    LARGE_CREDIT  = "large_credit",  "Large Credit"
    LARGE_DEBIT   = "large_debit",   "Large Debit"
    WITHDRAWAL    = "withdrawal",    "Withdrawal Alert"
    BONUS_EXPIRY  = "bonus_expiry",  "Bonus Expiring"
    FRAUD_SUSPECT = "fraud_suspect", "Fraud Suspected"

class PayoutFrequency(models.TextChoices):
    DAILY      = "daily",      "Daily (next day)"
    WEEKLY     = "weekly",     "Weekly"
    NET15      = "net15",      "Net-15"
    NET30      = "net30",      "Net-30 (default)"
    INSTANT    = "instant",    "Instant / Fast Pay"
    ON_REQUEST = "on_request", "On Request"

class FraudRiskLevel(models.TextChoices):
    LOW     = "low",     "Low Risk (0-30)"
    MEDIUM  = "medium",  "Medium Risk (31-70)"
    HIGH    = "high",    "High Risk (71-84)"
    BLOCKED = "blocked", "Blocked (85+)"

class AMLFlagType(models.TextChoices):
    STRUCTURING         = "structuring",         "Structuring (Smurfing)"
    RAPID_MOVEMENT      = "rapid_movement",      "Rapid Fund Movement"
    UNUSUAL_PATTERN     = "unusual_pattern",     "Unusual Pattern"
    HIGH_RISK_COUNTRY   = "high_risk_country",   "High Risk Country"
    POLITICALLY_EXPOSED = "politically_exposed", "Politically Exposed Person"
    SANCTION_MATCH      = "sanction_match",      "Sanctions List Match"
    ROUND_NUMBERS       = "round_numbers",       "Suspicious Round Numbers"

class KYCStatus(models.TextChoices):
    PENDING  = "pending",  "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    EXPIRED  = "expired",  "Expired"

class DisputeStatus(models.TextChoices):
    OPEN              = "open",              "Open"
    UNDER_REVIEW      = "under_review",      "Under Review"
    RESOLVED_USER     = "resolved_user",     "Resolved — User Favor"
    RESOLVED_PLATFORM = "resolved_platform", "Resolved — Platform Favor"
    CANCELLED         = "cancelled",         "Cancelled"
