# Deployment Guide

This guide provides comprehensive instructions for deploying the Tenant Management System in various environments.

## Prerequisites

### System Requirements
- Python 3.8+
- Django 4.0+
- PostgreSQL 12+
- Redis 6+
- Celery 5+
- Nginx (for production)

### Dependencies
```bash
pip install django djangorestframework celery redis psycopg2-binary
pip install django-cors-headers django-filter django-extensions
pip install cryptography python-dateutil
```

## Environment Configuration

### Development Environment

1. **Clone the repository**
```bash
git clone <repository-url>
cd tenant-management
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. **Database setup**
```bash
# Create database
createdb tenant_management

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

6. **Load initial data**
```bash
python manage.py loaddata fixtures/initial_data.json
```

### Production Environment

#### 1. Server Setup

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install python3 python3-pip python3-venv postgresql postgresql-contrib redis-server nginx -y

# Create application user
sudo useradd -m -s /bin/bash tenantapp
sudo usermod -aG sudo tenantapp
```

#### 2. Application Deployment

```bash
# Switch to application user
sudo su - tenantapp

# Clone repository
git clone <repository-url> tenant-management
cd tenant-management

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn
```

#### 3. Database Configuration

```bash
# Switch to postgres user
sudo su - postgres

# Create database and user
createdb tenant_management
createuser tenantapp
psql -c "ALTER USER tenantapp PASSWORD 'secure_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE tenant_management TO tenantapp;"

# Exit postgres user
exit
```

#### 4. Environment Configuration

Create `.env` file:
```bash
# Security
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DB_NAME=tenant_management
DB_USER=tenantapp
DB_PASSWORD=secure_password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Tenant Settings
TENANTS_DEFAULT_PLAN=basic
TENANTS_TRIAL_DAYS=14
TENANTS_MAX_TENANTS_PER_USER=10

# File Storage
MEDIA_ROOT=/home/tenantapp/tenant-management/media
STATIC_ROOT=/home/tenantapp/tenant-management/static
```

#### 5. Application Configuration

Update `settings.py` for production:
```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.getenv('STATIC_ROOT')
MEDIA_URL = '/media/'
MEDIA_ROOT = os.getenv('MEDIA_ROOT')

# Email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = os.getenv('EMAIL_PORT')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL')

# Celery
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/tenant-management/django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}
```

#### 6. Run Migrations

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## Service Configuration

### Gunicorn Service

Create `/etc/systemd/system/tenant-management.service`:
```ini
[Unit]
Description=tenant-management Django Application
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=tenantapp
Group=tenantapp
WorkingDirectory=/home/tenantapp/tenant-management
Environment=PATH=/home/tenantapp/tenant-management/venv/bin
ExecStart=/home/tenantapp/tenant-management/venv/bin/gunicorn --workers 3 --timeout 120 --bind unix:/run/tenant-management.sock tenant_management.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Celery Worker Service

Create `/etc/systemd/system/tenant-management-worker.service`:
```ini
[Unit]
Description=tenant-management Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=forking
User=tenantapp
Group=tenantapp
WorkingDirectory=/home/tenantapp/tenant-management
Environment=PATH=/home/tenantapp/tenant-management/venv/bin
ExecStart=/home/tenantapp/tenant-management/venv/bin/celery -A tenant_management worker --loglevel=INFO
ExecStop=/bin/kill -s TERM $MAINPID
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Celery Beat Service

Create `/etc/systemd/system/tenant-management-beat.service`:
```ini
[Unit]
Description=tenant-management Celery Beat
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=tenantapp
Group=tenantapp
WorkingDirectory=/home/tenantapp/tenant-management
Environment=PATH=/home/tenantapp/tenant-management/venv/bin
ExecStart=/home/tenantapp/tenant-management/venv/bin/celery -A tenant_management beat --loglevel=INFO
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Enable Services

```bash
sudo systemctl daemon-reload
sudo systemctl enable tenant-management
sudo systemctl enable tenant-management-worker
sudo systemctl enable tenant-management-beat

sudo systemctl start tenant-management
sudo systemctl start tenant-management-worker
sudo systemctl start tenant-management-beat
```

## Nginx Configuration

