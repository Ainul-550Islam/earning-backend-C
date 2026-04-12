"""Alert Configuration model helpers."""
from django.db import models
from django.utils import timezone
from datetime import timedelta


class AlertConfigurationManager(models.Manager):
    def active(self, tenant=None):
        qs = self.filter(is_active=True)
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def for_trigger(self, trigger: str, tenant=None):
        return self.active(tenant).filter(trigger=trigger)

    def ready_to_send(self, trigger: str, tenant=None):
        """Return configs not in their cooldown period."""
        configs = self.for_trigger(trigger, tenant)
        ready = []
        for cfg in configs:
            if cfg.last_sent is None:
                ready.append(cfg)
            else:
                cooldown_end = cfg.last_sent + timedelta(minutes=cfg.cooldown_minutes)
                if timezone.now() >= cooldown_end:
                    ready.append(cfg)
        return ready

    def above_threshold(self, trigger: str, score: int, tenant=None):
        return self.for_trigger(trigger, tenant).filter(threshold_score__lte=score)

    def mark_sent(self, config_id):
        self.filter(pk=config_id).update(last_sent=timezone.now())

    def by_channel(self, channel: str, tenant=None):
        return self.active(tenant).filter(channel=channel)

    def webhook_configs(self, tenant=None):
        return self.active(tenant).filter(channel='webhook').exclude(webhook_url='')

    def stats(self, tenant=None) -> dict:
        from django.db.models import Count
        qs = self.active(tenant)
        return {
            'total_active':   qs.count(),
            'by_trigger':     list(qs.values('trigger').annotate(n=Count('id'))),
            'by_channel':     list(qs.values('channel').annotate(n=Count('id'))),
            'webhook_count':  qs.filter(channel='webhook').count(),
            'email_count':    qs.filter(channel='email').count(),
        }
