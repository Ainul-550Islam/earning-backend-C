# 📥 Installation Guide

## Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.12+ |
| PostgreSQL | 13+ |
| Redis | 6+ |
| Node.js (optional) | 18+ |

---

## Step 1: Clone & Setup

```bash
git clone <your-repo-url>
cd earning-backend
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

---

## Step 2: Environment Variables

```bash
cp .env.example .env
```

Edit `.env` — minimum required:
```env
SECRET_KEY=your-secret-key-minimum-50-chars
DEBUG=False
DATABASE_URL=postgres://user:pass@localhost:5432/earningapp
REDIS_URL=redis://localhost:6379/0
```

---

## Step 3: Database Setup

```bash
# Create PostgreSQL database
createdb earningapp

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

---

## Step 4: Create First Tenant

```bash
python manage.py seed_tenant
```

This will output your **API Key** — save it for React Native app.

---

## Step 5: Run Server

```bash
# Development
python manage.py runserver

# Production (Gunicorn)
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

---

## Step 6: Run Celery (Background Tasks)

```bash
# Worker
celery -A config worker -l info

# Beat Scheduler (cron jobs)
celery -A config beat -l info
```

---

## Verify Installation

Open browser:
- `http://localhost:8000/admin/` → Django Admin
- `http://localhost:8000/api/docs/` → API Docs

---

## Common Issues

### "No module named 'environ'"
```bash
pip install django-environ
```

### "Redis connection refused"
```bash
# Start Redis
redis-server
```

### "relation does not exist"
```bash
python manage.py migrate --run-syncdb
```

### Static files not loading
```bash
python manage.py collectstatic
```
