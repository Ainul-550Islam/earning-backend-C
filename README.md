# Ì∫Ä EarningApp ‚Äî White-label Multi-Tenant Earning Platform

[![Django](https://img.shields.io/badge/Django-5.0-green)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.15-blue)](https://django-rest-framework.org)
[![License](https://img.shields.io/badge/License-Commercial-red)](LICENSE)

A **production-ready white-label earning platform** you can sell to clients. Each client gets their own branding, domain, users and settings ‚Äî all on one backend.

---

## ‚ú® Features

| Module | Description |
|--------|-------------|
| Ìø¢ **White-label** | Per-tenant logo, colors, domain, feature flags |
| Ì±• **Users** | Registration, Login, OTP, JWT, Google OAuth |
| Ì≤∞ **Wallet** | Balance, Transactions, Withdrawals |
| Ì≥° **Ad Networks** | AdMob, Unity, AppLovin, IronSource |
| ÌæØ **Offer Walls** | AdGate, AdGem, Tapjoy |
| Ìª°Ô∏è **Fraud Detection** | IP blocking, device fingerprint, VPN detect |
| Ì≥ä **Analytics** | Events, revenue, retention, real-time |
| Ì¥î **Notifications** | Push (FCM), Email, SMS (Twilio), In-app |
| Ì≤≥ **Payments** | bKash, Nagad, Rocket, Stripe, PayPal |
| ÌæÆ **Gamification** | Points, badges, leaderboards, contests |
| Ì¥ê **KYC** | Document verification, identity check |
| Ì≤¨ **Messaging** | Real-time chat (WebSocket) |
| Ì≥¶ **Subscription** | Plan management, billing |
| Ì¥Ñ **Referral** | Multi-level referral system |

---

## ÌøóÔ∏è Tech Stack

- **Backend**: Django 5.0 + Django REST Framework
- **Database**: PostgreSQL
- **Cache/Queue**: Redis + Celery
- **WebSocket**: Django Channels
- **Deploy**: Docker + Railway/Render
- **Docs**: Swagger UI (`/api/docs/`)

---

## ‚ö° Quick Start

### Option 1: Automated Installer
```bash
git clone <repo>
cd earning-backend
pip install -r requirements.txt
cp .env.example .env   # fill in your values
python installer.py
```

### Option 2: Manual Setup
```bash
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_tenant
python manage.py runserver
```

---

## Ìºê API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/auth/register/` | Register new user |
| `POST /api/auth/login/` | Login + get JWT token |
| `GET /api/wallet/` | Get wallet balance |
| `POST /api/wallet/withdraw/` | Request withdrawal |
| `GET /api/offers/` | List available offers |
| `GET /api/referral/` | Get referral code |
| `GET /api/gamification/leaderboard/` | Leaderboard |
| `GET /api/tenants/my_tenant/` | Get tenant branding |
| `GET /api/tenants/tenant-billing/status/` | Billing status |
| `GET /api/docs/` | Full Swagger docs |

---

## Ìø¢ White-label Setup

### 1. Create a tenant (for each client)
```bash
python manage.py seed_tenant
```

### 2. Configure branding via API
```
PATCH /api/tenants/{id}/update_branding/
{
  "name": "ClientApp",
  "primary_color": "#FF5733",
  "secondary_color": "#333333"
}
```

### 3. React Native app connects with API key
```
Header: X-API-Key: <tenant_api_key>
```

---

## Ì¥ß Environment Variables (.env)
```env
SECRET_KEY=your-secret-key
DEBUG=False
DATABASE_URL=postgres://user:pass@host:5432/db
REDIS_URL=redis://localhost:6379/0
STRIPE_SECRET_KEY=sk_live_...
ENVATO_API_TOKEN=...   # Codecanyon license validation
FIREBASE_CREDENTIALS_PATH=firebase.json
BKASH_APP_KEY=...
NAGAD_MERCHANT_ID=...
```

---

## Ì≥± React Native Integration
```javascript
const TENANT_API_KEY = 'your-api-key';
const BASE_URL = 'https://your-backend.railway.app';

// Get tenant branding
const branding = await fetch(`${BASE_URL}/api/tenants/my_tenant/`, {
  headers: { 'X-API-Key': TENANT_API_KEY }
});

// Login
const login = await fetch(`${BASE_URL}/api/auth/login/`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'X-API-Key': TENANT_API_KEY },
  body: JSON.stringify({ email, password })
});
```

---

## Ì≥ã Plans

| Plan | Users | Price |
|------|-------|-------|
| Basic | 100 | $49/mo |
| Pro | 1,000 | $99/mo |
| Enterprise | Unlimited | $299/mo |

---

## Ì≥û Support

- Email: support@earningapp.com
- Docs: `/api/docs/`
- Issues: GitHub Issues

---

## Ì≥Ñ License

Commercial License ‚Äî Codecanyon Regular/Extended License
