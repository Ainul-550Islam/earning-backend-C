# Djoyalty — World-Class Django Loyalty System

## Overview

Djoyalty is a **production-ready, API-first loyalty system** for Django applications.  
Inspired by Open Loyalty, Voucherify, Smile.io, Starbucks Rewards, and Subway MVP.

---

## 🚀 Quick Setup

### 1. Install & Configure

```python
# settings.py
INSTALLED_APPS = [
    ...
    'djoyalty',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_PAGINATION_CLASS': 'djoyalty.pagination.DjoyaltyPagePagination',
    'PAGE_SIZE': 20,
}

DJOYALTY = {
    'DEFAULT_EARN_RATE': 1,
    'DEFAULT_POINT_VALUE': 0.01,
    'DEFAULT_EXPIRY_DAYS': 365,
    'CURRENCY': 'BDT',
    'CASHOUT_ENABLED': True,
    'SPIN_WHEEL_ENABLED': True,
    'QR_EARN_ENABLED': True,
}
```

### 2. URLs

```python
# urls.py
urlpatterns = [
    path('api/loyalty/', include('djoyalty.urls')),
]
```

### 3. Migrate & Seed

```bash
python manage.py migrate
python manage.py seed_tiers
python manage.py seed_earn_rules
python manage.py seed_badges
```

---

## 🏗️ System Architecture

```
djoyalty/
├── models/          # 70+ models across 9 files
│   ├── core.py          Customer, Txn, Event, Tenant
│   ├── points.py         LoyaltyPoints, Ledger, Expiry, Transfer...
│   ├── tiers.py          LoyaltyTier, UserTier, TierBenefit...
│   ├── earn_rules.py     EarnRule, EarnTransaction, BonusEvent...
│   ├── redemption.py     RedemptionRequest, Voucher, GiftCard...
│   ├── engagement.py     DailyStreak, Badge, Challenge, Milestone...
│   ├── campaigns.py      LoyaltyCampaign, PartnerMerchant...
│   ├── advanced.py       Fraud, Insights, Subscription, Coalition...
│   ├── gamification.py   SpinWheel, ScratchCard, Lottery, Quiz...  ← World-class
│   ├── cashout.py        CashoutRequest, BankAccount, MobileWallet... ← World-class
│   └── social.py         SocialShare, QRCode, Segments, Reviews...  ← World-class
├── services/        # 30+ service classes
├── viewsets/        # 25+ API endpoints
├── serializers/     # 22 serializers
├── tasks/           # 14 Celery tasks
├── signals/         # 7 signal handlers
├── webhooks/        # Outbound webhook system
├── admin/           # Full Django admin
└── management/      # 10 management commands
```

---

## 📋 Core Features

| Feature | Status | World Equivalent |
|---|---|---|
| Points Earn/Burn | ✅ | Starbucks Stars |
| Tier System (5 tiers) | ✅ | Subway MVP, Delta SkyMiles |
| Vouchers & Gift Cards | ✅ | Voucherify |
| P2P Points Transfer | ✅ | Airline miles transfer |
| Daily Streaks | ✅ | Fitbit Rewards |
| Badges & Achievements | ✅ | Xbox Rewards Hub |
| Challenges | ✅ | Fitbit challenges |
| Milestones | ✅ | Capital One milestones |
| Campaigns (multiplier/bonus) | ✅ | Open Loyalty campaigns |
| Coalition (partner earn) | ✅ | Multi-merchant loyalty |
| Referral System | ✅ | Smile.io referrals |
| **Spin Wheel** | ✅ | Voucherify gamification |
| **Scratch Cards** | ✅ | WooCommerce gamification |
| **Lottery/Raffle** | ✅ | Airline miles lottery |
| **Quiz Rewards** | ✅ | Engagement mechanic |
| **Leaderboard Seasons** | ✅ | Xbox, Fitbit seasons |
| **Bank Cashout** | ✅ | Capital One rewards |
| **bKash/Nagad Cashout** | ✅ | BD mobile wallets |
| **Social Share Rewards** | ✅ | Smile.io social |
| **Review Rewards** | ✅ | Smile.io reviews |
| **QR Code Earn** | ✅ | Subway in-store scan |
| **Customer Segments (RFM)** | ✅ | Open Loyalty segments |
| Fraud Detection | ✅ | Voucherify anti-fraud |
| Webhooks | ✅ | Open Loyalty webhooks |
| GDPR Export | ✅ | Compliance |
| Analytics & Insights | ✅ | Open Loyalty analytics |

---

## 🔑 API Endpoints

Base URL: `/api/loyalty/`

### Core
- `GET/POST /customers/`
- `GET /customers/{id}/stats/`
- `GET/POST /transactions/`
- `GET /events/`
- `GET /health/`

### Points
- `GET /points/?customer_id=X`
- `POST /points/earn/`
- `POST /points/adjust/` (admin)
- `GET /ledger/?customer=X`
- `POST /transfers/transfer/`
- `GET /conversions/calculate/`

### Tiers
- `GET /tiers/`
- `GET /user-tiers/my_tier/?customer_id=X`
- `POST /user-tiers/evaluate/`
- `GET /user-tiers/progress/?customer_id=X`

### Redemption
- `POST /redemptions/redeem/`
- `POST /redemptions/{id}/approve/` (admin)
- `POST /vouchers/generate/` (admin)
- `POST /vouchers/use/`
- `POST /gift-cards/issue/` (admin)
- `POST /gift-cards/redeem/`

### Gamification
- `GET /partners/` — Partner merchants
- `POST /partners/{id}/earn/` — Coalition earn (API key)
- `GET /leaderboard/top/`

### Admin
- `GET /admin/customer_overview/?customer_id=X`
- `GET /admin/fraud_logs/`
- `POST /insights/generate/`
- `GET /health/`

---

## ⚙️ Celery Tasks (Schedule)

```python
# celery beat schedule
CELERY_BEAT_SCHEDULE = {
    'expire-points-daily': {
        'task': 'djoyalty.expire_points',
        'schedule': crontab(hour=0, minute=0),
    },
    'evaluate-tiers-monthly': {
        'task': 'djoyalty.evaluate_all_tiers',
        'schedule': crontab(day_of_month=1),
    },
    'check-broken-streaks': {
        'task': 'djoyalty.check_broken_streaks',
        'schedule': crontab(hour=0, minute=30),
    },
    'fraud-scan-hourly': {
        'task': 'djoyalty.fraud_scan',
        'schedule': crontab(minute=0),
    },
    'daily-insights': {
        'task': 'djoyalty.generate_daily_insight',
        'schedule': crontab(hour=1, minute=0),
    },
}
```

---

## 🛡️ Fraud Protection

- Rapid transaction detection (10 txns/15min = flag)
- Daily redemption cap (configurable)
- Cashout fraud scoring
- IP-based velocity checks
- Admin review queue

---

## 📦 Requirements

```
django>=4.2
djangorestframework>=3.14
celery>=5.3  # Optional (for background tasks)
redis>=5.0   # Optional (for caching + celery)
```
