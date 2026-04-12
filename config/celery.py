import os
from celery import Celery
from celery.schedules import crontab

# সেটিংস পাথ আপডেট করুন
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')

app = Celery('earning_backend') # আপনার প্রজেক্টের নাম দিন
from .celery_schedule import CELERY_BEAT_SCHEDULE
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Load task schedules
app.conf.beat_schedule = CELERY_BEAT_SCHEDULE

# config/celery.py


app.conf.beat_schedule = {
    # ... অন্যান্য টাস্ক ...
    
    # প্রতি রবিবার রাত ২টায় পুরনো ব্যাকআপ ক্লিনআপ
    'cleanup-old-backups-weekly': {
        'task': 'api.tasks.backup_tasks.cleanup_old_backups_task',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),  # রবিবার
        'args': (30,),  # ৩০ দিনের পুরনো ব্যাকআপ রাখুন
    },
    
    # প্রতিদিন সকাল ৬টায় ব্যাকআপ ভেরিফিকেশন
    'verify-backups-daily': {
        'task': 'api.tasks.backup_tasks.verify_backups_task', 
        'schedule': crontab(hour=6, minute=0),  # প্রতিদিন
        'args': (),
    },
}

# Django settings module set করো
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')

app = Celery('your_project')


# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')