# Wallet — Final Complete Package

## এই package-এ কী আছে

এটা তোমার সম্পূর্ণ wallet backend — পুরনো code + নতুন code + সব missing components একসাথে।

## File Structure

```
wallet/
├── models/                    ← সব DB models
├── services/                  ← Business logic
│   ├── core/WalletService.py
│   ├── earning/EarningService.py
│   ├── gateway/               ← bKash, Nagad, Rocket, SSLCommerz, Payoneer, Wise
│   └── offerwall/             ← OGAds, AdGate, Offertoro, Monlix
├── viewsets/                  ← REST API viewsets
│   ├── GamificationViewSet.py ← NEW: Scratchcard + Spin Wheel
│   └── RevenueSharingViewSet.py ← NEW: Advertiser + Publisher
├── migrations/
│   └── 0012_gamification_revenue_sharing.py ← NEW
├── adapters/                  ← Offerwall adapters
├── gamification.py            ← NEW: Scratchcard + Spin Wheel
├── push_notification_service.py ← NEW: FCM + APNs
├── revenue_sharing.py         ← NEW: Advertiser billing + revenue split
├── urls.py                    ← FINAL: সব routes wired
└── SETTINGS_ADDITIONS.py      ← settings.py-তে যা add করতে হবে
```

## Setup Steps

### 1. settings.py এ add করো (SETTINGS_ADDITIONS.py দেখো)
```python
SCRATCHCARD_COOLDOWN_HOURS = 24
SPINWHEEL_COOLDOWN_HOURS   = 24
FIREBASE_CREDS_PATH = "/path/to/firebase.json"
PLATFORM_REVENUE_SHARE_PCT = "0.30"
# বাকি SETTINGS_ADDITIONS.py থেকে copy করো
```

### 2. main urls.py তে add করো
```python
path("api/wallet/", include("api.wallet.urls")),
```

### 3. pip install
```bash
pip install firebase-admin httpx pyjwt
```

### 4. migrate
```bash
python manage.py migrate
```

### 5. Admin panel এ configure করো
- `ScratchcardPrize` — prize pool add করো
- `SpinWheelSegment` — wheel segments add করো

## নতুন API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/wallet/scratchcard/` | GET | Cooldown status |
| `/api/wallet/scratchcard/claim/` | POST | Daily scratchcard claim |
| `/api/wallet/spinwheel/config/` | GET | Wheel segments |
| `/api/wallet/spinwheel/spin/` | POST | Spin the wheel |
| `/api/wallet/gamification/history/` | GET | Win history |
| `/api/wallet/advertiser/account/` | GET/POST | Advertiser account |
| `/api/wallet/advertiser/deposit/` | POST | Top up balance |
| `/api/wallet/advertiser/campaigns/` | GET/POST | Campaigns |
| `/api/wallet/publisher/earnings/summary/` | GET | Revenue summary |
| `/api/wallet/push/register/` | POST | Register device token |
| `/api/wallet/push/unregister/` | POST | Unregister token |

## Celery Beat Tasks (tasks.py তে add করো)
```python
"reset-daily-campaign-spend": {
    "task": "api.wallet.tasks.reset_daily_campaign_spend",
    "schedule": crontab(hour=0, minute=0),
},
```
