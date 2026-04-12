from django.core.management.base import BaseCommand
import logging
logger = logging.getLogger('management.health')

class Command(BaseCommand):
    help = 'Check system health — DB, Redis, Celery, external services'

    def handle(self, *args, **options):
        from api.promotions.optimization.performance_monitor import HealthChecker
        from api.promotions.monitoring.uptime_checker import UptimeChecker
        from api.promotions.monitoring.alert_system import AlertSystem, AlertSeverity

        health   = HealthChecker().check_all()
        uptime   = UptimeChecker().check_all()
        failures = [k for k, v in health.items() if not v.get('healthy', True)]
        down     = [s.name for s in uptime if not s.is_up]

        if failures or down:
            AlertSystem().send_system_alert(
                'System Health', f'Failures: {failures} Down: {down}', AlertSeverity.CRITICAL
            )
            self.stdout.write(self.style.ERROR(f'UNHEALTHY: {failures} | DOWN: {down}'))
        else:
            self.stdout.write(self.style.SUCCESS('All systems healthy'))
