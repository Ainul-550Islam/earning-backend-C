# api/admin_panel/management/commands/check_system_health.py
"""
Management command: check system health and report status.
Usage:
  python manage.py check_system_health
  python manage.py check_system_health --json
  python manage.py check_system_health --alert-on-failure
"""
import json
import sys
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Run system health checks and report status of all services.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--json',
            action='store_true',
            default=False,
            help='Output health check result as JSON.',
        )
        parser.add_argument(
            '--alert-on-failure',
            action='store_true',
            default=False,
            help='Send email alert to superadmins if any service is down or degraded.',
        )
        parser.add_argument(
            '--exit-code',
            action='store_true',
            default=False,
            help='Exit with code 1 if health is not "healthy" (useful for CI/CD).',
        )

    def handle(self, *args, **options):
        from api.admin_panel.utils import (
            check_db_connection, check_cache_connection, check_celery_status, get_full_system_health
        )

        self.stdout.write('Running system health checks...\n')

        health = get_full_system_health()
        overall = health['overall']
        checks = health['checks']

        if options['json']:
            self.stdout.write(json.dumps(health, indent=2, default=str))
            if options['exit_code'] and overall != 'healthy':
                sys.exit(1)
            return

        # Pretty print
        status_icons = {
            'healthy': '✅',
            'degraded': '⚠️ ',
            'down': '❌',
            'unknown': '❓',
        }
        overall_color = {
            'healthy': self.style.SUCCESS,
            'degraded': self.style.WARNING,
            'down': self.style.ERROR,
            'unknown': self.style.WARNING,
        }

        self.stdout.write('=' * 50)
        self.stdout.write(f'Overall Status: {status_icons.get(overall, "?")} {overall.upper()}')
        self.stdout.write(f'Checked At:    {health.get("checked_at", "?")}')
        self.stdout.write('=' * 50)
        self.stdout.write('')

        for service, result in checks.items():
            status = result.get('status', 'unknown')
            icon = status_icons.get(status, '❓')
            msg = result.get('error', result.get('latency_ms', ''))
            workers = result.get('workers', '')

            detail = ''
            if msg:
                detail = f' — {msg}'
            if workers:
                detail = f' — {workers} worker(s) active'

            line = f'  {icon} {service:<20} {status.upper()}{detail}'
            style_fn = overall_color.get(status, lambda x: x)
            self.stdout.write(style_fn(line))

        self.stdout.write('')

        # Alert on failure
        if options['alert_on_failure'] and overall in ('down', 'degraded'):
            try:
                from api.admin_panel.services.AdminNotificationService import AdminNotificationService
                AdminNotificationService.notify_system_health_alert(health)
                self.stdout.write(self.style.WARNING('  Alert sent to superadmins.'))
            except Exception as e:
                self.stderr.write(f'  Alert send failed: {e}')

        # Update cache with latest health
        try:
            from django.core.cache import cache
            cache.set('admin_panel:system_health', health, 60)
        except Exception:
            pass

        # Summary
        if overall == 'healthy':
            self.stdout.write(self.style.SUCCESS('All systems operational.'))
        elif overall == 'degraded':
            self.stdout.write(self.style.WARNING('Some services degraded. Investigation recommended.'))
        else:
            self.stdout.write(self.style.ERROR('CRITICAL: One or more services are DOWN.'))

        if options['exit_code'] and overall != 'healthy':
            sys.exit(1)