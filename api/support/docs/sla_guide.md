# SLA Policy Configuration

## Default Policies
Run `python manage.py seed_sla_policies` to create defaults.

## Customizing
```python
from support.models import SLAPolicy
SLAPolicy.objects.update_or_create(
    priority_level='urgent',
    defaults={'name':'VIP Urgent','first_response_hours':1,'resolution_hours':4,'business_hours_only':False}
)
```

## Business Hours
SLA can pause outside business hours. Configure in `BusinessHours` model per department.

## Holidays
Add holidays in `Holiday` model. SLA won't count holiday hours.

## Celery Schedule
```python
CELERY_BEAT_SCHEDULE["support-sla-check"] = {
    "task": "support.tasks.sla_tasks.check_sla_breaches",
    "schedule": 900,  # every 15 minutes
}
```
