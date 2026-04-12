# Alerts API Deployment Guide

## Overview

This guide covers deployment strategies, configurations, and best practices for the Alerts API in production environments.

## Deployment Options

### 1. Traditional Server Deployment

#### System Requirements

**Minimum Requirements:**
- CPU: 2 cores
- RAM: 4GB
- Storage: 50GB SSD
- OS: Ubuntu 20.04+ / CentOS 8+

**Recommended Requirements:**
- CPU: 4 cores
- RAM: 8GB
- Storage: 100GB SSD
- OS: Ubuntu 22.04 LTS

#### Dependencies

```bash
# System packages
sudo apt update
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib redis-server nginx

# Python packages
pip install gunicorn psycopg2-binary redis celery django-celery-beat django-celery-results
```

#### Database Setup

```bash
# PostgreSQL
sudo -u postgres createuser alerts_user
sudo -u postgres createdb alerts_db
sudo -u postgres psql -c "ALTER USER alerts_user PASSWORD 'secure_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE alerts_db TO alerts_user;"
```

#### Redis Setup

```bash
# Redis configuration
sudo nano /etc/redis/redis.conf
# Set: bind 127.0.0.1, requirepass, maxmemory, etc.

sudo systemctl enable redis-server
sudo systemctl start redis-server
```

#### Application Deployment

```bash
# Clone repository
git clone <repository-url>
cd alerts-api

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Environment configuration
cp .env.example .env
nano .env

# Database migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser

# Load initial data
python manage.py loaddata alerts/fixtures/core_alerts.json
```

#### Gunicorn Configuration

```bash
# Create gunicorn config
sudo nano /etc/systemd/system/alerts-api.service
```

```ini
[Unit]
Description=Alerts API Gunicorn daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/alerts-api
Environment="PATH=/path/to/alerts-api/venv/bin"
ExecStart=/path/to/alerts-api/venv/bin/gunicorn \
    --workers 4 \
    --worker-class sync \
    --worker-connections 1000 \
    --timeout 30 \
    --bind unix:/run/gunicorn.sock \
    alerts.wsgi:application

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable alerts-api
sudo systemctl start alerts-api
```

#### Nginx Configuration

```nginx
server {
    listen 80;
    server_name api.example.com;

    location /static/ {
        alias /path/to/alerts-api/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /path/to/alerts-api/media/;
    }

    location / {
        proxy_pass http://unix:/run/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Celery Configuration

```bash
# Create celery service files
sudo nano /etc/systemd/system/alerts-worker.service
```

```ini
[Unit]
Description=Alerts API Celery Worker
After=network.target redis.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/alerts-api
Environment="PATH=/path/to/alerts-api/venv/bin"
ExecStart=/path/to/alerts-api/venv/bin/celery -A alerts worker \
    --loglevel=info \
    --concurrency=4

[Install]
WantedBy=multi-user.target
```

```bash
sudo nano /etc/systemd/system/alerts-beat.service
```

```ini
[Unit]
Description=Alerts API Celery Beat
After=network.target redis.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/alerts-api
Environment="PATH=/path/to/alerts-api/venv/bin"
ExecStart=/path/to/alerts-api/venv/bin/celery -A alerts beat \
    --loglevel=info

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable alerts-worker alerts-beat
sudo systemctl start alerts-worker alerts-beat
```

### 2. Docker Deployment

#### Dockerfile

```dockerfile
FROM python:3.9-slim

# Set environment variables
ENV PYTHUNUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DJANGO_SETTINGS_MODULE=alerts.settings

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create app directory
WORKDIR /app

# Copy application
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/alerts/health/ || exit 1

# Start application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "alerts.wsgi:application"]
```

#### Docker Compose

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://alerts_user:password@db:5432/alerts_db
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=your-secret-key
      - DEBUG=False
    volumes:
      - static_volume:/app/staticfiles
      - media_volume:/app/media
    depends_on:
      - db
      - redis
    restart: unless-stopped

  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=alerts_db
      - POSTGRES_USER=alerts_user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:6-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped

  worker:
    build: .
    command: celery -A alerts worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://alerts_user:password@db:5432/alerts_db
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=your-secret-key
    depends_on:
      - db
      - redis
    restart: unless-stopped

  beat:
    build: .
    command: celery -A alerts beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql://alerts_user:password@db:5432/alerts_db
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=your-secret-key
    depends_on:
      - db
      - redis
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - static_volume:/static
      - media_volume:/media
    depends_on:
      - web
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:
```

#### Docker Compose Commands

```bash
# Build and start services
docker-compose up -d --build

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Load initial data
docker-compose exec web python manage.py loaddata alerts/fixtures/core_alerts.json

# View logs
docker-compose logs -f web
docker-compose logs -f worker
docker-compose logs -f beat

# Scale workers
docker-compose up -d --scale worker=4

# Stop services
docker-compose down

# Remove volumes (WARNING: deletes data)
docker-compose down -v
```

