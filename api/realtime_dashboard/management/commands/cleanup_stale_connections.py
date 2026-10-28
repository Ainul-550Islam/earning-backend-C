"""
Management command: cleanup_stale_connections

Marks WebSocketConnection rows whose last_ping is older than
--timeout-seconds as disconnected.

This is the manual/cron alternative to the Celery beat task of the
same name. Use it when Celery is not available (local dev, CI, one-off
production maintenance) or to run cleanup immediately without waiting
for the next beat interval.

Usage:
    # Default 1-hour timeout
    python manage.py cleanup_stale_connections

    # Custom timeout
    python manage.py cleanup_stale_connections --timeout-seconds 1800

    # Dry run — shows count without updating DB
    python manage.py cleanup_stale_connections --dry-run

OWNERSHIP: This command is the sole owner of the "trigger stale-connection
cleanup" action at the management-command level. It delegates to
WebSocketManagerService.cleanup_old_connections() — it does NOT call
WebSocketManager or the ORM directly.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Mark WebSocket connections silent for longer than --timeout-seconds as disconnected.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout-seconds',
            type=int,
            default=3600,
            metavar='SECONDS',
            help='Connections silent for longer than this are considered stale (default: 3600).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Show how many connections would be cleaned without updating the DB.',
        )

    def handle(self, *args, **options):
        timeout = options['timeout_seconds']
        dry_run = options['dry_run']

        if dry_run:
            from django.utils import timezone
            from datetime import timedelta
            from ...models.websocket_connection import WebSocketConnection

            cutoff = timezone.now() - timedelta(seconds=timeout)
            count = WebSocketConnection.objects.filter(
                last_ping__lt=cutoff,
                status='connected',
            ).count()
            self.stdout.write(
                self.style.WARNING(
                    f'[dry-run] {count} connection(s) would be marked disconnected '
                    f'(timeout={timeout}s).'
                )
            )
            return

        from ...services.websocket_manager_service import WebSocketManagerService
        count = WebSocketManagerService().cleanup_old_connections(timeout)

        msg = f'Marked {count} stale connection(s) as disconnected (timeout={timeout}s).'
        if count > 0:
            self.stdout.write(self.style.SUCCESS(msg))
        else:
            self.stdout.write(msg)
