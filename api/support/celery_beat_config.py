# api/support/celery_beat_config.py
"""
Add to settings.py:
    from api.support.celery_beat_config import SUPPORT_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE.update(SUPPORT_BEAT_SCHEDULE)
"""
SUPPORT_BEAT_SCHEDULE = {
    'support-sla-check':      {'task': 'support.tasks.check_sla_breaches',          'schedule': 900},
    'support-auto-close':     {'task': 'support.tasks.auto_close_stale_tickets',     'schedule': 86400},
    'support-daily-digest':   {'task': 'support.tasks.send_daily_digest',            'schedule': 86400},
    'support-auto-assign':    {'task': 'support.tasks.assign_unassigned_tickets',    'schedule': 600},
    'support-kb-suggest':     {'task': 'support.tasks.suggest_kb_for_new_tickets',   'schedule': 300},
    'support-cap-auto-approve':{'task': 'support.tasks_cap.auto_approve_eligible_disputes', 'schedule': 3600},
    'support-cap-fraud':      {'task': 'support.tasks_cap.flag_suspicious_patterns', 'schedule': 86400},
}