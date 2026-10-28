"""
tasks/management/commands/flush_dead_letter.py
Retry or discard Dead Letter Queue tasks from the CLI.

Usage:
  python manage.py flush_dead_letter --stats
  python manage.py flush_dead_letter --retry-all
  python manage.py flush_dead_letter --retry-all --task-name tasks.payment_tasks.process_withdrawal_requests
  python manage.py flush_dead_letter --discard-all
  python manage.py flush_dead_letter --retry-id 42
  python manage.py flush_dead_letter --discard-id 42
"""
import sys
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Manage Dead Letter Queue — retry or discard failed tasks'

    def add_arguments(self, parser):
        parser.add_argument('--stats',        action='store_true', help='Show DLQ statistics')
        parser.add_argument('--retry-all',    action='store_true', help='Retry all pending DLQ entries')
        parser.add_argument('--discard-all',  action='store_true', help='Discard all pending DLQ entries')
        parser.add_argument('--retry-id',     type=int,            help='Retry a specific DLQ entry by ID')
        parser.add_argument('--discard-id',   type=int,            help='Discard a specific DLQ entry by ID')
        parser.add_argument('--task-name',    type=str,            help='Filter by task name')
        parser.add_argument('--list',         action='store_true', help='List pending DLQ entries')
        parser.add_argument('--limit',        type=int, default=50, help='Max entries to list (default 50)')
        parser.add_argument('--notes',        type=str, default='', help='Notes to attach to requeue/discard')
        parser.add_argument(
            '--yes', '-y',
            action='store_true',
            default=False,
            help='Skip confirmation prompt for destructive actions',
        )

    def handle(self, *args, **options):
        from api.tasks.services.DeadLetterService import DeadLetterService

        svc = DeadLetterService()

        # ── Stats ─────────────────────────────────────────────────────
        if options['stats']:
            self._show_stats(svc)
            return

        # ── List ──────────────────────────────────────────────────────
        if options['list']:
            self._list_entries(svc, options['task_name'], options['limit'])
            return

        # ── Retry single ──────────────────────────────────────────────
        if options.get('retry_id'):
            dlq_id = options['retry_id']
            self.stdout.write(f'Retrying DLQ entry #{dlq_id}...')
            result = svc.retry_entry(dlq_id, notes=options['notes'])
            if result.get('success'):
                self.stdout.write(self.style.SUCCESS(
                    f"[OK] Requeued as Celery task {result.get('new_task_id')}"
                ))
            else:
                self.stderr.write(self.style.ERROR(f"[FAIL] {result.get('error')}"))
                sys.exit(1)
            return

        # ── Discard single ────────────────────────────────────────────
        if options.get('discard_id'):
            dlq_id = options['discard_id']
            self.stdout.write(f'Discarding DLQ entry #{dlq_id}...')
            result = svc.discard_entry(dlq_id, notes=options['notes'])
            if result.get('success'):
                self.stdout.write(self.style.SUCCESS(f'[OK] Entry #{dlq_id} discarded.'))
            else:
                self.stderr.write(self.style.ERROR(f"[FAIL] {result.get('error')}"))
            return

        # ── Retry all ─────────────────────────────────────────────────
        if options['retry_all']:
            task_name = options.get('task_name')
            if not options['yes']:
                confirm = input(
                    f'Retry ALL pending DLQ entries'
                    f'{" for " + task_name if task_name else ""}? [y/N] '
                )
                if confirm.lower() != 'y':
                    self.stdout.write('Aborted.')
                    return

            self.stdout.write('Retrying all pending DLQ entries...')
            result = svc.retry_all_pending(task_name=task_name)
            self.stdout.write(self.style.SUCCESS(
                f"[OK] Retried={result.get('retried')} Failed={result.get('failed')}"
            ))
            return

        # ── Discard all ───────────────────────────────────────────────
        if options['discard_all']:
            task_name = options.get('task_name')
            if not options['yes']:
                confirm = input(
                    f'Discard ALL pending DLQ entries'
                    f'{" for " + task_name if task_name else ""}? [y/N] '
                )
                if confirm.lower() != 'y':
                    self.stdout.write('Aborted.')
                    return

            result = svc.discard_all(task_name=task_name)
            self.stdout.write(self.style.WARNING(
                f"[DONE] Discarded {result.get('discarded')} entries."
            ))
            return

        # ── No action ─────────────────────────────────────────────────
        self.stdout.write('No action specified. Use --help for usage.')

    def _show_stats(self, svc):
        stats = svc.get_stats()
        self.stdout.write(self.style.SUCCESS('\nDead Letter Queue Statistics'))
        self.stdout.write('-' * 50)
        self.stdout.write(f"  Total entries : {stats.get('total', 0)}")
        self.stdout.write(f"  Pending       : {stats.get('pending', 0)}")
        self.stdout.write(f"  Requeued      : {stats.get('requeued', 0)}")
        self.stdout.write(f"  Discarded     : {stats.get('discarded', 0)}")
        top = stats.get('top_failing_tasks', [])
        if top:
            self.stdout.write('\nTop failing tasks:')
            for t in top:
                self.stdout.write(f"  {t['count']:>5}x  {t['task_name']}")
        self.stdout.write('')

    def _list_entries(self, svc, task_name=None, limit=50):
        entries = svc.list_pending(limit=limit)
        if task_name:
            entries = [e for e in entries if task_name in e['task_name']]
        if not entries:
            self.stdout.write(self.style.WARNING('No pending DLQ entries found.'))
            return
        self.stdout.write(f'\nPending DLQ entries ({len(entries)}):')
        self.stdout.write('-' * 80)
        for e in entries:
            self.stdout.write(
                f"  [{e['id']:>6}]  {e['task_name']:<50}  "
                f"retries={e['retry_count']}  reason={e['failure_reason']}"
            )
            self.stdout.write(f"           Error: {str(e.get('error', ''))[:80]}")