### 3. Kubernetes Deployment

#### Namespace Configuration

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: alerts-api
```

#### ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: alerts-config
  namespace: alerts-api
data:
  DATABASE_HOST: "alerts-db"
  DATABASE_PORT: "5432"
  DATABASE_NAME: "alerts_db"
  DATABASE_USER: "alerts_user"
  REDIS_HOST: "alerts-redis"
  REDIS_PORT: "6379"
  DEBUG: "false"
```

#### Secret

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: alerts-secrets
  namespace: alerts-api
type: Opaque
data:
  DATABASE_PASSWORD: <base64-encoded-password>
  SECRET_KEY: <base64-encoded-secret>
  REDIS_PASSWORD: <base64-encoded-redis-password>
```

#### Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: alerts-api
  namespace: alerts-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: alerts-api
  template:
    metadata:
      labels:
        app: alerts-api
    spec:
      containers:
      - name: alerts-api
        image: alerts-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: alerts-secrets
              key: DATABASE_URL
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: alerts-secrets
              key: SECRET_KEY
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/alerts/health/
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/alerts/health/
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

#### Service

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: alerts-api-service
  namespace: alerts-api
spec:
  selector:
    app: alerts-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

#### Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: alerts-api-ingress
  namespace: alerts-api
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.example.com
    secretName: alerts-api-tls
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: alerts-api-service
            port:
              number: 80
```

#### Persistent Volumes

```yaml
# pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: alerts-db-pvc
  namespace: alerts-api
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
```

#### StatefulSet for Database

```yaml
# postgres-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: alerts-db
  namespace: alerts-api
spec:
  serviceName: alerts-db
  replicas: 1
  selector:
    matchLabels:
      app: alerts-db
  template:
    metadata:
      labels:
        app: alerts-db
    spec:
      containers:
      - name: postgres
        image: postgres:13
        env:
        - name: POSTGRES_DB
          value: alerts_db
        - name: POSTGRES_USER
          value: alerts_user
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: alerts-secrets
              key: POSTGRES_PASSWORD
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: postgres-storage
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 20Gi
```

## Environment Configuration

### Production Settings

```python
# settings.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Security
SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = False
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DATABASE_NAME'),
        'USER': os.environ.get('DATABASE_USER'),
        'PASSWORD': os.environ.get('DATABASE_PASSWORD'),
        'HOST': os.environ.get('DATABASE_HOST', 'localhost'),
        'PORT': os.environ.get('DATABASE_PORT', '5432'),
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c default_transaction_isolation=serializable',
        }
    }
}

# Cache
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            }
        }
    }
}

# Celery
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}'
        },
        'json': {
            '()': 'pythonjson_lib.loggers.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        }
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/alerts/alerts.log',
            'maxBytes': 50000000,  # 50MB
            'backupCount': 5,
            'formatter': 'json'
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        }
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'alerts': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'celery': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False,
        }
    }
}

# Security
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_X_FRAME_OPTIONS = 'DENY'

# CORS
CORS_ALLOWED_ORIGINS = [
    "https://api.example.com",
    "https://admin.example.com"
]
CORS_ALLOW_CREDENTIALS = True

# Media and static files
MEDIA_URL = '/media/'
STATIC_URL = '/static/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
```

### Environment Variables

```bash
# .env
SECRET_KEY=your-very-secret-key-here
DEBUG=False
ALLOWED_HOSTS=api.example.com,admin.example.com

# Database
DATABASE_NAME=alerts_db
DATABASE_USER=alerts_user
DATABASE_PASSWORD=secure_database_password
DATABASE_HOST=localhost
DATABASE_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0

# Email
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=alerts@example.com
EMAIL_HOST_PASSWORD=email_password
DEFAULT_FROM_EMAIL=alerts@example.com

# Monitoring
SENTRY_DSN=https://your-sentry-dsn
NEW_RELIC_LICENSE_KEY=your-newrelic-key

# Performance
GUNICORN_WORKERS=4
GUNICORN_WORKER_CLASS=sync
GUNICORN_WORKER_CONNECTIONS=1000
GUNICORN_TIMEOUT=30
```

## Monitoring and Logging

### Application Monitoring

#### Health Checks

```python
# alerts/views/health.py
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import redis

def health_check(request):
    checks = {}
    
    # Database check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            checks['database'] = 'healthy'
    except Exception as e:
        checks['database'] = f'unhealthy: {str(e)}'
    
    # Redis check
    try:
        r = redis.from_url(settings.CELERY_BROKER_URL)
        r.ping()
        checks['redis'] = 'healthy'
    except Exception as e:
        checks['redis'] = f'unhealthy: {str(e)}'
    
    # Celery check
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        stats = inspect.stats()
        checks['celery'] = 'healthy' if stats else 'unhealthy'
    except Exception as e:
        checks['celery'] = f'unhealthy: {str(e)}'
    
    status = 200 if all(status == 'healthy' for status in checks.values()) else 503
    return JsonResponse({'status': 'healthy' if status == 200 else 'unhealthy', 'checks': checks}, status=status)
```

