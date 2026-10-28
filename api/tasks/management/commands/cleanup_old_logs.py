"""
tasks/management/commands/cleanup_old_logs.py
Purge old task logs, queue snapshots, and workflow instances.

Usage:
  python manage.py cleanup_old_logs
  python manage.py cleanup_old_logs --perf-days 60 --depth-days 3
  python manage.py cleanup_old_logs --dry-run
  python manage.py cleanup_old_logs --all
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Clean up old task logs, queue depth snapshots, and workflow instances'

    def add_arguments(self, parser):
        parser.add_argument('--perf-days',     type=int, default=30,  help='Days to keep TaskPerformanceLog (default 30)')
        parser.add_argument('--depth-days',    type=int, default=7,   help='Days to keep QueueDepth snapshots (default 7)')
        parser.add_argument('--workflow-days', type=int, default=30,  help='Days to keep completed WorkflowInstances (default 30)')
        parser.add_argument('--sessions',      action='store_true',   help='Also clean expired Django sessions')
        parser.add_argument('--stale-workers', action='store_true',   help='Also clean stale WorkerHealth records')
        parser.add_argument('--all',           action='store_true',   help='Run all cleanup routines with defaults')
        parser.add_argument('--dry-run',       action='store_true',   help='Show what would be deleted without deleting')
        parser.add_argument('--async',         dest='run_async', action='store_true',
                            help='Run as Celery background tasks')

    def handle(self, *args, **options):
        dry      = options['dry_run']
        run_all  = options['all']
        run_async = options['run_async']

        if dry:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No data will be deleted.\n'))

        self.stdout.write('Starting cleanup...')
        self.stdout.write('-' * 50)

        total_deleted = 0

        # ── Performance logs ──────────────────────────────────────────
        perf_days = options['perf_days']
        if not dry:
            if run_async:
                from api.tasks.cleanup_tasks import cleanup_old_task_performance_logs
                cleanup_old_task_performance_logs.apply_async(kwargs={'days_to_keep': perf_days})
                self.stdout.write(f'  TaskPerformanceLog: async cleanup queued (keep={perf_days}d)')
            else:
                from api.tasks.cleanup_tasks import cleanup_old_task_performance_logs
                result = cleanup_old_task_performance_logs.apply(kwargs={'days_to_keep': perf_days})
                data   = result.get()
                n = data.get('deleted', 0)
                total_deleted += n
                self.stdout.write(f'  TaskPerformanceLog  : deleted {n} rows (>{perf_days}d old)')
        else:
            from api.tasks.models.monitoring import TaskPerformanceLog
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=perf_days)
            n = TaskPerformanceLog.objects.filter(created_at__lt=cutoff).count()
            self.stdout.write(f'  TaskPerformanceLog  : would delete {n} rows (>{perf_days}d old)')

        # ── Queue depth snapshots ─────────────────────────────────────
        depth_days = options['depth_days']
        if not dry:
            if run_async:
                from api.tasks.cleanup_tasks import cleanup_old_queue_depth_snapshots
                cleanup_old_queue_depth_snapshots.apply_async(kwargs={'days_to_keep': depth_days})
                self.stdout.write(f'  QueueDepth: async cleanup queued (keep={depth_days}d)')
            else:
                from api.tasks.cleanup_tasks import cleanup_old_queue_depth_snapshots
                result = cleanup_old_queue_depth_snapshots.apply(kwargs={'days_to_keep': depth_days})
                data   = result.get()
                n = data.get('deleted', 0)
                total_deleted += n
                self.stdout.write(f'  QueueDepth snapshots: deleted {n} rows (>{depth_days}d old)')
        else:
            from api.tasks.models.monitoring import QueueDepth
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(days=depth_days)
            n = QueueDepth.objects.filter(checked_at__lt=cutoff).count()
            self.stdout.write(f'  QueueDepth snapshots: would delete {n} rows (>{depth_days}d old)')

        # ── Workflow instances ─────────────────────────────────────────
        wf_days = options['workflow_days']
        if not dry:
            if run_async:
                from api.tasks.cleanup_tasks import cleanup_old_workflow_instances
                cleanup_old_workflow_instances.apply_async(kwargs={'days_to_keep': wf_days})
                self.stdout.write(f'  WorkflowInstances: async cleanup queued (keep={wf_days}d)')
            else:
                from api.tasks.cleanup_tasks import cleanup_old_workflow_instances
                result = cleanup_old_workflow_instances.apply(kwargs={'days_to_keep': wf_days})
                data   = result.get()
                n = data.get('deleted', 0)
                total_deleted += n
                self.stdout.write(f'  WorkflowInstances   : deleted {n} rows (>{wf_days}d old)')

        # ── Sessions ──────────────────────────────────────────────────
        if options['sessions'] or run_all:
            if not dry:
                from api.tasks.cleanup_tasks import cleanup_expired_sessions
                result = cleanup_expired_sessions.apply()
                data   = result.get()
                n = data.get('deleted', 0)
                total_deleted += n
                self.stdout.write(f'  Django sessions     : deleted {n} expired sessions')

        # ── Stale workers ─────────────────────────────────────────────
        if options['stale_workers'] or run_all:
            if not dry:
                from api.tasks.cleanup_tasks import cleanup_stale_worker_records
                result = cleanup_stale_worker_records.apply()
                data   = result.get()
                self.stdout.write(
                    f"  WorkerHealth        : {data.get('marked_offline', 0)} marked offline, "
                    f"{data.get('deleted', 0)} deleted"
                )

        self.stdout.write('-' * 50)
        if not dry:
            self.stdout.write(self.style.SUCCESS(
                f'[DONE] Total deleted: {total_deleted} records.'
            ))
        else:
            self.stdout.write(self.style.WARNING('[DRY RUN] Nothing was deleted.'))
