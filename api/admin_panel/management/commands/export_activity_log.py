# api/admin_panel/management/commands/export_activity_log.py
"""
Management command: export admin activity log to CSV or JSON.
Usage:
  python manage.py export_activity_log --output /tmp/activity.csv
  python manage.py export_activity_log --days 30 --format json --output /tmp/activity.json
  python manage.py export_activity_log --actor admin --action create
"""
import csv
import json
import os
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Export AdminActivity log to CSV or JSON file.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output', '-o',
            type=str,
            required=True,
            help='Output file path (e.g. /tmp/activity_log.csv)',
        )
        parser.add_argument(
            '--format', '-f',
            type=str,
            choices=['csv', 'json'],
            default='csv',
            help='Output format: csv or json (default: csv).',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Export activities from the last N days (default: 30).',
        )
        parser.add_argument(
            '--actor',
            type=str,
            default=None,
            help='Filter by actor username.',
        )
        parser.add_argument(
            '--action',
            type=str,
            default=None,
            help='Filter by action (e.g. create, delete, admin_login).',
        )
        parser.add_argument(
            '--status',
            type=str,
            choices=['success', 'failed', 'partial'],
            default=None,
            help='Filter by activity status.',
        )
        parser.add_argument(
            '--model',
            type=str,
            default=None,
            help='Filter by model_name.',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100000,
            help='Maximum number of records to export (default: 100000).',
        )

    def handle(self, *args, **options):
        output_path = options['output']
        fmt = options['format']
        days = options['days']
        actor_filter = options.get('actor')
        action_filter = options.get('action')
        status_filter = options.get('status')
        model_filter = options.get('model')
        limit = options['limit']

        # Build queryset
        try:
            from api.admin_panel.models.activity import AdminActivity
        except ImportError as e:
            raise CommandError(f'AdminActivity model not available: {e}')

        cutoff = timezone.now() - timedelta(days=days)
        qs = AdminActivity.objects.filter(
            created_at__gte=cutoff
        ).select_related('actor').order_by('-created_at')

        if actor_filter:
            qs = qs.filter(actor__username__icontains=actor_filter)
        if action_filter:
            qs = qs.filter(action=action_filter)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if model_filter:
            qs = qs.filter(model_name__icontains=model_filter)

        total = qs.count()
        export_count = min(total, limit)
        qs = qs[:limit]

        self.stdout.write(f'Exporting {export_count} of {total} activity records...')
        self.stdout.write(f'  Filter: days={days}, actor={actor_filter}, action={action_filter}')
        self.stdout.write(f'  Output: {output_path} ({fmt.upper()})')

        # Ensure output directory exists
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        if fmt == 'csv':
            written = self._write_csv(qs, output_path)
        else:
            written = self._write_json(qs, output_path)

        file_size = os.path.getsize(output_path)
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Exported {written} records to {output_path} '
            f'({file_size / 1024:.1f} KB)'
        ))

    def _write_csv(self, queryset, path: str) -> int:
        fields = [
            'id', 'actor__username', 'action', 'model_name', 'object_id',
            'object_repr', 'status', 'ip', 'method', 'response_code',
            'path', 'user_agent', 'created_at',
        ]
        headers = [
            'ID', 'Actor', 'Action', 'Model', 'Object ID',
            'Object', 'Status', 'IP', 'Method', 'Response Code',
            'Path', 'User Agent', 'Created At',
        ]
        count = 0
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for record in queryset.values(*fields).iterator(chunk_size=1000):
                writer.writerow([
                    record.get('id', ''),
                    record.get('actor__username', ''),
                    record.get('action', ''),
                    record.get('model_name', ''),
                    record.get('object_id', ''),
                    record.get('object_repr', ''),
                    record.get('status', ''),
                    record.get('ip', ''),
                    record.get('method', ''),
                    record.get('response_code', ''),
                    record.get('path', ''),
                    str(record.get('user_agent', ''))[:100],
                    str(record.get('created_at', '')),
                ])
                count += 1
        return count

    def _write_json(self, queryset, path: str) -> int:
        records = []
        for activity in queryset.select_related('actor').iterator(chunk_size=1000):
            records.append({
                'id': activity.pk,
                'actor': activity.actor.username if activity.actor else None,
                'action': activity.action,
                'model_name': activity.model_name,
                'object_id': activity.object_id,
                'object_repr': activity.object_repr,
                'changes': activity.changes,
                'status': activity.status,
                'ip': activity.ip,
                'method': activity.method,
                'response_code': activity.response_code,
                'path': activity.path,
                'user_agent': activity.user_agent[:100] if activity.user_agent else '',
                'created_at': activity.created_at.isoformat(),
            })
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2, default=str)
        return len(records)