"""
tasks/management/commands/monitor_queue_depth.py
Monitor and display real-time queue depths from CLI.

Usage:
  python manage.py monitor_queue_depth
  python manage.py monitor_queue_depth --queue default --watch
  python manage.py monitor_queue_depth --snapshot
  python manage.py monitor_queue_depth --alert-threshold 100
"""
import time
import sys
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Monitor Celery queue depths'

    def add_arguments(self, parser):
        parser.add_argument('--queue',           type=str, help='Filter by specific queue name')
        parser.add_argument('--watch',           action='store_true', help='Continuously refresh every N seconds')
        parser.add_argument('--interval',        type=int, default=5, help='Watch interval in seconds (default 5)')
        parser.add_argument('--snapshot',        action='store_true', help='Save a depth snapshot to DB')
        parser.add_argument('--alert-threshold', type=int, default=0,
                            help='Exit with code 1 if any queue depth exceeds this value')
        parser.add_argument('--history',         type=str, help='Show historical depths for a queue name')
        parser.add_argument('--history-hours',   type=int, default=6, help='Hours of history to show (default 6)')

    def handle(self, *args, **options):
        from api.tasks.services.QueueDepthService import QueueDepthService

        svc = QueueDepthService()

        # ── Historical mode ───────────────────────────────────────────
        if options.get('history'):
            self._show_history(svc, options['history'], options['history_hours'])
            return

        # ── Snapshot mode ─────────────────────────────────────────────
        if options['snapshot']:
            self.stdout.write('Taking queue depth snapshot...')
            snapshots = svc.snapshot_all()
            self.stdout.write(self.style.SUCCESS(f'[OK] Saved {len(snapshots)} snapshots.'))
            self._print_depths(snapshots)
            return

        # ── Watch mode ────────────────────────────────────────────────
        if options['watch']:
            interval  = options['interval']
            threshold = options['alert_threshold']
            queue_f   = options.get('queue')

            self.stdout.write(
                f'Watching queue depths every {interval}s... (Ctrl+C to stop)\n'
            )
            try:
                while True:
                    depths = svc.get_all_depths()
                    if queue_f:
                        depths = [d for d in depths if d['queue_name'] == queue_f]

                    self.stdout.write(
                        f'\n[{timezone.now().strftime("%H:%M:%S")}]'
                    )
                    self._print_depths(depths)

                    if threshold:
                        for d in depths:
                            if d.get('depth', 0) > threshold:
                                self.stderr.write(self.style.ERROR(
                                    f'ALERT: Queue {d["queue_name"]} depth={d["depth"]} '
                                    f'exceeds threshold {threshold}'
                                ))

                    time.sleep(interval)

            except KeyboardInterrupt:
                self.stdout.write('\nStopped.')
            return

        # ── Single check ──────────────────────────────────────────────
        queue_f = options.get('queue')

        if queue_f:
            depths = [svc.get_queue_depth(queue_f)]
        else:
            depths = svc.get_all_depths()

        self.stdout.write(f'\nQueue Depths @ {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}')
        self.stdout.write('-' * 60)
        self._print_depths(depths)

        # ── Alert threshold ───────────────────────────────────────────
        threshold = options['alert_threshold']
        if threshold:
            exceeded = [d for d in depths if d.get('depth', 0) > threshold]
            if exceeded:
                self.stderr.write(self.style.ERROR(
                    f'\n[ALERT] {len(exceeded)} queue(s) exceed threshold {threshold}.'
                ))
                sys.exit(1)

    def _print_depths(self, depths):
        for d in depths:
            queue  = d.get('queue_name', 'unknown')
            depth  = d.get('depth', 0)
            proc   = d.get('processing_count', 0)
            failed = d.get('failed_count', 0)

            color = (
                self.style.ERROR   if depth > 500
                else self.style.WARNING if depth > 100
                else self.style.SUCCESS
            )
            self.stdout.write(color(
                f'  {queue:<40}  depth={depth:<6}  proc={proc:<4}  failed={failed}'
            ))

    def _show_history(self, svc, queue_name: str, hours: int):
        records = svc.get_historical(queue_name, hours=hours)
        if not records:
            self.stdout.write(self.style.WARNING(f'No history found for queue: {queue_name}'))
            return

        self.stdout.write(f'\nHistory for queue "{queue_name}" (last {hours}h):')
        self.stdout.write('-' * 60)
        for r in records[-30:]:  # last 30 records
            self.stdout.write(
                f"  {r['checked_at']}  depth={r['depth']:<6}  "
                f"proc={r['processing_count']:<4}  failed={r['failed_count']}"
            )