#### Metrics Collection

```python
# alerts/middleware/metrics.py
import time
import logging
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache

logger = logging.getLogger(__name__)

class MetricsMiddleware(MiddlewareMixin):
    def process_request(self, request):
        start_time = time.time()
        response = self.get_response(request)
        
        # Record metrics
        duration = time.time() - start_time
        status_code = response.status_code
        
        # Cache metrics
        cache_key = f"metrics:{status_code}:{int(duration)}"
        cache.incr(cache_key)
        cache.expire(cache_key, 3600)
        
        # Log slow requests
        if duration > 1.0:  # 1 second
            logger.warning(
                f"Slow request: {request.method} {request.get_full_path()} "
                f"took {duration:.2f}s, status: {status_code}"
            )
        
        return response
```

### Error Tracking

#### Sentry Integration

```python
# settings.py
import sentry_sdk

sentry_sdk.init(
    dsn=os.environ.get('SENTRY_DSN'),
    traces_sample_rate=0.1,
    send_default_pii=False,
    environment=os.environ.get('ENVIRONMENT', 'development'),
    integrations=[sentry_sdk.integrations.django.DjangoIntegration()],
    before_send=lambda event, hint: event.get('logger') == 'django.db.backends' and hint.get('record').sql and 'password' in hint.get('record').sql.lower()
)
```

#### Performance Monitoring

```python
# alerts/tasks/metrics.py
from celery import shared_task
from django.core.cache import cache
from django.db import connection
import time

@shared_task
def collect_metrics():
    """Collect system metrics periodically"""
    metrics = {}
    
    # Database metrics
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    pg_stat_database.datname,
                    pg_stat_database.numbackends,
                    pg_stat_database.xact_commit,
                    pg_stat_database.xact_rollback
                FROM pg_stat_database
            """)
            db_stats = cursor.fetchall()
            metrics['database'] = db_stats
    except Exception as e:
        logger.error(f"Failed to collect database metrics: {e}")
    
    # Cache metrics
    try:
        redis_client = redis.from_url(settings.CELERY_BROKER_URL)
        info = redis_client.info()
        metrics['redis'] = info
    except Exception as e:
        logger.error(f"Failed to collect Redis metrics: {e}")
    
    # Application metrics
    metrics['timestamp'] = time.time()
    cache.set('system_metrics', metrics, timeout=300)
    
    return metrics
```

## Security

### SSL/TLS Configuration

#### Nginx SSL

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/ssl/certs/api.example.com.crt;
    ssl_certificate_key /etc/ssl/private/api.example.com.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-GCM-SHA256';
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    location / {
        proxy_pass http://unix:/run/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
    }
}

server {
    listen 80;
    server_name api.example.com;
    return 301 https://$server_name$request_uri;
}
```

#### Application Security Headers

```python
# alerts/middleware/security.py
from django.http import HttpResponse
from django.conf import settings

class SecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https:; "
            "connect-src 'self' https:api.example.com; "
            "frame-ancestors 'self';"
        )
        
        return response
```

### Access Control

```python
# alerts/permissions.py
from rest_framework.permissions import BasePermission

class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return request.user and request.user.is_staff

class IsOwnerOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True
        return obj.user == request.user
```

### API Rate Limiting

```python
# alerts/throttling.py
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

class AlertRateThrottle(SimpleRateThrottle):
    scope = 'alert'
    rate = '100/hour'

class AdminRateThrottle(SimpleRateThrottle):
    scope = 'admin'
    rate = '500/hour'
```

## Performance Optimization

### Database Optimization

#### Indexes

```python
# models/core.py
class AlertLog(models.Model):
    rule = models.ForeignKey('AlertRule', on_delete=models.CASCADE)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['rule', 'created_at']),
            models.Index(fields=['is_resolved', 'created_at']),
            models.Index(fields=['created_at']),
        ]