Create `/etc/nginx/sites-available/tenant-management`:
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /path/to/ssl/fullchain.pem;
    ssl_certificate_key /path/to/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    client_max_body_size 100M;

    location /static/ {
        alias /home/tenantapp/tenant-management/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /home/tenantapp/tenant-management/media/;
        expires 1y;
        add_header Cache-Control "public";
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/tenant-management.sock;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
        proxy_redirect off;
    }

    location /api/ {
        include proxy_params;
        proxy_pass http://unix:/run/tenant-management.sock;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $host;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/tenant-management /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## SSL Configuration

### Let's Encrypt (Recommended)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Set up auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### Custom SSL

Place your SSL certificates in `/etc/ssl/certs/` and update the Nginx configuration accordingly.

## Monitoring and Logging

### Log Rotation

Create `/etc/logrotate.d/tenant-management`:
```
/var/log/tenant-management/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 tenantapp tenantapp
    postrotate
        systemctl reload tenant-management
    endscript
}
```

### Health Checks

Create health check endpoint in `views.py`:
```python
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import redis

def health_check(request):
    checks = {
        'database': 'ok',
        'redis': 'ok',
        'cache': 'ok'
    }
    
    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        checks['database'] = 'error'
    
    # Check Redis
    try:
        r = redis.from_url('redis://localhost:6379/0')
        r.ping()
    except Exception:
        checks['redis'] = 'error'
    
    # Check cache
    try:
        cache.set('health_check', 'ok', 10)
        cache.get('health_check')
    except Exception:
        checks['cache'] = 'error'
    
    status = 200 if all(check == 'ok' for check in checks.values()) else 503
    
    return JsonResponse({
        'status': 'ok' if status == 200 else 'error',
        'checks': checks
    }, status=status)
```

Add to `urls.py`:
```python
from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    # ... other urls
]
```

## Performance Optimization

### Database Optimization

1. **Connection Pooling**
```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
        'OPTIONS': {
            'MAX_CONNS': 20,
            'MIN_CONNS': 5,
        }
    }
}
```

2. **Database Indexes**
```python
# models.py
class Tenant(models.Model):
    # ... fields
    
    class Meta:
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['admin_email']),
        ]
```

### Caching

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Cache middleware
MIDDLEWARE = [
    'django.middleware.cache.UpdateCacheMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.cache.FetchFromCacheMiddleware',
    # ... other middleware
]

CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 600
CACHE_MIDDLEWARE_KEY_PREFIX = 'tenant_management'
```

## Security Hardening

### Django Security Settings

```python
# settings.py
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_HSTS_SECONDS = 31536000
SECURE_REDIRECT_EXEMPT = []
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'
```

### Firewall Configuration

```bash
# UFW configuration
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw deny 5432  # PostgreSQL
sudo ufw deny 6379  # Redis
sudo ufw enable
```

## Backup Strategy

### Database Backup

Create backup script `/home/tenantapp/backup-db.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/home/tenantapp/backups"
DB_NAME="tenant_management"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
pg_dump -h localhost -U tenantapp $DB_NAME > $BACKUP_DIR/backup_$DATE.sql

# Compress backup
gzip $BACKUP_DIR/backup_$DATE.sql

# Remove old backups (keep last 30 days)
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: backup_$DATE.sql.gz"
```

Add to crontab:
```bash
# Daily backup at 2 AM
0 2 * * * /home/tenantapp/backup-db.sh
```

### File Backup

```bash
# Backup media files
rsync -av /home/tenantapp/tenant-management/media/ /backup/media/

# Backup static files
rsync -av /home/tenantapp/tenant-management/static/ /backup/static/
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check PostgreSQL service status
   - Verify database credentials
   - Check firewall rules

2. **Celery Tasks Not Running**
   - Check Redis service status
   - Verify Celery worker logs
   - Check broker connection

3. **Static Files Not Loading**
   - Run `collectstatic` command
   - Check Nginx configuration
   - Verify file permissions

4. **SSL Certificate Issues**
   - Check certificate expiration
   - Verify certificate path
   - Test SSL configuration

### Log Analysis

```bash
# Check application logs
sudo journalctl -u tenant-management -f

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log

# Check Celery logs
sudo journalctl -u tenant-management-worker -f
```

### Performance Monitoring

```bash
# Monitor system resources
htop
iotop
nethogs

# Check database connections
psql -U tenantapp -d tenant_management -c "SELECT count(*) FROM pg_stat_activity;"

# Monitor Redis
redis-cli info memory
redis-cli info stats
```

## Scaling Considerations

### Horizontal Scaling

1. **Load Balancer Setup**
   - Configure multiple application servers
   - Use Nginx as load balancer
   - Implement health checks

2. **Database Replication**
   - Set up read replicas
   - Configure Django for multiple databases
   - Implement connection routing

3. **Cache Clustering**
   - Set up Redis cluster
   - Configure cache partitioning
   - Implement cache warming

### Vertical Scaling

1. **Resource Allocation**
   - Increase CPU cores
   - Add more RAM
   - Use faster storage (SSD)

2. **Application Optimization**
   - Profile application performance
   - Optimize database queries
   - Implement caching strategies

## Maintenance

### Regular Maintenance Tasks

1. **Weekly**
   - Check system logs
   - Monitor disk usage
   - Update security patches

2. **Monthly**
   - Database maintenance
   - Log rotation
   - Performance analysis

3. **Quarterly**
   - Security audit
   - Backup verification
   - Capacity planning

### Update Process

1. **Application Updates**
```bash
# Backup current version
cp -r /home/tenantapp/tenant-management /home/tenantapp/tenant-management.backup

# Update code
cd /home/tenantapp/tenant-management
git pull origin main

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart services
sudo systemctl restart tenant-management tenant-management-worker tenant-management-beat
```

2. **System Updates**
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Reboot if necessary
sudo reboot
```

This deployment guide provides comprehensive instructions for deploying the Tenant Management System in production environments with proper security, monitoring, and maintenance procedures.
