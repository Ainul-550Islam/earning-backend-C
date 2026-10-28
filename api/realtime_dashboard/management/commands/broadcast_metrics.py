"""
Management command: broadcast_metrics

Pushes the current value of active RealTimeMetric rows to all subscribed
WebSocket clients via Django Channels.

This is the manual alternative to the Celery beat task of the same name.
Use it for:
  - Debugging: confirm that WebSocket broadcast plumbing works end-to-end
  - Initial state push: send all current metric values immediately after
    a deployment without waiting for the next beat interval
  - CI smoke tests: verify channel-layer connectivity

Usage:
    # Broadcast all active metrics
    python manage.py broadcast_metrics

    # Broadcast specific metric IDs only
    python manage.py broadcast_metrics --ids 1 2 3

    # Dry run — lists which metrics would be broadcast, sends nothing
    python manage.py broadcast_metrics --dry-run

OWNERSHIP: delegates to EventStreamingService.stream_metric_updates() —
does NOT call WebSocketManager or channel layer directly.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Broadcast current metric values to all subscribed WebSocket clients.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ids',
            nargs='+',
            type=int,
            metavar='ID',
            default=None,
            help='Metric IDs to broadcast. Omit to broadcast all active metrics.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='List which metrics would be broadcast without sending.',
        )

    def handle(self, *args, **options):
        from ...models.real_time_metric import RealTimeMetric
        from ...services.event_streaming_service import EventStreamingService

        metric_ids = options['ids']
        dry_run = options['dry_run']

        if metric_ids:
            qs = RealTimeMetric.objects.filter(id__in=metric_ids)
        else:
            qs = RealTimeMetric.objects.active()

        ids = list(qs.values_list('id', flat=True))
        names = list(qs.values_list('name', flat=True))

        if not ids:
            self.stdout.write(self.style.WARNING('No matching active metrics found.'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[dry-run] Would broadcast {len(ids)} metric(s):'))
            for mid, name in zip(ids, names):
                self.stdout.write(f'  id={mid}  name={name}')
            return

        EventStreamingService().stream_metric_updates(ids)
        self.stdout.write(
            self.style.SUCCESS(f'Broadcast {len(ids)} metric(s) to subscribed WebSocket clients.')
        )
        for mid, name in zip(ids, names):
            self.stdout.write(f'  id={mid}  name={name}')
