# 🚀 EarningApp — White-label Multi-Tenant Earning Platform

[![Django](https://img.shields.io/badge/Django-5.0-brightgreen)](https://djangoproject.com)
[![DRF](https://img.shields.io/badge/DRF-3.15-blue)](https://django-rest-framework.org)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-Commercial-red)](LICENSE)

> **Sell this app to unlimited clients. Each client gets their own branding, domain, users, and settings — all running on one powerful backend.**

---

## 📦 What's Included

```
earning-backend/          ← Django Backend (this package)
├── 44 API modules
├── White-label tenant system
├── Multi-payment gateway
├── Fraud detection
├── Real-time WebSocket
├── Celery background tasks
└── Docker ready
```

---

## ✨ Full Feature List

### 🏢 White-label / Multi-Tenant
- Per-tenant custom logo, colors, domain
- Per-tenant feature on/off (referral, KYC, offers, etc.)
- Per-tenant payout rules & limits
- Tenant billing (Trial → Paid → Enterprise)
- Tenant admin dashboard API
- Codecanyon license validator
- One-command installer (`python installer.py`)

### 👥 Users & Auth
- Register / Login / Logout
- OTP verification (Email + SMS)
- JWT Authentication (access + refresh tokens)
- Google OAuth2 login
- Password reset via email
- Login history & device tracking
- IP reputation check
- Multi-account detection

### 💰 Wallet System
- Current balance, pending, frozen, bonus
- Wallet transactions with full history
- Deposit / Withdrawal requests
- Withdrawal fee configuration
- Currency support (BDT, USD, etc.)
- Bonus expiry system

### 💳 Payment Gateways
| Gateway | Type | Status |
|---------|------|--------|
| bKash | Mobile Banking (BD) | ✅ |
| Nagad | Mobile Banking (BD) | ✅ |
| Rocket | Mobile Banking (BD) | ✅ |
| Stripe | International Card | ✅ |
| PayPal | International | ✅ |

### 📡 Ad Networks
| Network | SDK | Webhook |
|---------|-----|---------|
| AdMob | ✅ | ✅ |
| Unity Ads | ✅ | ✅ |
| AppLovin | ✅ | ✅ |
| IronSource | ✅ | ✅ |

### 🎯 Offer Walls
| Provider | Postback | Status |
|----------|----------|--------|
| AdGate | ✅ | ✅ |
| AdGem | ✅ | ✅ |
| Tapjoy | ✅ | ✅ |

### 🛡️ Fraud Detection
- IP blocking & geolocation
- VPN / Proxy detection
- Device fingerprinting
- Click fraud detection
- Multi-account detection
- Behavior pattern analysis
- Auto-ban system
- Fraud score calculator

### 📊 Analytics
- Real-time dashboard
- User analytics (registration, activity, churn)
- Revenue analytics
- Offer performance tracking
- Behavior analytics
- Admin analytics dashboard
- Excel/PDF report export

### 🔔 Notifications
- Firebase Push (FCM) — Android & iOS
- Email (SendGrid + SMTP)
- SMS (Twilio)
- Telegram Bot
- In-app notifications
- Notification campaigns
- Per-user preferences

### 🎮 Gamification
- Points system
- Badges & achievements
- Leaderboard (daily, weekly, all-time)
- Contests & tournaments
- User levels & ranks
- Streak rewards

### 🔐 KYC (Know Your Customer)
- Document upload (NID, passport)
- Identity verification
- KYC status tracking
- Admin review panel

### 💬 Real-time Messaging
- WebSocket chat (Django Channels)
- Support ticket system
- Broadcast messages
- File/image attachments

### 🔄 Referral System
- Unique referral codes
- Multi-level referral earnings
- Referral analytics
- Per-tenant referral settings

### 📦 Subscription Plans
- Plan management (Basic/Pro/Enterprise)
- Feature gating by plan
- Stripe billing integration
- Invoice generation

### 🎰 Offer/Task Management
- Task creation & management
- Offer categories
- Task verification (auto + manual)
- Screenshot validation
- Social media task (Facebook, Instagram, YouTube, TikTok, Twitter)

### 🔧 Admin Panel
- Full Django Admin
- Custom admin dashboard
- User management
- Transaction management
- Fraud review queue
- Analytics dashboard
- Backup management
- Audit logs

### 🔒 Security
- Rate limiting (per IP, per user)
- JWT token blacklist
- Security audit logs
- API encryption
- CORS configuration
- Webhook IP whitelist

### 🗄️ System
- Redis caching
- Celery background tasks + beat scheduler
- Database backup (local + S3)
- Audit logs
- Version control API
- Maintenance mode
- Docker + docker-compose ready

---

## 🏗️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend Framework | Django 5.0 |
| API | Django REST Framework 3.15 |
| Database | PostgreSQL |
| Cache | Redis |
| Task Queue | Celery + Redis |
| WebSocket | Django Channels |
| API Docs | Swagger UI (drf-spectacular) |
| Auth | JWT (SimpleJWT) |
| Deploy | Docker / Railway / Render |

---

## ⚡ Installation

### Option 1: One-Command Installer (Recommended)
```bash
git clone <your-repo>
cd earning-backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
python installer.py
```

### Option 2: Manual
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_tenant
python manage.py runserver
```

### Option 3: Docker
```bash
cp .env.example .env
docker-compose up --build
```

---

## 🔧 Environment Setup (.env)

```env
# Core
SECRET_KEY=your-50-char-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,localhost

# Database
DATABASE_URL=postgres://user:password@localhost:5432/earningapp

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Firebase (Push Notifications)
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# bKash
BKASH_APP_KEY=
BKASH_APP_SECRET=
BKASH_USERNAME=
BKASH_PASSWORD=

# Nagad
NAGAD_MERCHANT_ID=
NAGAD_MERCHANT_PRIVATE_KEY=

# Twilio SMS
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# Codecanyon License
ENVATO_API_TOKEN=your-envato-token
```

---

## 🌐 API Reference

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Register new user |
| POST | `/api/auth/login/` | Login → get JWT tokens |
| POST | `/api/auth/logout/` | Logout + blacklist token |
| POST | `/api/auth/token/refresh/` | Refresh access token |
| POST | `/api/auth/otp/verify/` | Verify OTP code |
| POST | `/api/auth/password/reset/` | Request password reset |

### Wallet
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/wallet/` | Get wallet balance |
| GET | `/api/wallet/transactions/` | Transaction history |
| POST | `/api/wallet/withdraw/` | Request withdrawal |
| GET | `/api/wallet/withdraw/history/` | Withdrawal history |

### Offers & Tasks
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/offers/` | List all offers |
| POST | `/api/offers/{id}/complete/` | Mark offer complete |
| GET | `/api/tasks/` | List tasks |
| POST | `/api/tasks/{id}/submit/` | Submit task proof |

### Referral
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/referral/` | Get referral code & stats |
| POST | `/api/referral/apply/` | Apply referral code |

### Gamification
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/gamification/leaderboard/` | Global leaderboard |
| GET | `/api/gamification/badges/` | User badges |
| GET | `/api/gamification/points/` | Points history |

### Notifications
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/notifications/` | List notifications |
| POST | `/api/notifications/device-token/` | Register FCM token |
| PATCH | `/api/notifications/{id}/read/` | Mark as read |

### White-label (Tenant)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tenants/my_tenant/` | Get branding for current tenant |
| GET | `/api/tenant-billing/status/` | Check billing status |
| PATCH | `/api/tenants/{id}/update_branding/` | Update logo/colors |
| PATCH | `/api/tenants/{id}/update_features/` | Toggle features |
| GET | `/api/tenants/{id}/dashboard/` | Tenant stats |

> 📖 **Full Interactive Docs**: `https://your-domain.com/api/docs/`

---

## 📱 React Native Integration

```javascript
// config.js
export const API_KEY = 'your-tenant-api-key';
export const BASE_URL = 'https://your-backend.railway.app';

// Get tenant branding (app loads colors/logo from server)
const getBranding = async () => {
  const res = await fetch(`${BASE_URL}/api/tenants/my_tenant/`, {
    headers: { 'X-API-Key': API_KEY }
  });
  return res.json();
  // Returns: { name, primary_color, secondary_color, logo, enable_referral, ... }
};

// Login
const login = async (email, password) => {
  const res = await fetch(`${BASE_URL}/api/auth/login/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY
    },
    body: JSON.stringify({ email, password })
  });
  const data = await res.json();
  // data.access = JWT token
  // data.refresh = refresh token
  return data;
};

