# KYC World #1 — Complete Setup & Deployment Guide

## Quick Start (5 minutes)

```bash
# 1. Install dependencies
pip install djangorestframework celery redis pillow \
            pytesseract boto3 google-cloud-vision \
            requests drf-spectacular

# 2. Add to INSTALLED_APPS in settings.py
INSTALLED_APPS += ['api.kyc']

# 3. Include all URLs in main urls.py
from django.urls import path, include
urlpatterns += [
    path('api/kyc/',          include('api.kyc.urls')),
    path('api/kyc/aml/',      include('api.kyc.aml.urls')),
    path('api/kyc/kyb/',      include('api.kyc.kyb.urls')),
    path('api/kyc/liveness/', include('api.kyc.liveness.urls')),
    path('api/kyc/compliance/', include('api.kyc.compliance.urls')),
    path('api/kyc/monitoring/', include('api.kyc.transaction_monitoring.urls')),
    path('api/kyc/billing/',  include('api.kyc.billing.urls')),
    path('api/kyc/workflow/', include('api.kyc.workflow.urls')),
    path('api/kyc/health/',   include('api.kyc.monitoring.urls')),
    # API docs
    *get_kyc_schema_urls(),
]

# 4. Run migrations
python manage.py migrate kyc

# 5. Start Celery workers
celery -A your_project worker -Q kyc_ai,kyc_fraud --concurrency=2 &
celery -A your_project worker -Q kyc_notifications,kyc_maintenance --concurrency=4 &
celery -A your_project beat --loglevel=info &
```

---

## AI Provider Setup

### Option A — Google Cloud Vision (OCR) + AWS Rekognition (Face)
Best combination. Google Vision excels at Bengali text.

```bash
# Google Cloud Vision
pip install google-cloud-vision
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
# OR in settings.py:
# from google.oauth2 import service_account
# GOOGLE_CREDENTIALS = service_account.Credentials.from_service_account_file(...)

# AWS Rekognition + Textract
pip install boto3
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=ap-southeast-1
```

```python
# settings.py
KYC_OCR_PROVIDER_PRIORITY = ['google_vision', 'aws_textract', 'tesseract']
KYC_FACE_PROVIDER          = 'aws_rekognition'
```

### Option B — Azure (OCR + Face)
```bash
pip install azure-cognitiveservices-vision-computervision azure-cognitiveservices-vision-face msrest
export AZURE_VISION_KEY=your_key
export AZURE_VISION_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
export AZURE_FACE_KEY=your_face_key
export AZURE_FACE_ENDPOINT=https://your-face.cognitiveservices.azure.com/
```

### Option C — Free / Local (Development)
```bash
# Tesseract OCR (free, local)
sudo apt-get install tesseract-ocr tesseract-ocr-ben   # Bengali support
pip install pytesseract

# Local face matching
pip install deepface tensorflow  # or just use mock
```

---

## AML Provider Setup

### ComplyAdvantage (Recommended)
```python
# settings.py
COMPLYADVANTAGE_API_KEY = 'your_api_key'
```
Pricing: ~$0.10-$0.50/search. Free trial available.

### Local Sanctions DB (Free)
```bash
# Download and update local sanctions lists
python manage.py update_sanctions_list --source all
# Schedule weekly update (already in Celery beat)
```

---

## IP Intelligence Setup

```python
# settings.py — choose one:
IPINFO_TOKEN = 'your_token'          # ipinfo.io (50k free/month)
# OR
MAXMIND_DB_PATH = '/usr/local/share/GeoIP/GeoLite2-City.mmdb'
```

---

## Environment Variables (production)

```bash
# Django
SECRET_KEY=your_secret_key
DEBUG=False
ALLOWED_HOSTS=yourdomain.com

# Database
DATABASE_URL=postgres://user:pass@host:5432/kyc_db

# Redis (Celery + Cache)
REDIS_URL=redis://localhost:6379/0

# AI Providers
GOOGLE_APPLICATION_CREDENTIALS=/app/google-service-account.json
AWS_ACCESS_KEY_ID=AKIAxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxx
AWS_DEFAULT_REGION=ap-southeast-1

# AML
COMPLYADVANTAGE_API_KEY=xxxxxxxxxx

# IP Intelligence
IPINFO_TOKEN=xxxxxxxxxx

# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your@email.com
EMAIL_HOST_PASSWORD=your_app_password

# File Storage (S3 recommended for production)
AWS_S3_BUCKET=your-kyc-bucket
AWS_S3_REGION=ap-southeast-1
DEFAULT_FILE_STORAGE=storages.backends.s3boto3.S3Boto3Storage

# KYC Config
KYC_OCR_PROVIDER_PRIORITY=google_vision,aws_textract,tesseract
KYC_FACE_PROVIDER=aws_rekognition
```

---

## Management Commands

```bash
# Expire overdue KYCs (daily via cron)
python manage.py expire_kycs
python manage.py expire_kycs --dry-run          # preview
python manage.py expire_kycs --notify           # send notifications

# Generate analytics
python manage.py generate_kyc_analytics --days 7

# Update sanctions lists (weekly)
python manage.py update_sanctions_list --source all  # UN + OFAC + EU + BD
python manage.py update_sanctions_list --source ofac

# Run periodic AML re-screening
python manage.py run_periodic_aml_screening --days-since 30 --provider complyadvantage

# Cleanup old data
python manage.py cleanup_kyc_data --days 30
```

---

## Docker Compose (Production)

```yaml
version: '3.9'
services:
  web:
    build: .
    command: gunicorn your_project.wsgi:application --bind 0.0.0.0:8000
    environment:
      - DATABASE_URL=postgres://kyc:pass@db:5432/kyc
      - REDIS_URL=redis://redis:6379/0
    depends_on: [db, redis]

  celery-ai:
    build: .
    command: celery -A your_project worker -Q kyc_ai,kyc_fraud --concurrency=2
    environment:
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-key.json

  celery-default:
    build: .
    command: celery -A your_project worker -Q kyc_notifications,kyc_maintenance,kyc_batch --concurrency=4

  celery-beat:
    build: .
    command: celery -A your_project beat --loglevel=info

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: kyc
      POSTGRES_PASSWORD: pass

  redis:
    image: redis:7-alpine
```

---

## API Documentation

After setup, access:
- Swagger UI: `https://yourdomain.com/api/kyc/docs/`
- ReDoc:       `https://yourdomain.com/api/kyc/redoc/`
- Schema JSON: `https://yourdomain.com/api/kyc/schema/`

---

## Health Checks

```bash
# Basic (load balancer probe)
curl https://yourdomain.com/api/kyc/health/

# Deep (full system)
curl https://yourdomain.com/api/kyc/health/deep/

# Provider status (admin only)
curl -H "Authorization: Bearer TOKEN" https://yourdomain.com/api/kyc/health/providers/
```

---

## Testing

```bash
# Run all tests
python manage.py test api.kyc.tests

# Run specific test class
python manage.py test api.kyc.tests.test_models.KYCModelTest
python manage.py test api.kyc.tests.test_security.FraudDetectorTest

# Coverage
pip install coverage
coverage run manage.py test api.kyc.tests
coverage report
```
