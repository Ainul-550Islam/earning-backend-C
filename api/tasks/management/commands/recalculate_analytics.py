"""
tasks/management/commands/recalculate_analytics.py
Recalculate TaskInsight, TaskFailureRate, TaskThroughput records.

Usage:
  python manage.py recalculate_analytics
  python manage.py recalculate_analytics --days 30
  python manage.py recalculate_analytics --date 2025-01-01
  python manage.py recalculate_analytics --failure-rates --period daily
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Recalculate task analytics (TaskInsight, failure rates, throughput)'

    def add_arguments(self, parser):
        parser.add_argument('--days',  type=int, default=7,  help='Backfill last N days (default 7)')
        parser.add_argument('--date',  type=str,              help='Recalculate a specific date YYYY-MM-DD')
        parser.add_argument('--failure-rates', action='store_true', help='Also recalculate failure rates')
        parser.add_argument('--period', type=str, default='daily',
                            choices=['hourly', 'daily', 'weekly', 'monthly'],
                            help='Period for failure rate calculation')
        parser.add_argument('--platform-kpis', action='store_true', help='Recompute platform KPIs')
        parser.add_argument('--async',   dest='run_async', action='store_true',
                            help='Dispatch as background Celery tasks instead of running synchronously')

    def handle(self, *args, **options):
        days       = options['days']
        date_str   = options.get('date')
        run_async  = options['run_async']
        fail_rates = options['failure_rates']
        period     = options['period']
        plat_kpis  = options['platform_kpis']

        self.stdout.write(f'\nRecalculating analytics (days={days}, async={run_async})...')

        if date_str:
            # Single date
            self._run_rollup(date_str, run_async)
        else:
            # Backfill N days
            from datetime import timedelta, date
            today = timezone.now().date()
            for i in range(days, 0, -1):
                d = (today - timedelta(days=i)).strftime('%Y-%m-%d')
                self._run_rollup(d, run_async)

        if fail_rates:
            self.stdout.write(f'\nRecalculating failure rates (period={period})...')
            if run_async:
                from api.tasks.analytics_tasks import compute_task_failure_rates
                result = compute_task_failure_rates.apply_async(kwargs={'period': period})
                self.stdout.write(f'  Dispatched async: task_id={result.id}')
            else:
                from api.tasks.analytics_tasks import compute_task_failure_rates
                result = compute_task_failure_rates.apply(kwargs={'period': period})
                data   = result.get()
                self.stdout.write(self.style.SUCCESS(
                    f"  [OK] {data.get('rows_created', 0)} created, {data.get('rows_updated', 0)} updated"
                ))

        if plat_kpis:
            self.stdout.write('\nRecomputing platform KPIs...')
            if run_async:
                from api.tasks.analytics_tasks import compute_platform_kpis
                result = compute_platform_kpis.apply_async()
                self.stdout.write(f'  Dispatched async: task_id={result.id}')
            else:
                from api.tasks.analytics_tasks import compute_platform_kpis
                result = compute_platform_kpis.apply()
                data   = result.get()
                self.stdout.write(self.style.SUCCESS(f"  [OK] KPIs: {data.get('kpis', {})}"))

        self.stdout.write(self.style.SUCCESS('\n[DONE] Analytics recalculation complete.'))

    def _run_rollup(self, date_str: str, run_async: bool):
        if run_async:
            from api.tasks.analytics_tasks import daily_analytics_rollup
            result = daily_analytics_rollup.apply_async(kwargs={'date_str': date_str})
            self.stdout.write(f'  {date_str} → dispatched (task_id={result.id})')
        else:
            from api.tasks.analytics_tasks import daily_analytics_rollup
            result = daily_analytics_rollup.apply(kwargs={'date_str': date_str})
            data   = result.get()
            self.stdout.write(
                f"  {date_str} → created={data.get('rows_created', 0)} "
                f"updated={data.get('rows_updated', 0)}"
            )
