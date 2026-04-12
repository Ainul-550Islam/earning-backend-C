# Alerts API Troubleshooting Guide

## Overview

This guide provides comprehensive troubleshooting information for common issues, errors, and problems that may occur with the Alerts API.

## Quick Reference

### Common Issues
- [Database Connection Issues](#database-connection-issues)
- [Celery Task Issues](#celery-task-issues)
- [Performance Problems](#performance-problems)
- [Authentication Issues](#authentication-issues)
- [Notification Failures](#notification-failures)
- [Memory Issues](#memory-issues)
- [API Errors](#api-errors)

### Health Check Commands
```bash
# Check API health
curl http://localhost:8000/api/alerts/health/

# Check database connection
python manage.py dbshell

# Check Celery status
celery -A alerts inspect ping

# Check Redis connection
redis-cli ping
```

## Database Connection Issues

### Symptoms
- Database connection errors
- Slow database queries
- Connection timeouts
- "OperationalError: could not connect to server"

### Common Causes
1. **Database server down**
2. **Incorrect connection parameters**
3. **Network connectivity issues**
4. **Database permission issues**
5. **Connection pool exhaustion**

### Troubleshooting Steps

#### 1. Check Database Server Status
```bash
# PostgreSQL
sudo systemctl status postgresql
sudo systemctl start postgresql

# Check if PostgreSQL is listening
sudo netstat -tlnp | grep :5432

# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql.log
```

#### 2. Test Database Connection
```bash
# Test connection manually
psql -h localhost -U alerts_user -d alerts_db

# Test from Python
python manage.py dbshell
```

#### 3. Verify Connection Settings
```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'alerts_db',
        'USER': 'alerts_user',
        'PASSWORD': 'correct_password',
        'HOST': 'localhost',
        'PORT': '5432',
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}
```

#### 4. Check Connection Limits
```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity;

-- Check connection limits
SHOW max_connections;
```

#### 5. Optimize Connection Pool
```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'alerts_db',
        'USER': 'alerts_user',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
        'CONN_MAX_AGE': 60,  # Persistent connections
        'OPTIONS': {
            'MAX_CONNS': 20,
        }
    }
}
```

### Solutions

#### Solution 1: Restart Database
```bash
sudo systemctl restart postgresql
```

#### Solution 2: Check Network Connectivity
```bash
# Test network connectivity
telnet localhost 5432
nc -zv localhost 5432
```

#### Solution 3: Fix Connection Parameters
```bash
# Update .env file
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=alerts_db
DATABASE_USER=alerts_user
DATABASE_PASSWORD=correct_password
```

#### Solution 4: Increase Connection Limits
```sql
-- In postgresql.conf
max_connections = 200

-- Reload configuration
SELECT pg_reload_conf();
```

## Celery Task Issues

### Symptoms
- Tasks not executing
- Tasks stuck in pending state
- Worker crashes
- Memory leaks in workers
- Tasks failing silently

### Common Causes
1. **Redis connection issues**
2. **Celery worker not running**
3. **Task configuration errors**
4. **Memory exhaustion**
5. **Task dependencies not met**

### Troubleshooting Steps

#### 1. Check Celery Worker Status
```bash
# Check if workers are running
celery -A alerts inspect ping
celery -A alerts inspect stats
celery -A alerts inspect active

# Check worker logs
tail -f /var/log/celery/worker.log
```

#### 2. Check Redis Connection
```bash
# Test Redis connection
redis-cli ping
redis-cli info

# Check Redis logs
sudo tail -f /var/log/redis/redis.log
```

#### 3. Verify Task Configuration
```python
# settings.py
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
```

#### 4. Check Task Queue
```bash
# Check pending tasks
celery -A alerts inspect reserved
celery -A alerts inspect scheduled

# Clear stuck tasks
celery -A alerts purge
```

#### 5. Monitor Worker Memory
```bash
# Check worker memory usage
ps aux | grep celery
top -p $(pgrep -f celery)
```

### Solutions

#### Solution 1: Restart Celery Workers
```bash
sudo systemctl restart alerts-worker
sudo systemctl restart alerts-beat
```

#### Solution 2: Fix Redis Connection
```bash
# Restart Redis
sudo systemctl restart redis-server

# Check Redis configuration
sudo nano /etc/redis/redis.conf
```

#### Solution 3: Optimize Worker Configuration
```python
# settings.py
CELERY_WORKER_CONCURRENCY = 4
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
```

#### Solution 4: Implement Task Retry Logic
```python
# tasks/core.py
from celery import shared_task
from celery.exceptions import Retry

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_alert(self, alert_id):
    try:
        # Process alert
        pass
    except Exception as exc:
        raise self.retry(exc=exc)
```

## Performance Problems

### Symptoms
- Slow API responses
- High CPU usage
- Memory exhaustion
- Database timeouts
- Slow query execution

### Common Causes
1. **Database query inefficiency**
2. **Missing database indexes**
3. **Memory leaks**
4. **Inefficient code**
5. **High traffic volume**

### Troubleshooting Steps

#### 1. Monitor System Resources
```bash
# CPU and memory usage
top
htop
free -h

# Disk usage
df -h
du -sh /path/to/app

# Network usage
iftop
netstat -i
```

#### 2. Analyze Database Queries
```sql
-- Enable query logging
ALTER SYSTEM SET log_statement = 'all';
SELECT pg_reload_conf();

-- Check slow queries
SELECT query, mean_time, calls, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

#### 3. Profile Application Code
```python
# Add profiling middleware
import cProfile
import pstats
from django.conf import settings

class ProfilingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.DEBUG and 'profile' in request.GET:
            profiler = cProfile.Profile()
            profiler.enable()
            response = self.get_response(request)
            profiler.disable()
            
            stats = pstats.Stats(profiler)
            stats.sort_stats('cumulative')
            
            # Save profiling data
            with open(f'profile_{request.path.replace("/", "_")}.prof', 'w') as f:
                stats.print_stats(stream=f)
            
            return response
        else:
            return self.get_response(request)
```

#### 4. Check API Response Times
```bash
# Test API endpoints
curl -w "@curl-format.txt" http://localhost:8000/api/alerts/rules/

# curl-format.txt
      time_namelookup:  %{time_namelookup}\n
         time_connect:  %{time_connect}\n
      time_appconnect:  %{time_appconnect}\n
     time_pretransfer:  %{time_pretransfer}\n
        time_redirect:  %{time_redirect}\n
   time_starttransfer:  %{time_starttransfer}\n
                      ----------\n
           time_total:  %{time_total}\n
```

#### 5. Monitor Database Performance
```bash
# Check database locks
SELECT blocked_locks.pid AS blocked_pid,
       blocked_activity.usename AS blocked_user,
       blocking_locks.pid AS blocking_pid,
       blocking_activity.usename AS blocking_user,
       blocked_activity.query AS blocked_statement,
       blocking_activity.query AS current_statement_in_blocking_process
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

### Solutions

#### Solution 1: Add Database Indexes
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
        ]
```

#### Solution 2: Optimize Queries
```python
# Before: N+1 queries
alerts = AlertLog.objects.all()
for alert in alerts:
    print(alert.rule.name)  # N+1 queries

# After: Optimized with select_related
alerts = AlertLog.objects.select_related('rule').all()
for alert in alerts:
    print(alert.rule.name)  # Single query
```

#### Solution 3: Implement Caching
```python
# services/cache.py
from django.core.cache import cache

def get_alert_rules():
    cache_key = 'alert_rules_all'
    rules = cache.get(cache_key)
    
    if rules is None:
        rules = list(AlertRule.objects.all())
        cache.set(cache_key, rules, timeout=300)  # 5 minutes
    
    return rules
```

#### Solution 4: Scale Workers
```bash
# Increase worker count
celery -A alerts worker --concurrency=8

# Use gunicorn with multiple workers
gunicorn --workers 4 --worker-class sync alerts.wsgi:application
```

## Authentication Issues

### Symptoms
- 401 Unauthorized errors
- 403 Forbidden errors
- Token authentication failures
- Session authentication issues

### Common Causes
1. **Invalid authentication credentials**
2. **Expired tokens**
3. **Permission misconfiguration**
4. **CSRF token issues**
5. **Session timeout**

### Troubleshooting Steps

#### 1. Check Authentication Configuration
```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
```

#### 2. Verify Token Validity
```bash
# Check token in database
python manage.py shell
>>> from rest_framework.authtoken.models import Token
>>> Token.objects.get(user_id=1)
```

#### 3. Test Authentication
```bash
# Test with token
curl -H "Authorization: Token your-token-here" \
     http://localhost:8000/api/alerts/rules/

# Test with session
curl -c cookies.txt -b cookies.txt \
     http://localhost:8000/api/alerts/rules/
```

#### 4. Check Permissions
```python
# views.py
from rest_framework.permissions import IsAuthenticated

class AlertRuleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
```

### Solutions

#### Solution 1: Generate New Token
```bash
python manage.py shell
>>> from rest_framework.authtoken.models import Token
>>> from django.contrib.auth import get_user_model
>>> user = get_user_model().objects.get(username='youruser')
>>> token = Token.objects.create(user=user)
>>> print(token.key)
```

#### Solution 2: Fix Token Authentication
```python
# settings.py
INSTALLED_APPS = [
    # ...
    'rest_framework.authtoken',
]
```

#### Solution 3: Configure CORS
```python
# settings.py
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://yourdomain.com",
]
CORS_ALLOW_CREDENTIALS = True
```

## Notification Failures

### Symptoms
- Emails not sending
- SMS delivery failures
- Webhook timeouts
- Notification queue buildup

### Common Causes
1. **SMTP configuration errors**
2. **API key issues**
3. **Network connectivity problems**
4. **Rate limiting**
5. **Invalid recipient addresses**

### Troubleshooting Steps

#### 1. Check Email Configuration
```python
# settings.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.example.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'alerts@example.com'
EMAIL_HOST_PASSWORD = 'your-password'
DEFAULT_FROM_EMAIL = 'alerts@example.com'
```

#### 2. Test Email Sending
```python
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test Subject', 'Test Message', 'alerts@example.com', ['test@example.com'])
```

#### 3. Check Notification Logs
```bash
# Check notification logs
grep "notification" /var/log/alerts/alerts.log
tail -f /var/log/alerts/notifications.log
```

#### 4. Verify Webhook Configuration
```bash
# Test webhook endpoint
curl -X POST -H "Content-Type: application/json" \
     -d '{"test": "data"}' \
     https://webhook.example.com/endpoint
```

### Solutions

#### Solution 1: Fix Email Configuration
```python
# Use environment variables
EMAIL_HOST = os.environ.get('EMAIL_HOST')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
```

#### Solution 2: Implement Retry Logic
```python
# services/notification.py
import time
from django.core.mail import send_mail

def send_email_with_retry(subject, message, recipient, max_retries=3):
    for attempt in range(max_retries):
        try:
            send_mail(subject, message, 'alerts@example.com', [recipient])
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
    return False
```

#### Solution 3: Handle Rate Limiting
```python
# services/rate_limit.py
import time
from django.core.cache import cache

def check_rate_limit(key, limit, period):
    cache_key = f'rate_limit:{key}'
    current_count = cache.get(cache_key, 0)
    
    if current_count >= limit:
        return False
    
    cache.set(cache_key, current_count + 1, period)
    return True
```

## Memory Issues

### Symptoms
- Out of memory errors
- Process crashes
- High memory usage
- Slow performance

### Common Causes
1. **Memory leaks**
2. **Large dataset processing**
3. **Inefficient algorithms**
4. **Cache overflow**
5. **Database connection leaks**

### Troubleshooting Steps

#### 1. Monitor Memory Usage
```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head
top

# Check specific process memory
ps -p $(pgrep -f gunicorn) -o pid,ppid,cmd,%mem,%cpu
```

#### 2. Analyze Memory Leaks
```python
# Add memory monitoring
import tracemalloc

tracemalloc.start()

# In your view function
def my_view(request):
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')
    for stat in top_stats[:10]:
        print(stat)
```

#### 3. Check Database Connections
```bash
# Check connection count
ps aux | grep postgres
netstat -an | grep :5432 | wc -l
```

#### 4. Profile Memory Usage
```python
# Use memory_profiler
pip install memory-profiler

@profile
def memory_intensive_function():
    # Your code here
    pass
```

### Solutions

#### Solution 1: Optimize Database Queries
```python
# Use pagination
from django.core.paginator import Paginator

def get_alerts_paginated(page=1, page_size=20):
    alerts = AlertLog.objects.all()
    paginator = Paginator(alerts, page_size)
    return paginator.get_page(page)
```

#### Solution 2: Implement Memory Management
```python
# Use generators for large datasets
def get_alerts_generator():
    offset = 0
    limit = 1000
    
    while True:
        alerts = AlertLog.objects.all()[offset:offset+limit]
        if not alerts:
            break
        for alert in alerts:
            yield alert
        offset += limit
```

#### Solution 3: Configure Connection Pooling
```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'alerts_db',
        'USER': 'alerts_user',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
        'CONN_MAX_AGE': 60,  # Persistent connections
        'OPTIONS': {
            'MAX_CONNS': 20,
        }
    }
}
```

## API Errors

### Common Error Codes
- `400 Bad Request` - Invalid input data
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Permission denied
- `404 Not Found` - Resource not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

### Troubleshooting API Errors

#### 1. Check Request Format
```bash
# Validate JSON
curl -X POST -H "Content-Type: application/json" \
     -d '{"name": "Test", "severity": "high"}' \
     http://localhost:8000/api/alerts/rules/
```

#### 2. Check Response Headers
```bash
# Include headers in response
curl -I http://localhost:8000/api/alerts/rules/
```

#### 3. Debug with Django Debug Toolbar
```python
# settings.py
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
```

#### 4. Check API Logs
```bash
# Check Django logs
tail -f /var/log/alerts/django.log

# Check Nginx logs
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### Solutions

#### Solution 1: Fix Input Validation
```python
# serializers/core.py
class AlertRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertRule
        fields = '__all__'
    
    def validate_threshold_value(self, value):
        if value < 0:
            raise serializers.ValidationError("Threshold value must be positive")
        return value
```

#### Solution 2: Improve Error Messages
```python
# views.py
from rest_framework.response import Response
from rest_framework import status

def create_error_response(message, error_code=None, details=None):
    response_data = {
        'error': message,
        'timestamp': timezone.now().isoformat(),
    }
    
    if error_code:
        response_data['error_code'] = error_code
    
    if details:
        response_data['details'] = details
    
    return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
```

## System Health Monitoring

### Health Check Script
```bash
#!/bin/bash
# health_check.sh

echo "=== Alerts API Health Check ==="
DATE=$(date +%Y-%m-%d %H:%M:%S)

# Check web service
echo "[$DATE] Checking web service..."
if curl -f http://localhost:8000/api/alerts/health/ > /dev/null 2>&1; then
    echo "[$DATE] Web service: OK"
else
    echo "[$DATE] Web service: FAILED"
fi

# Check database
echo "[$DATE] Checking database..."
if sudo -u postgres psql -c "SELECT 1" alerts_db > /dev/null 2>&1; then
    echo "[$DATE] Database: OK"
else
    echo "[$DATE] Database: FAILED"
fi

# Check Redis
echo "[$DATE] Checking Redis..."
if redis-cli ping > /dev/null 2>&1; then
    echo "[$DATE] Redis: OK"
else
    echo "[$DATE] Redis: FAILED"
fi

# Check Celery
echo "[$DATE] Checking Celery..."
if celery -A alerts inspect ping > /dev/null 2>&1; then
    echo "[$DATE] Celery: OK"
else
    echo "[$DATE] Celery: FAILED"
fi

# Check disk space
echo "[$DATE] Checking disk space..."
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -lt 80 ]; then
    echo "[$DATE] Disk space: OK (${DISK_USAGE}%)"
else
    echo "[$DATE] Disk space: WARNING (${DISK_USAGE}%)"
fi

# Check memory
echo "[$DATE] Checking memory..."
MEMORY_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ $MEMORY_USAGE -lt 80 ]; then
    echo "[$DATE] Memory: OK (${MEMORY_USAGE}%)"
else
    echo "[$DATE] Memory: WARNING (${MEMORY_USAGE}%)"
fi

echo "[$DATE] Health check completed"
```

### Log Analysis Script
```bash
#!/bin/bash
# log_analysis.sh

LOG_FILE="/var/log/alerts/alerts.log"
DATE=$(date +%Y-%m-%d)

echo "=== Log Analysis for $DATE ==="

# Count errors
ERROR_COUNT=$(grep -c "ERROR" $LOG_FILE)
echo "Errors today: $ERROR_COUNT"

# Count warnings
WARNING_COUNT=$(grep -c "WARNING" $LOG_FILE)
echo "Warnings today: $WARNING_COUNT"

# Top error messages
echo "Top error messages:"
grep "ERROR" $LOG_FILE | awk '{print $4, $5, $6, $7, $8, $9}' | sort | uniq -c | sort -nr | head -5

# Recent errors
echo "Recent errors (last 10):"
grep "ERROR" $LOG_FILE | tail -10

# Database errors
echo "Database errors:"
grep -i "database\|connection\|sql" $LOG_FILE | grep -i "error\|failed" | tail -5

# API errors
echo "API errors:"
grep "api\|request\|response" $LOG_FILE | grep -i "error\|failed\|exception" | tail -5
```

## Emergency Procedures

### Database Corruption
```bash
# Emergency database recovery
sudo -u postgres pg_dump alerts_db > /tmp/emergency_backup.sql
sudo -u postgres psql -d alerts_db -c "VACUUM FULL"
sudo -u postgres psql -d alerts_db -c "REINDEX DATABASE alerts_db"
```

### Service Recovery
```bash
# Emergency service restart
sudo systemctl restart alerts-api
sudo systemctl restart alerts-worker
sudo systemctl restart alerts-beat
sudo systemctl restart postgresql
sudo systemctl restart redis-server
```

### Data Recovery
```bash
# Restore from backup
gunzip -c /backups/alerts/alerts_backup_20240120_020000.sql.gz | \
sudo -u postgres psql alerts_db

# Verify data integrity
python manage.py check
python manage.py migrate --fake-initial
```

## Contact Support

### When to Contact Support
- System down for more than 15 minutes
- Critical data loss or corruption
- Security breach suspected
- Performance degradation > 50%
- Multiple service failures

### Information to Provide
1. Error messages and logs
2. Time of issue occurrence
3. Steps to reproduce
4. System status at time of issue
5. Recent changes or deployments

### Support Channels
- Email: support@example.com
- Slack: #alerts-support
- Phone: +1-555-ALERTS
- Emergency: +1-555-EMERGENCY

This troubleshooting guide should help resolve most common issues with the Alerts API. For additional assistance, contact the support team with detailed information about the problem.
