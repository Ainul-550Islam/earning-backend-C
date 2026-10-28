import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")

app = Celery("earning_backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Extras are merged with update(); "=" would replace the settings schedule.
from api.telemetry_observability.celery_schedule import TELEMETRY_BEAT_SCHEDULE  # noqa: E402

app.conf.beat_schedule.update(TELEMETRY_BEAT_SCHEDULE)
