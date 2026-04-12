"""
DR Integration Settings — Add these to your Django settings.py
"""
# ── Add to INSTALLED_APPS ─────────────────────────────────────────────────────
# INSTALLED_APPS = [
#     ...
#     'dr_integration',
#     ...
# ]

# ── Add to urls.py ────────────────────────────────────────────────────────────
# path('api/dr/', include('dr_integration.urls')),

# ── DR System Path ────────────────────────────────────────────────────────────
import os
DR_SYSTEM_PATH = os.environ.get('DR_SYSTEM_PATH', '/app/disaster_recovery')

# ── DR Notification Config (Slack, PagerDuty, Datadog) ───────────────────────
DR_NOTIFICATION_CONFIG = {
    'slack_webhook_url': os.environ.get('DR_SLACK_WEBHOOK_URL', ''),
    'pagerduty_api_key': os.environ.get('DR_PAGERDUTY_API_KEY', ''),
    'pagerduty_integration_key': os.environ.get('DR_PAGERDUTY_INTEGRATION_KEY', ''),
    'datadog_api_key': os.environ.get('DR_DATADOG_API_KEY', ''),
    'critical_channel_url': os.environ.get('DR_SLACK_CRITICAL_CHANNEL_URL', ''),
    'ops_channel_url': os.environ.get('DR_SLACK_OPS_CHANNEL_URL', ''),
}

# ── DR Audit Config ───────────────────────────────────────────────────────────
DR_AUDIT_CONFIG = {
    'log_file': '/var/log/api/dr_audit.jsonl',
    'security_log_file': '/var/log/api/dr_security_audit.jsonl',
}

# ── DR Storage Configs ────────────────────────────────────────────────────────
DR_STORAGE_CONFIGS = [
    {'name': 'local', 'provider': 'local', 'base_path': '/var/backups/api'},
    {
        'name': 's3-backups',
        'provider': 'aws_s3',
        'bucket': os.environ.get('BACKUP_S3_BUCKET', 'api-backups'),
        'region': os.environ.get('AWS_REGION', 'us-east-1'),
        'access_key_id': os.environ.get('AWS_ACCESS_KEY_ID', ''),
        'secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
    },
]

# ── DR Prometheus Config ──────────────────────────────────────────────────────
DR_PROMETHEUS_CONFIG = {
    'port': int(os.environ.get('DR_PROMETHEUS_PORT', '9091')),
    'push_gateway_url': os.environ.get('DR_PROMETHEUS_PUSH_GATEWAY', ''),
}

# ── DR Health Check Components ────────────────────────────────────────────────
DR_HEALTH_CHECK_COMPONENTS = [
    {'name': 'database', 'type': 'database', 'url': 'postgresql://localhost:5432/apidb'},
    {'name': 'redis', 'type': 'tcp', 'host': 'localhost', 'port': 6379},
    {'name': 'api', 'type': 'http', 'url': 'http://localhost:8000/health/', 'timeout': 5},
    {'name': 'celery', 'type': 'tcp', 'host': 'localhost', 'port': 6379},
]

# ── DR Replica Hosts (for replication monitoring) ─────────────────────────────
DR_REPLICA_HOSTS = os.environ.get('DR_REPLICA_HOSTS', '').split(',') or []

# ── DR On-Call Roster ─────────────────────────────────────────────────────────
DR_ON_CALL_ROSTER = [
    {
        'name': os.environ.get('ON_CALL_PRIMARY_NAME', 'Primary On-Call'),
        'email': os.environ.get('ON_CALL_PRIMARY_EMAIL', ''),
        'phone': os.environ.get('ON_CALL_PRIMARY_PHONE', ''),
        'slack_id': os.environ.get('ON_CALL_PRIMARY_SLACK', ''),
        'team': 'Platform',
    }
]

# ── DR Status Page Config ─────────────────────────────────────────────────────
DR_STATUS_PAGE_CONFIG = {
    'company_name': 'API Platform',
    'status_page_url': os.environ.get('STATUS_PAGE_URL', 'https://status.yourapp.com'),
}

DR_STATUS_PAGE_COMPONENTS = [
    {'name': 'api', 'display_name': 'API Server', 'group': 'Application'},
    {'name': 'database', 'display_name': 'Database', 'group': 'Infrastructure'},
    {'name': 'offerwall', 'display_name': 'Offerwall', 'group': 'Application'},
    {'name': 'payment_gateway', 'display_name': 'Payment Gateway', 'group': 'External'},
    {'name': 'marketplace', 'display_name': 'Marketplace', 'group': 'Application'},
    {'name': 'ai_engine', 'display_name': 'AI Engine', 'group': 'Application'},
]

# ── DR Key Config ─────────────────────────────────────────────────────────────
DR_KEY_CONFIG = {
    'key_store_path': '/etc/api/dr_keys',
    'rotation_days': 90,
    'kms_provider': os.environ.get('DR_KMS_PROVIDER', 'local'),
}

# ── Celery Beat Schedule (add to CELERY_BEAT_SCHEDULE) ───────────────────────
DR_CELERY_BEAT_SCHEDULE = {
    'dr-incremental-backup-every-4h': {
        'task': 'dr_integration.auto_backup',
        'schedule': 4 * 60 * 60,  # Every 4 hours
        'kwargs': {'backup_type': 'incremental'},
    },
    'dr-full-backup-weekly': {
        'task': 'dr_integration.auto_backup',
        'schedule': 7 * 24 * 60 * 60,  # Weekly
        'kwargs': {'backup_type': 'full'},
    },
    'dr-sync-status-every-5m': {
        'task': 'dr_integration.sync_dr_status',
        'schedule': 5 * 60,
    },
    'dr-verify-backups-daily': {
        'task': 'dr_integration.verify_recent_backups',
        'schedule': 24 * 60 * 60,
    },
    'dr-health-check-every-2m': {
        'task': 'dr_integration.health_check',
        'schedule': 2 * 60,
    },
    'dr-collect-metrics-every-1m': {
        'task': 'dr_integration.collect_and_push_metrics',
        'schedule': 60,
    },
    'dr-key-rotation-check-daily': {
        'task': 'dr_integration.check_key_rotation',
        'schedule': 24 * 60 * 60,
    },
    'dr-cleanup-alerts-weekly': {
        'task': 'dr_integration.cleanup_old_dr_alerts',
        'schedule': 7 * 24 * 60 * 60,
    },
}
