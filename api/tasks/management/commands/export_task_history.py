"""
tasks/management/commands/export_task_history.py
Export task history records to CSV/JSON from CLI.

Usage:
  python manage.py export_task_history
  python manage.py export_task_history --start 2025-01-01 --end 2025-01-31
  python manage.py export_task_history --type performance_logs --format json
  python manage.py export_task_history --type insights --days 30
"""
import os
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Export task history and analytics data to CSV/JSON files'

    EXPORT_TYPES = ['task_history', 'performance_logs', 'insights', 'dlq', 'user_earnings', 'admin_ledger']

    def add_arguments(self, parser):
        parser.add_argument('--type',    type=str, default='task_history', choices=self.EXPORT_TYPES)
        parser.add_argument('--start',   type=str, help='Start date YYYY-MM-DD')
        parser.add_argument('--end',     type=str, help='End date YYYY-MM-DD')
        parser.add_argument('--days',    type=int, default=30, help='Lookback days (default 30)')
        parser.add_argument('--format',  type=str, default='csv', choices=['csv', 'json'])
        parser.add_argument('--status',  type=str, help='Filter by completion status')
        parser.add_argument('--user-id', type=int, help='Filter by user ID')
        parser.add_argument('--output',  type=str, help='Output directory (default: EXPORT_DIR setting)')
        parser.add_argument('--async',   dest='run_async', action='store_true',
                            help='Dispatch as async Celery task')

    def handle(self, *args, **options):
        export_type = options['type']
        fmt         = options['format']
        run_async   = options['run_async']

        self.stdout.write(f'\nExporting {export_type} as {fmt}...')

        if run_async:
            self._dispatch_async(options)
            return

        from api.tasks.services.TaskExportService import TaskExportService
        svc = TaskExportService()

        if export_type == 'performance_logs':
            result = svc.export_performance_logs(
                task_name=None,
                days=options['days'],
                fmt=fmt,
            )
        elif export_type == 'insights':
            result = svc.export_insights(days=options['days'], fmt=fmt)

        elif export_type == 'dlq':
            result = svc.export_dlq(fmt=fmt)

        elif export_type == 'task_history':
            from api.tasks.export_tasks import export_task_history
            r = export_task_history.apply(kwargs={
                'user_id': options.get('user_id'),
                'start_date': options.get('start'),
                'end_date': options.get('end'),
                'status': options.get('status'),
            })
            result = r.get()

        elif export_type == 'user_earnings':
            from api.tasks.export_tasks import export_user_earnings
            r = export_user_earnings.apply(kwargs={
                'start_date': options.get('start'),
                'end_date': options.get('end'),
            })
            result = r.get()

        elif export_type == 'admin_ledger':
            from api.tasks.export_tasks import export_admin_ledger
            r = export_admin_ledger.apply(kwargs={
                'start_date': options.get('start'),
                'end_date': options.get('end'),
            })
            result = r.get()

        else:
            result = {'success': False, 'error': 'Unknown export type'}

        if result.get('success'):
            filename = result.get('filename', '')
            rows     = result.get('row_count', 0)
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Exported {rows} rows → {filename}'
            ))
            from django.conf import settings
            export_dir = getattr(settings, 'EXPORT_DIR', '/tmp/task_exports/')
            self.stdout.write(f'     Full path: {os.path.join(export_dir, filename)}')
        else:
            self.stderr.write(self.style.ERROR(f"[FAIL] {result.get('error')}"))

    def _dispatch_async(self, options):
        export_type = options['type']
        if export_type == 'task_history':
            from api.tasks.export_tasks import export_task_history
            result = export_task_history.apply_async(kwargs={
                'user_id': options.get('user_id'),
                'start_date': options.get('start'),
                'end_date': options.get('end'),
                'status': options.get('status'),
            })
        elif export_type == 'user_earnings':
            from api.tasks.export_tasks import export_user_earnings
            result = export_user_earnings.apply_async(kwargs={
                'start_date': options.get('start'),
                'end_date': options.get('end'),
            })
        else:
            self.stderr.write(self.style.WARNING(
                f'Async not supported for {export_type}. Running synchronously.'
            ))
            options['run_async'] = False
            self.handle(**{'options': options})
            return

        self.stdout.write(self.style.SUCCESS(f'[OK] Export queued. Task ID: {result.id}'))
