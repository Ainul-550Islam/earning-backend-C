"""
tasks/management/commands/generate_task_report.py
Generate and display task performance/revenue reports from the CLI.

Usage:
  python manage.py generate_task_report --type daily_revenue
  python manage.py generate_task_report --type weekly_user
  python manage.py generate_task_report --type task_performance --days 30
  python manage.py generate_task_report --type daily_revenue --date 2025-01-15 --email
"""
import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Generate task system reports'

    REPORT_TYPES = ['daily_revenue', 'weekly_user', 'monthly_admin', 'task_performance', 'platform_kpis']

    def add_arguments(self, parser):
        parser.add_argument(
            '--type', '-t',
            type=str,
            default='daily_revenue',
            choices=self.REPORT_TYPES,
            help=f'Report type. Options: {", ".join(self.REPORT_TYPES)}',
        )
        parser.add_argument('--date',   type=str, help='Target date YYYY-MM-DD (default: yesterday)')
        parser.add_argument('--days',   type=int, default=30, help='Lookback days (for task_performance)')
        parser.add_argument('--email',  action='store_true', help='Email report to all admins')
        parser.add_argument('--json',   action='store_true', help='Output raw JSON')

    def handle(self, *args, **options):
        report_type = options['type']
        date_str    = options.get('date')
        days        = options['days']
        emit_json   = options['json']

        self.stdout.write(f'\nGenerating {report_type} report...')

        report = self._generate(report_type, date_str, days)

        if emit_json:
            self.stdout.write(json.dumps(report, indent=2, default=str))
        else:
            self._pretty_print(report_type, report)

        if options['email']:
            self._email_report(report_type, date_str)

    def _generate(self, report_type: str, date_str: str, days: int) -> dict:
        if report_type == 'daily_revenue':
            from api.tasks.report_tasks import generate_daily_revenue_report
            result = generate_daily_revenue_report.apply(kwargs={'date_str': date_str})
            return result.get() if hasattr(result, 'get') else result

        elif report_type == 'weekly_user':
            from api.tasks.report_tasks import generate_weekly_user_report
            result = generate_weekly_user_report.apply()
            return result.get() if hasattr(result, 'get') else result

        elif report_type == 'monthly_admin':
            from api.tasks.report_tasks import generate_monthly_admin_report
            result = generate_monthly_admin_report.apply()
            return result.get() if hasattr(result, 'get') else result

        elif report_type == 'task_performance':
            from api.tasks.report_tasks import generate_task_performance_report
            result = generate_task_performance_report.apply(kwargs={'lookback_days': days})
            return result.get() if hasattr(result, 'get') else result

        elif report_type == 'platform_kpis':
            from api.tasks.analytics_tasks import compute_platform_kpis
            result = compute_platform_kpis.apply()
            return result.get() if hasattr(result, 'get') else result

        return {}

    def _pretty_print(self, report_type: str, result: dict):
        report = result.get('report') or result.get('kpis') or result
        self.stdout.write('=' * 60)
        self.stdout.write(f'  Report: {report_type.replace("_", " ").title()}')
        self.stdout.write('=' * 60)

        if isinstance(report, dict):
            for key, value in report.items():
                if isinstance(value, (list, dict)):
                    self.stdout.write(f'\n  {key}:')
                    if isinstance(value, list):
                        for item in value[:10]:
                            self.stdout.write(f'    {item}')
                    else:
                        for k, v in value.items():
                            self.stdout.write(f'    {k}: {v}')
                else:
                    self.stdout.write(f'  {key:<35}: {value}')
        self.stdout.write('')

    def _email_report(self, report_type: str, date_str: str):
        from api.tasks.report_tasks import email_report_to_admins
        self.stdout.write('Queuing email to admins...')
        email_report_to_admins.apply_async(kwargs={
            'report_type': report_type,
            'date_str': date_str,
        })
        self.stdout.write(self.style.SUCCESS('[OK] Email queued.'))