// Get wallet balance
const getWallet = async (token) => {
  const res = await fetch(`${BASE_URL}/api/wallet/`, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-API-Key': API_KEY
    }
  });
  return res.json();
};
```

---

## 🏢 White-label Client Setup

### Step 1: Create tenant for new client
```bash
python manage.py seed_tenant
# OR via API:
POST /api/tenants/
{
  "name": "ClientApp",
  "domain": "client.com",
  "plan": "pro",
  "admin_email": "admin@client.com"
}
```

### Step 2: Share API key with client
```
API Key: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
Header: X-API-Key: <api_key>
```

### Step 3: Client customizes branding
```
PATCH /api/tenants/{id}/update_branding/
{
  "primary_color": "#FF5733",
  "secondary_color": "#333333",
  "logo": <image_file>
}
```

### Step 4: Client React Native app uses API key
All data is automatically isolated per tenant. ✅

---

## 🐳 Docker Deployment

```bash
# Build and run
docker-compose up --build -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create admin
docker-compose exec web python manage.py createsuperuser
```

### docker-compose.yml
```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - db
      - redis
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: earningapp
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
  redis:
    image: redis:7-alpine
  celery:
    build: .
    command: celery -A config worker -l info
    env_file: .env
    depends_on:
      - redis
  celery-beat:
    build: .
    command: celery -A config beat -l info
    env_file: .env
    depends_on:
      - redis
```

---

## 🚀 Railway Deployment (One-Click)

1. Fork this repo
2. Connect to Railway
3. Add PostgreSQL + Redis plugins
4. Set environment variables
5. Deploy ✅

---

## 📋 Admin Panel URLs

| URL | Description |
|-----|-------------|
| `/admin/` | Main Django Admin |
| `/task-admin/` | Task Management Admin |
| `/api/cms-admin/` | CMS Admin |
| `/api/security-admin/` | Security Admin |
| `/api/docs/` | Swagger API Docs |
| `/api/redoc/` | ReDoc API Docs |

---

## 🔄 Changelog

### v1.0.0
- Initial release
- 44 API modules
- White-label multi-tenant system
- Full payment gateway integration
- Fraud detection system
- React Native ready API

---

## 📞 Support

- 📧 Email: support@earningapp.com
- 📖 Docs: `/api/docs/`
- 🐛 Bugs: Open a GitHub issue
- ⭐ Rate us on Codecanyon!

---

## 📄 License

**Commercial License** — Codecanyon Regular/Extended License

- Regular License: Use in 1 end product
- Extended License: Use in unlimited end products

© 2026 EarningApp. All rights reserved.
