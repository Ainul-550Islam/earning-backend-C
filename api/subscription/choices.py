from django.db import models


class PlanInterval(models.TextChoices):
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"
    YEARLY = "yearly", "Yearly"
    LIFETIME = "lifetime", "Lifetime"


class PlanStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    ARCHIVED = "archived", "Archived"


class SubscriptionStatus(models.TextChoices):
    TRIALING = "trialing", "Trialing"
    ACTIVE = "active", "Active"
    PAST_DUE = "past_due", "Past Due"
    CANCELLED = "cancelled", "Cancelled"
    EXPIRED = "expired", "Expired"
    PAUSED = "paused", "Paused"
    PENDING = "pending", "Pending"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"
    PARTIALLY_REFUNDED = "partially_refunded", "Partially Refunded"
    DISPUTED = "disputed", "Disputed"
    CANCELLED = "cancelled", "Cancelled"


class PaymentMethod(models.TextChoices):
    CREDIT_CARD = "credit_card", "Credit Card"
    DEBIT_CARD = "debit_card", "Debit Card"
    PAYPAL = "paypal", "PayPal"
    STRIPE = "stripe", "Stripe"
    BANK_TRANSFER = "bank_transfer", "Bank Transfer"
    CRYPTO = "crypto", "Cryptocurrency"
    BKASH = "bkash", "bKash"
    NAGAD = "nagad", "Nagad"
    ROCKET = "rocket", "Rocket"
    OTHER = "other", "Other"


class BenefitType(models.TextChoices):
    FEATURE = "feature", "Feature Access"
    LIMIT = "limit", "Usage Limit"
    DISCOUNT = "discount", "Discount"
    PRIORITY = "priority", "Priority Access"
    STORAGE = "storage", "Storage"
    API_CALLS = "api_calls", "API Calls"
    SUPPORT = "support", "Support Level"
    CUSTOM = "custom", "Custom"


class CancellationReason(models.TextChoices):
    TOO_EXPENSIVE = "too_expensive", "Too Expensive"
    NOT_USING = "not_using", "Not Using Enough"
    MISSING_FEATURES = "missing_features", "Missing Features"
    FOUND_ALTERNATIVE = "found_alternative", "Found Alternative"
    TECHNICAL_ISSUES = "technical_issues", "Technical Issues"
    CUSTOMER_SERVICE = "customer_service", "Poor Customer Service"
    OTHER = "other", "Other"


class Currency(models.TextChoices):
    USD = "USD", "US Dollar"
    EUR = "EUR", "Euro"
    GBP = "GBP", "British Pound"
    BDT = "BDT", "Bangladeshi Taka"
    INR = "INR", "Indian Rupee"
    AUD = "AUD", "Australian Dollar"
    CAD = "CAD", "Canadian Dollar"