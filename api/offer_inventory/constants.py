# api/offer_inventory/constants.py

# ── Payout & Finance ────────────────────────────────────────────
MIN_WITHDRAWAL_BDT      = 50          # সর্বনিম্ন উইথড্রয়াল (BDT)
MAX_WITHDRAWAL_BDT      = 50_000      # সর্বোচ্চ উইথড্রয়াল (BDT)
DEFAULT_PLATFORM_FEE_PCT= 2.5         # Platform charge %
DEFAULT_REVENUE_SHARE   = 70.0        # User-এর ভাগ %
MAX_DAILY_OFFERS        = 30          # প্রতিদিন সর্বোচ্চ অফার
BONUS_EXPIRY_DAYS       = 30          # Bonus balance expire দিন

# ── Click & Conversion ──────────────────────────────────────────
CLICK_TOKEN_TTL_SECONDS = 86_400      # Click token valid 24h
MAX_CLICKS_PER_HOUR     = 60          # Rate limit per user
MIN_CLICK_INTERVAL_SEC  = 3           # Duplicate click window
POSTBACK_RETRY_LIMIT    = 5           # Max postback retry
POSTBACK_RETRY_DELAY    = 300         # Retry after 5 min (sec)

# ── Fraud Detection ─────────────────────────────────────────────
FRAUD_SCORE_THRESHOLD   = 75.0        # এর উপরে = high risk
AUTO_BLOCK_SCORE        = 90.0        # Auto block threshold
MAX_ACCOUNTS_PER_IP     = 3           # Same IP থেকে max account
HONEYPOT_BLOCK_HOURS    = 72          # Honeypot block duration
VPN_RISK_SCORE_ADD      = 30          # VPN detection score add

# ── Cache TTL (seconds) ─────────────────────────────────────────
CACHE_TTL_OFFER_LIST    = 300         # 5 min
CACHE_TTL_OFFER_DETAIL  = 600         # 10 min
CACHE_TTL_USER_PROFILE  = 900         # 15 min
CACHE_TTL_DAILY_STATS   = 3_600       # 1 hour
CACHE_TTL_NETWORK_PING  = 60          # 1 min

# ── Pagination ──────────────────────────────────────────────────
PAGE_SIZE_DEFAULT       = 20
PAGE_SIZE_MAX           = 100
PAGE_SIZE_ADMIN         = 50

# ── OTP & Auth ──────────────────────────────────────────────────
OTP_EXPIRY_MINUTES      = 10
MAX_OTP_ATTEMPTS        = 5
SESSION_TIMEOUT_MINUTES = 60

# ── File Upload ─────────────────────────────────────────────────
MAX_UPLOAD_SIZE_MB      = 10
ALLOWED_IMAGE_TYPES     = ['image/jpeg', 'image/png', 'image/webp']
ALLOWED_DOC_TYPES       = ['application/pdf']

# ── Geo & Targeting ─────────────────────────────────────────────
DEFAULT_COUNTRY         = 'BD'
SUPPORTED_CURRENCIES    = ['BDT', 'USD', 'EUR', 'GBP', 'INR']
DEFAULT_CURRENCY        = 'BDT'

# ── SmartLink ───────────────────────────────────────────────────
SMARTLINK_ALGORITHMS    = ['highest_payout', 'best_cvr', 'random', 'round_robin']

# ── Celery Queue Names ──────────────────────────────────────────
QUEUE_POSTBACK          = 'postback'
QUEUE_FRAUD             = 'fraud'
QUEUE_NOTIFICATION      = 'notification'
QUEUE_PAYOUT            = 'payout'
QUEUE_ANALYTICS         = 'analytics'
QUEUE_DEFAULT           = 'default'

# ── Referral ────────────────────────────────────────────────────
DEFAULT_REFERRAL_PCT    = 5.0         # Default referral commission %
MAX_REFERRAL_DEPTH      = 2           # Multi-level referral depth

# ── A/B Testing ─────────────────────────────────────────────────
AB_DEFAULT_SPLIT        = 0.5         # 50/50 split
AB_MIN_SAMPLE_SIZE      = 100         # Minimum conversions before result

# ── Webhook ─────────────────────────────────────────────────────
WEBHOOK_TIMEOUT_SEC     = 10
WEBHOOK_MAX_RETRIES     = 3
WEBHOOK_EVENTS = [
    'conversion.approved',
    'conversion.rejected',
    'conversion.reversed',
    'withdrawal.completed',
    'withdrawal.rejected',
    'fraud.detected',
    'offer.expired',
    'user.suspended',
]

# ── Error Messages (Bangla) ─────────────────────────────────────
ERR_OFFER_NOT_FOUND       = 'অফারটি পাওয়া যায়নি।'
ERR_OFFER_EXPIRED         = 'অফারটির মেয়াদ শেষ হয়ে গেছে।'
ERR_OFFER_CAP_REACHED     = 'এই অফারটির সীমা পূরণ হয়ে গেছে।'
ERR_ALREADY_COMPLETED     = 'আপনি ইতিমধ্যে এই অফারটি সম্পন্ন করেছেন।'
ERR_INSUFFICIENT_BALANCE  = 'পর্যাপ্ত ব্যালেন্স নেই।'
ERR_MIN_WITHDRAWAL        = f'সর্বনিম্ন উইথড্রয়াল {MIN_WITHDRAWAL_BDT} টাকা।'
ERR_MAX_WITHDRAWAL        = f'সর্বোচ্চ উইথড্রয়াল {MAX_WITHDRAWAL_BDT} টাকা।'
ERR_WALLET_LOCKED         = 'আপনার ওয়ালেট লক করা আছে।'
ERR_USER_SUSPENDED        = 'আপনার অ্যাকাউন্ট সাসপেন্ড করা হয়েছে।'
ERR_FRAUD_DETECTED        = 'সন্দেহজনক কার্যকলাপ সনাক্ত হয়েছে।'
ERR_RATE_LIMIT            = 'অনুরোধ সীমা অতিক্রম করেছেন। কিছুক্ষণ পরে চেষ্টা করুন।'
ERR_VPN_DETECTED          = 'VPN/Proxy ব্যবহার করা যাবে না।'
ERR_DUPLICATE_CLICK       = 'Duplicate click detected।'
ERR_INVALID_POSTBACK      = 'Invalid postback signature।'
ERR_KYC_REQUIRED          = 'উইথড্রয়ালের আগে KYC যাচাই করুন।'
