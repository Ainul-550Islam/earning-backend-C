# 🚀 Earning Platform — Full Stack SaaS

A production-ready **multi-tenant earning platform** with Django REST Framework backend and React frontend. Supports ad networks, wallet management, fraud detection, real-time analytics, and a powerful admin panel.

---

## ✨ Features

### Backend (Django + DRF)
| Module | Description |
|--------|-------------|
| 👥 **Users** | Registration, Login, OTP, JWT Auth |
| 💰 **Wallet** | Balance, Transactions, Withdrawals |
| 📡 **Ad Networks** | AdMob, Unity Ads, AppLovin, IronSource |
| 🛡️ **Fraud Detection** | IP blocking, behavior analysis, rate limiting |
| 📊 **Analytics** | Events, funnels, retention, revenue |
| 🏢 **Multi-Tenant** | Full tenant isolation per organization |
| 🔔 **Notifications** | Push, Email, In-app |
| 💳 **Payment Gateways** | bKash, Nagad, Stripe, PayPal, SSLCommerz |
| 🎮 **Gamification** | Points, badges, leaderboards |
| 🤖 **Auto-Mod** | Automated content moderation |
| 📋 **Audit Logs** | Full activity trail |
| ⚙️ **Admin Panel** | API endpoint control, bulk toggles |
| 🔄 **Celery** | Async tasks, scheduled jobs |
| 📦 **Backup** | Automated database backups |
| + 24 more modules | ... |

### Frontend (React + Vite)
- 48 pages with dark cyberpunk UI
- Real-time dashboard with live stats
- **API Endpoint Control** — enable/disable 3874 endpoints live
- Deployed on **Vercel** (auto-deploy on push)

---

## 🏗️ Tech Stack

```
Backend:   Django 5 · DRF · PostgreSQL · Redis · Celery · WebSocket
Frontend:  React 18 · Vite · Axios · CSS Modules
Deploy:    Railway (backend) · Vercel (frontend)
Auth:      JWT + OTP
Storage:   AWS S3 / local
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+

### 1. Clone & Setup Backend
```bash
git clone https://github.com/your-username/earning-backend.git
cd earning-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Edit .env with your values

# Database
python manage.py migrate
python manage.py seed_tenant  # Create demo tenant
python manage.py createsuperuser

# Run
python manage.py runserver
```

### 2. Setup Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
# Set VITE_API_URL=http://localhost:8000/api

npm run dev
```

### 3. Start Celery (for async tasks)
```bash
# In a separate terminal
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

---

## ⚙️ Environment Variables

```env
# See .env.example for full list

# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname

# Redis
REDIS_URL=redis://localhost:6379/0

# AWS S3 (optional)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
```

---

## 🚢 Deploy

### Railway (Backend)
1. Connect GitHub repo to Railway
2. Set environment variables in Railway dashboard
3. Push to `main` → auto-deploy triggers

### Vercel (Frontend)
1. Connect `frontend/` folder to Vercel
2. Set `VITE_API_URL` in Vercel environment
3. Push to `main` → auto-deploy triggers

---

## 🧪 Running Tests

```bash
# All tests
python manage.py test

# Specific module
python manage.py test api.wallet
python manage.py test api.users

# With coverage report
coverage run manage.py test
coverage report
coverage html  # Opens htmlcov/index.html
```

---

## 📁 Project Structure

```
earning-backend/
├── api/
│   ├── ad_networks/       # Ad network integrations
│   ├── admin_panel/       # Admin controls + endpoint toggles
│   ├── analytics/         # Event tracking & analytics
│   ├── audit_logs/        # Activity audit trail
│   ├── auto_mod/          # Auto moderation
│   ├── backup/            # Database backup system
│   ├── behavior_analytics/# User behavior tracking
│   ├── cache/             # Cache management
│   ├── cms/               # Content management
│   ├── fraud_detection/   # Fraud prevention
│   ├── gamification/      # Points & badges
│   ├── kyc/               # Know Your Customer
│   ├── notifications/     # Push/Email/In-app
│   ├── payment_gateways/  # Payment providers
│   ├── referral/          # Referral system
│   ├── security/          # Security controls
│   ├── subscription/      # Subscription plans
│   ├── tenants/           # Multi-tenancy
│   ├── users/             # User management
│   ├── wallet/            # Wallet & transactions
│   └── ...
├── config/                # Django settings
├── core/                  # Shared base models
├── frontend/              # React app
│   ├── src/
│   │   ├── pages/         # 48 page components
│   │   ├── components/    # Shared UI components
│   │   └── api/           # Axios instances
│   └── vercel.json
├── Dockerfile
├── Procfile
└── railway.toml
```

---

## 🔑 Default Credentials (Demo)

After `seed_tenant`:
```
Admin: admin@demo.com / admin123
User:  user@demo.com  / user123
```
> ⚠️ Change these immediately in production!

---

## 📄 License

MIT License — free to use, modify, and sell.

---

## 🤝 Support

For questions or custom development, open an issue or contact via GitHub.
