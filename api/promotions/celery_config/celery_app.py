# =============================================================================
# promotions/celery_config/celery_app.py
# Celery App Configuration
# =============================================================================
import os
from celery import Celery

# Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('promotions_platform')

# Use Django settings for Celery config
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Celery config
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,    # 5 minutes soft limit
    task_time_limit=600,         # 10 minutes hard limit
    result_expires=3600,
    beat_scheduler='django_celery_beat.schedulers:DatabaseScheduler',
)

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
