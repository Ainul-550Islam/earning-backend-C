"""
tasks/management/commands/estimate_task_costs.py
Compute and display compute cost estimates per Celery task.

Usage:
  python manage.py estimate_task_costs
  python manage.py estimate_task_costs --top 20
  python manage.py estimate_task_costs --task tasks.payment_tasks.process_withdrawal_requests
  python manage.py estimate_task_costs --period last_30_days --update
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Estimate and display Celery task compute costs'

    def add_arguments(self, parser):
        parser.add_argument('--task',    type=str, help='Estimate cost for a specific task_name')
        parser.add_argument('--top',     type=int, default=15, help='Show top N costly tasks (default 15)')
        parser.add_argument('--period',  type=str, default='last_7_days',
                            choices=['last_1_day', 'last_7_days', 'last_30_days'])
        parser.add_argument('--update',  action='store_true', help='Recompute and save estimates to DB')
        parser.add_argument('--monthly', action='store_true', help='Show projected monthly cost')

    def handle(self, *args, **options):
        from api.tasks.services.TaskCostService import TaskCostService

        svc    = TaskCostService()
        period = options['period']
        top    = options['top']

        # ── Recompute ─────────────────────────────────────────────────
        if options['update']:
            task_name = options.get('task')
            if task_name:
                self.stdout.write(f'Recomputing cost for: {task_name}...')
                result = svc.update_cost_estimate(task_name, estimation_period=period)
                if result.get('success'):
                    self.stdout.write(self.style.SUCCESS(
                        f"  cost_per_run = ${result['cost_per_run']}"
                        f"  monthly_est  = ${result['monthly_cost_est']}"
                        f"  samples      = {result['sample_size']}"
                    ))
                else:
                    self.stderr.write(self.style.ERROR(f"  [FAIL] {result.get('error')}"))
                return
            else:
                self.stdout.write(f'Recomputing costs for all tasks (period={period})...')
                result = svc.refresh_all()
                self.stdout.write(self.style.SUCCESS(
                    f"[OK] Updated={result.get('updated')} Errors={result.get('errors')}"
                ))

        # ── Display top costly ─────────────────────────────────────────
        tasks = svc.get_top_costly_tasks(limit=top)

        if not tasks:
            self.stdout.write(self.style.WARNING(
                'No cost estimates found. Run with --update to compute estimates first.'
            ))
            return

        self.stdout.write(f'\nTop {top} Costly Tasks (period={period}):')
        self.stdout.write('=' * 90)
        self.stdout.write(
            f"{'Task Name':<55} {'$/run':>10} {'CPU sec':>8} {'Mem MB':>7} {'Samples':>8}"
        )
        if options['monthly']:
            self.stdout.write(
                f"{'Task Name':<55} {'$/run':>10} {'$/month':>10} {'CPU sec':>8} {'Samples':>8}"
            )
        self.stdout.write('-' * 90)

        total_monthly = 0.0
        for t in tasks:
            cost     = float(t.get('cost_per_run') or 0)
            monthly  = float(t.get('monthly_cost_est') or 0)
            cpu      = t.get('avg_cpu_seconds') or 0
            mem      = t.get('avg_memory_mb') or 0
            samples  = t.get('sample_size') or 0
            name     = t['task_name']
            total_monthly += monthly

            if options['monthly']:
                self.stdout.write(
                    f"  {name:<53} ${cost:>9.6f} ${monthly:>9.4f} {cpu:>8.2f} {samples:>8}"
                )
            else:
                self.stdout.write(
                    f"  {name:<53} ${cost:>9.6f} {cpu:>8.2f} {mem:>7.1f} {samples:>8}"
                )

        self.stdout.write('=' * 90)

        if options['monthly']:
            self.stdout.write(
                self.style.SUCCESS(f"\n  Projected Total Monthly Cost: ${total_monthly:.4f}")
            )

        self.stdout.write('')
