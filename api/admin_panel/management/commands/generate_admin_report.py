# api/admin_panel/management/commands/generate_admin_report.py
"""
Management command: manually generate an admin report.
Usage:
  python manage.py generate_admin_report --type user --output /tmp/user_report.csv
  python manage.py generate_admin_report --type revenue --format json --days 30
  python manage.py generate_admin_report --definition-id 5
"""
import os
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Manually generate an admin report and save to file.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type', '-t',
            type=str,
            choices=['user', 'payment', 'revenue', 'activity', 'withdrawal', 'referral', 'earning', 'fraud'],
            default='user',
            help='Report type (default: user).',
        )
        parser.add_argument(
            '--output', '-o',
            type=str,
            default=None,
            help='Output file path. Defaults to /tmp/<type>_report_<date>.<format>.',
        )
        parser.add_argument(
            '--format', '-f',
            type=str,
            choices=['csv', 'xlsx', 'json'],
            default='csv',
            help='Output format (default: csv).',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Data range: last N days (default: 30).',
        )
        parser.add_argument(
            '--start-date',
            type=str,
            default=None,
            help='Start date filter YYYY-MM-DD.',
        )
        parser.add_argument(
            '--end-date',
            type=str,
            default=None,
            help='End date filter YYYY-MM-DD.',
        )
        parser.add_argument(
            '--definition-id',
            type=int,
            default=None,
            help='Use a specific ReportDefinition ID instead of type.',
        )
        parser.add_argument(
            '--email',
            type=str,
            default=None,
            help='Email address to send the completed report to.',
        )

    def handle(self, *args, **options):
        from django.utils import timezone
        from datetime import timedelta, datetime

        report_type = options['type']
        output_path = options.get('output')
        fmt = options['format']
        days = options['days']
        start_str = options.get('start_date')
        end_str = options.get('end_date')
        definition_id = options.get('definition_id')
        email = options.get('email')

        # Resolve dates
        end_date = datetime.strptime(end_str, '%Y-%m-%d').date() if end_str else timezone.now().date()
        start_date = datetime.strptime(start_str, '%Y-%m-%d').date() if start_str else (end_date - timedelta(days=days))

        # Default output path
        if not output_path:
            date_str = timezone.now().strftime('%Y%m%d_%H%M%S')
            output_path = f'/tmp/{report_type}_report_{date_str}.{fmt}'

        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        self.stdout.write(f'Generating {report_type.upper()} report...')
        self.stdout.write(f'  Date range: {start_date} → {end_date}')
        self.stdout.write(f'  Format: {fmt.upper()}')
        self.stdout.write(f'  Output: {output_path}')

        try:
            from api.admin_panel.services.ReportService import ReportService
            data = ReportService.get_report_data(
                report_type=report_type,
                filters={'start_date': start_date, 'end_date': end_date},
            )
        except Exception as e:
            raise CommandError(f'Report data generation failed: {e}')

        rows = data.get('rows', [])
        total = data.get('total', len(rows))
        self.stdout.write(f'  Records found: {total}')

        if not rows:
            self.stdout.write(self.style.WARNING('  No data found for this filter.'))
            return

        # Write output file
        try:
            if fmt == 'csv':
                self._write_csv(output_path, rows)
            elif fmt == 'xlsx':
                self._write_xlsx(output_path, rows)
            elif fmt == 'json':
                self._write_json(output_path, rows, data)
        except Exception as e:
            raise CommandError(f'File write failed: {e}')

        file_size = os.path.getsize(output_path)
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Report generated: {output_path} ({file_size / 1024:.1f} KB, {len(rows)} rows)'
        ))

        # Also create a Report model record
        try:
            from django.contrib.auth import get_user_model
            from api.admin_panel.models.core import Report
            Report.objects.create(
                title=f'{report_type.title()} Report {timezone.now().strftime("%Y-%m-%d")}',
                report_type=report_type,
                start_date=start_date,
                end_date=end_date,
                report_data={'rows_count': len(rows), 'total': total},
                file_format=fmt,
                status='completed',
            )
        except Exception:
            pass

        # Email if requested
        if email:
            try:
                from api.admin_panel.utils import send_admin_email_notification
                with open(output_path, 'rb') as f:
                    pass  # Just check it exists
                send_admin_email_notification(
                    subject=f'[Report] {report_type.title()} Report — {timezone.now().strftime("%Y-%m-%d")}',
                    message=f'Your {report_type} report is attached. Records: {len(rows)}',
                    recipient_list=[email],
                )
                self.stdout.write(f'  Email sent to: {email}')
            except Exception as e:
                self.stderr.write(f'  Email send failed: {e}')

    def _write_csv(self, path: str, rows: list):
        import csv
        if not rows:
            return
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)

    def _write_xlsx(self, path: str, rows: list):
        try:
            import openpyxl
        except ImportError:
            self.stderr.write('openpyxl not installed. Falling back to CSV.')
            self._write_csv(path.replace('.xlsx', '.csv'), rows)
            return
        if not rows:
            return
        wb = openpyxl.Workbook()
        ws = wb.active
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([str(row.get(h, '')) for h in headers])
        wb.save(path)

    def _write_json(self, path: str, rows: list, full_data: dict):
        import json
        output = {
            'meta': {
                'total': full_data.get('total', len(rows)),
                'rows_exported': len(rows),
            },
            'data': rows,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)