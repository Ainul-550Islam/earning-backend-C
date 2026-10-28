import logging
import datetime
from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model

logger = logging.getLogger('smartlink.tasks.reports')
User = get_user_model()


# REMOVED: duplicate task @shared_task(name='smartlink.report_tasks.send_daily_publisher', queue='email') — canonical definition in billing_tasks.py / cap_reset_tasks.py

# REMOVED: duplicate task @shared_task(name='smartlink.report_tasks.send_weekly_publisher', queue='email') — canonical definition in billing_tasks.py / cap_reset_tasks.py

# REMOVED: duplicate task @shared_task(name='smartlink.report_tasks.alert_cap_nearly_reached', queue='email') — canonical definition in billing_tasks.py / cap_reset_tasks.py

