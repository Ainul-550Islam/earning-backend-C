# SETTINGS_ADDITIONS.py
"""
Add these to your Django settings.py for the new components.
Copy-paste the relevant sections into your existing settings.py.
"""

# ════════════════════════════════════════════════════════════════
# 1. GAMIFICATION — Scratchcard & Spin Wheel
# ════════════════════════════════════════════════════════════════
SCRATCHCARD_COOLDOWN_HOURS = 24     # Hours between scratchcard claims
SPINWHEEL_COOLDOWN_HOURS   = 24     # Hours between spins
SCRATCHCARD_MAX_DAILY_BDT  = "50"   # Max BDT won per day via scratchcard
SPINWHEEL_MAX_DAILY_BDT    = "100"  # Max BDT won per day via spin wheel

# ════════════════════════════════════════════════════════════════
# 2. PUSH NOTIFICATIONS — FCM + APNs
# ════════════════════════════════════════════════════════════════

# Firebase (Android + Web push)
FIREBASE_CREDS_PATH = "/path/to/firebase-service-account.json"  # Set to None to disable

# Apple APNs (iOS)
APNS_KEY_PATH  = "/path/to/AuthKey_XXXXXXXXXX.p8"   # Set to None to disable
APNS_KEY_ID    = "XXXXXXXXXX"                        # 10-char key ID from Apple Developer
APNS_TEAM_ID   = "XXXXXXXXXX"                        # 10-char team ID
APNS_BUNDLE_ID = "com.yourapp.wallet"                # Your iOS app bundle ID

# ════════════════════════════════════════════════════════════════
# 3. REVENUE SHARING
# ════════════════════════════════════════════════════════════════
PLATFORM_REVENUE_SHARE_PCT = "0.30"   # Platform keeps 30% of advertiser payout
REFERRAL_L1_PCT            = "0.10"   # L1 referrer gets 10% of publisher net
REFERRAL_L2_PCT            = "0.05"   # L2 referrer gets 5%
REFERRAL_L3_PCT            = "0.02"   # L3 referrer gets 2%

# ════════════════════════════════════════════════════════════════
# 4. OFFERWALL PLATFORMS (already in new code, confirm these)
# ════════════════════════════════════════════════════════════════
OGADS_API_KEY          = ""
OGADS_POSTBACK_SECRET  = ""
OGADS_PUBLISHER_ID     = ""
OGADS_WALL_ID          = ""

ADGATE_API_KEY         = ""
ADGATE_SECRET_KEY      = ""
ADGATE_WALL_HASH       = ""

OFFERTORO_PUB_ID       = ""
OFFERTORO_APP_ID       = ""
OFFERTORO_SECRET_KEY   = ""
OFFERTORO_API_KEY      = ""

MONLIX_APP_ID          = ""
MONLIX_SECRET_KEY      = ""
MONLIX_API_KEY         = ""

# ════════════════════════════════════════════════════════════════
# 5. PAYMENT GATEWAYS
# ════════════════════════════════════════════════════════════════

# SSLCommerz
SSLCOMMERZ_BASE_URL    = "https://securepay.sslcommerz.com"  # sandbox: sandbox.sslcommerz.com
SSLCOMMERZ_STORE_ID    = ""
SSLCOMMERZ_STORE_PASSWD = ""

# Rocket MFS
ROCKET_BASE_URL        = "https://api.rocket.com.bd/v1"
ROCKET_API_KEY         = ""
ROCKET_API_SECRET      = ""

# Payoneer
PAYONEER_CLIENT_ID     = ""
PAYONEER_API_KEY       = ""
PAYONEER_PROGRAM_ID    = ""

# Wise
WISE_API_KEY           = ""
WISE_PROFILE_ID        = ""
WISE_SANDBOX           = True   # Set False in production

# ════════════════════════════════════════════════════════════════
# 6. INSTALLED_APPS — confirm wallet is registered
# ════════════════════════════════════════════════════════════════
# Ensure this is in INSTALLED_APPS:
# "api.wallet",

# ════════════════════════════════════════════════════════════════
# 7. CELERY BEAT — new tasks to add
# ════════════════════════════════════════════════════════════════
# In your CELERY_BEAT_SCHEDULE, add:
"""
"reset-daily-campaign-spend": {
    "task": "api.wallet.tasks.reset_daily_campaign_spend",
    "schedule": crontab(hour=0, minute=0),
},
"streak-reminder-push": {
    "task": "api.wallet.tasks.send_streak_reminders",
    "schedule": crontab(hour=18, minute=0),   # 6 PM daily
},
"""
