"""
tasks/management/commands/check_worker_health.py
Check and display Celery worker health from the CLI.

Usage:
  python manage.py check_worker_health
  python manage.py check_worker_health --verbose
  python manage.py check_worker_health --alert-offline
"""
import sys
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Check Celery worker health and display status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose', '-v',
            action='store_true',
            default=False,
            help='Show detailed worker info (queues, concurrency, cpu, memory)',
        )
        parser.add_argument(
            '--alert-offline',
            action='store_true',
            default=False,
            help='Exit with code 1 if any worker is offline',
        )
        parser.add_argument(
            '--min-workers',
            type=int,
            default=1,
            help='Minimum expected number of online workers (default: 1)',
        )
        parser.add_argument(
            '--timeout',
            type=float,
            default=3.0,
            help='Celery inspect timeout in seconds (default: 3.0)',
        )
        parser.add_argument(
            '--update-db',
            action='store_true',
            default=True,
            help='Update WorkerHealth model records (default: True)',
        )

    def handle(self, *args, **options):
        from api.tasks.services.WorkerHealthService import WorkerHealthService

        verbose     = options['verbose']
        alert_off   = options['alert_offline']
        min_workers = options['min_workers']
        timeout     = options['timeout']

        self.stdout.write(f'\n[{timezone.now().strftime("%Y-%m-%d %H:%M:%S")}] Checking worker health...')
        self.stdout.write('-' * 60)

        svc     = WorkerHealthService()
        summary = svc.refresh(timeout=timeout)

        online  = summary.get('online', 0)
        workers = summary.get('workers', [])

        # ── Display summary ───────────────────────────────────────────
        if online == 0:
            self.stderr.write(self.style.ERROR('  ✗ NO WORKERS ONLINE'))
        else:
            self.stdout.write(self.style.SUCCESS(f'  ✓ {online} worker(s) online'))

        # ── Display per-worker info ───────────────────────────────────
        if verbose and workers:
            from api.tasks.models.monitoring import WorkerHealth

            self.stdout.write('')
            all_wh = {
                w['worker_id']: w
                for w in WorkerHealth.objects.values(
                    'worker_id', 'hostname', 'status', 'queue_names',
                    'concurrency', 'active_tasks', 'cpu_percent',
                    'memory_mb', 'last_heartbeat',
                )
            }

            for wid in workers:
                wh = all_wh.get(wid, {})
                status_label = wh.get('status', 'unknown').upper()
                color = (
                    self.style.SUCCESS if status_label in ('IDLE', 'BUSY', 'ONLINE')
                    else self.style.ERROR
                )
                self.stdout.write(color(f'\n  Worker: {wid}'))
                self.stdout.write(f'    Status      : {status_label}')
                self.stdout.write(f'    Hostname    : {wh.get("hostname", "?")}')
                self.stdout.write(f'    Queues      : {", ".join(wh.get("queue_names") or ["?"])}')
                self.stdout.write(f'    Concurrency : {wh.get("concurrency", "?")}')
                self.stdout.write(f'    Active Tasks: {wh.get("active_tasks", 0)}')
                if wh.get('cpu_percent') is not None:
                    self.stdout.write(f'    CPU         : {wh["cpu_percent"]:.1f}%')
                if wh.get('memory_mb') is not None:
                    self.stdout.write(f'    Memory      : {wh["memory_mb"]:.1f} MB')
                if wh.get('last_heartbeat'):
                    self.stdout.write(f'    Last Heartbeat: {wh["last_heartbeat"]}')

        # ── Check stale workers in DB ─────────────────────────────────
        try:
            from api.tasks.models.monitoring import WorkerHealth
            from datetime import timedelta

            stale_cutoff = timezone.now() - timedelta(minutes=5)
            stale = WorkerHealth.objects.filter(
                last_heartbeat__lt=stale_cutoff,
                status__in=['online', 'idle', 'busy'],
            )
            if stale.exists():
                self.stdout.write(self.style.WARNING(
                    f'\n  ⚠  {stale.count()} stale worker record(s) in DB '
                    f'(last heartbeat > 5 min ago)'
                ))
                for w in stale.values('worker_id', 'last_heartbeat'):
                    self.stdout.write(f'     - {w["worker_id"]} last: {w["last_heartbeat"]}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  [WARN] Could not check stale workers: {e}'))

        # ── Exit code ─────────────────────────────────────────────────
        self.stdout.write('-' * 60)

        if alert_off and online < min_workers:
            self.stderr.write(self.style.ERROR(
                f'[FAIL] Only {online} worker(s) online, expected at least {min_workers}.'
            ))
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS('[DONE] Worker health check complete.\n'))
