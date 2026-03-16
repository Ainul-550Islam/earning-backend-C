from decimal import Decimal


# ─── Trial Settings ────────────────────────────────────────────────────────────
DEFAULT_TRIAL_DAYS = 14
MAX_TRIAL_DAYS = 90

# ─── Grace Period ──────────────────────────────────────────────────────────────
PAYMENT_GRACE_PERIOD_DAYS = 3
PAST_DUE_GRACE_PERIOD_DAYS = 7

# ─── Retry Settings ────────────────────────────────────────────────────────────
MAX_PAYMENT_RETRY_ATTEMPTS = 3
PAYMENT_RETRY_INTERVALS_DAYS = [1, 3, 7]  # Days between retries

# ─── Pricing ───────────────────────────────────────────────────────────────────
MIN_PLAN_PRICE = Decimal("0.00")
MAX_PLAN_PRICE = Decimal("99999.99")
MIN_DISCOUNT_PERCENT = Decimal("0.00")
MAX_DISCOUNT_PERCENT = Decimal("100.00")

# ─── Pagination ────────────────────────────────────────────────────────────────
SUBSCRIPTION_PAGE_SIZE = 20
PLAN_PAGE_SIZE = 10
PAYMENT_PAGE_SIZE = 25

# ─── Cache Keys ────────────────────────────────────────────────────────────────
CACHE_KEY_ACTIVE_PLANS = "subscription:active_plans"
CACHE_KEY_USER_SUBSCRIPTION = "subscription:user:{user_id}:active"
CACHE_KEY_PLAN_BENEFITS = "subscription:plan:{plan_id}:benefits"
CACHE_TIMEOUT_PLANS = 60 * 60  # 1 hour
CACHE_TIMEOUT_USER_SUB = 60 * 5  # 5 minutes

# ─── Rate Limiting ─────────────────────────────────────────────────────────────
SUBSCRIPTION_THROTTLE_RATE = "10/minute"
PAYMENT_THROTTLE_RATE = "5/minute"
WEBHOOK_THROTTLE_RATE = "100/minute"

# ─── Webhook ───────────────────────────────────────────────────────────────────
WEBHOOK_SIGNATURE_HEADER = "X-Subscription-Signature"
WEBHOOK_TOLERANCE_SECONDS = 300  # 5 minutes

# ─── Email Templates ───────────────────────────────────────────────────────────
EMAIL_SUBSCRIPTION_CREATED = "subscription/emails/created.html"
EMAIL_SUBSCRIPTION_RENEWED = "subscription/emails/renewed.html"
EMAIL_SUBSCRIPTION_CANCELLED = "subscription/emails/cancelled.html"
EMAIL_SUBSCRIPTION_EXPIRED = "subscription/emails/expired.html"
EMAIL_PAYMENT_SUCCEEDED = "subscription/emails/payment_success.html"
EMAIL_PAYMENT_FAILED = "subscription/emails/payment_failed.html"
EMAIL_TRIAL_ENDING = "subscription/emails/trial_ending.html"
EMAIL_TRIAL_ENDED = "subscription/emails/trial_ended.html"

# ─── Task Names ────────────────────────────────────────────────────────────────
TASK_EXPIRE_SUBSCRIPTIONS = "subscription.tasks.expire_subscriptions"
TASK_SEND_RENEWAL_REMINDERS = "subscription.tasks.send_renewal_reminders"
TASK_RETRY_FAILED_PAYMENTS = "subscription.tasks.retry_failed_payments"
TASK_SEND_TRIAL_ENDING_NOTICE = "subscription.tasks.send_trial_ending_notice"

# ─── Notification Days Before Expiry ──────────────────────────────────────────
RENEWAL_REMINDER_DAYS = [7, 3, 1]
TRIAL_ENDING_REMINDER_DAYS = [3, 1]

# ─── Subscription Limits ──────────────────────────────────────────────────────
MAX_ACTIVE_SUBSCRIPTIONS_PER_USER = 1  # One active subscription at a time
MAX_SUBSCRIPTION_PAUSE_DAYS = 90

# ─── Plan Feature Flags ────────────────────────────────────────────────────────
FEATURE_UNLIMITED = -1  # Sentinel value meaning "unlimited"

# ─── Currency ─────────────────────────────────────────────────────────────────
DEFAULT_CURRENCY = "USD"

# ─── Coupon / Promo ───────────────────────────────────────────────────────────
MAX_COUPON_USES = 10000
COUPON_CODE_LENGTH = 8