```

#### Query Optimization

```python
# services/core.py
class AlertProcessingService:
    def get_recent_alerts(self, hours=24):
        """Get recent alerts with optimized query"""
        from django.db import connection
        
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT al.id, al.message, al.created_at, ar.name as rule_name
                FROM alerts_alertlog al
                JOIN alerts_alertrule ar ON al.rule_id = ar.id
                WHERE al.created_at >= NOW() - INTERVAL '%s hours'
                ORDER BY al.created_at DESC
                LIMIT 100
            """ % hours)
            
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

### Caching Strategy

```python
# services/cache.py
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key

def get_alert_rule_with_cache(rule_id):
    cache_key = f'alert_rule_{rule_id}'
    rule = cache.get(cache_key)
    
    if rule is None:
        rule = AlertRule.objects.get(id=rule_id)
        cache.set(cache_key, rule, timeout=300)  # 5 minutes
    
    return rule

def invalidate_alert_rule_cache(rule_id):
    cache_key = f'alert_rule_{rule_id}'
    cache.delete(cache_key)
```

## Backup and Recovery

### Database Backup

#### Automated Backups

```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/alerts"
DB_NAME="alerts_db"

# Create backup directory
mkdir -p $BACKUP_DIR

# Database backup
pg_dump -h localhost -U alerts_user -d $DB_NAME > $BACKUP_DIR/alerts_backup_$DATE.sql

# Compress backup
gzip $BACKUP_DIR/alerts_backup_$DATE.sql

# Remove old backups (keep last 7 days)
find $BACKUP_DIR -name "alerts_backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed: alerts_backup_$DATE.sql.gz"
```

#### Cron Job

```bash
# Add to crontab
0 2 * * * /path/to/backup.sh
```

### Data Recovery

```bash
# Restore database
gunzip -c /backups/alerts/alerts_backup_20240120_020000.sql.gz | psql -h localhost -U alerts_user -d alerts_db
```

### Application Backup

```python
# management/commands/backup_data.py
from django.core.management.base import BaseCommand
import json
import os
from datetime import datetime

class Command(BaseCommand):
    help = 'Backup alerts data to JSON files'
    
    def add_arguments(self, parser):
        parser.add_argument('--output-dir', type=str, default='/backups/alerts')
        parser.add_argument('--models', nargs='+', default=['all'])
    
    def handle(self, *args, **options):
        output_dir = options['output_dir']
        models = options['models']
        
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for model in models:
            if model == 'all':
                # Backup all models
                pass
            else:
                # Backup specific model
                pass
```

## Troubleshooting

### Common Issues

#### Database Connection Errors

```bash
# Check database status
sudo systemctl status postgresql

# Check logs
sudo tail -f /var/log/postgresql/postgresql.log

# Test connection
psql -h localhost -U alerts_user -d alerts_db
```

#### Redis Connection Errors

```bash
# Check Redis status
sudo systemctl status redis-server

# Test connection
redis-cli ping

# Check logs
sudo tail -f /var/log/redis/redis.log
```

#### Application Errors

```bash
# Check application logs
sudo journalctl -u www-data -f
sudo tail -f /var/log/alerts/alerts.log

# Check Celery logs
tail -f /var/log/celery/worker.log
```

#### Performance Issues

```bash
# Check system resources
top
htop
free -h
df -h

# Check database queries
sudo -u postgres psql -d alerts_db -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10"
```

### Health Check Script

```bash
#!/bin/bash
# health_check.sh

echo "=== Alerts API Health Check ==="

# Check web service
if curl -f http://localhost:8000/api/alerts/health/ > /dev/null; then
    echo "Web service: OK"
else
    echo "Web service: FAILED"
fi

# Check database
if sudo -u postgres psql -c "SELECT 1" alerts_db > /dev/null 2>&1; then
    echo "Database: OK"
else
    echo "Database: FAILED"
fi

# Check Redis
if redis-cli ping > /dev/null 2>&1; then
    echo "Redis: OK"
else
    echo "Redis: FAILED"
fi

# Check Celery
if celery -A alerts inspect ping > /dev/null 2>&1; then
    echo "Celery: OK"
else
    echo "Celery: FAILED"
fi

echo "Health check completed"
```

## Maintenance

### Regular Maintenance Tasks

1. **Daily**
   - Check system health
   - Review error logs
   - Monitor performance metrics
   - Check disk space

2. **Weekly**
   - Update packages
   - Review security logs
   - Optimize database
   - Clean up old logs

3. **Monthly**
   - Update dependencies
   - Security audit
   - Performance tuning
   - Backup verification

### Update Process

```bash
# Update application
git pull origin main
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart alerts-api
sudo systemctl restart alerts-worker alerts-beat
```

### Scaling Guidelines

#### Horizontal Scaling

```yaml
# docker-compose.yml
services:
  web:
    image: alerts-api:latest
    deploy:
      replicas: 5
    depends_on:
      - db
      - redis
  
  worker:
    image: alerts-api:latest
    deploy:
      replicas: 4
    depends_on:
      - db
      - redis
```

#### Database Scaling

```sql
-- Add read replicas for read-heavy workloads
CREATE DATABASE alerts_readonly;
ALTER DATABASE alerts_readonly OWNER TO alerts_user;
```

This deployment guide provides comprehensive information for deploying the Alerts API in various environments with best practices for security, performance, and maintainability.
