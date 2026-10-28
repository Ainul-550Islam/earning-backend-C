# api/admin_panel/management/commands/cleanup_old_data.py
"""
Management command: cleanup old admin data (activity logs, sessions, exports).
Usage:
  python manage.py cleanup_old_data
  python manage.py cleanup_old_data --dry-run
  python manage.py cleanup_old_data --activity-days 60 --session-days 14
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Cleanup old admin activity logs, sessions, search history, and expired exports.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Show what would be deleted without actually deleting.',
        )
        parser.add_argument(
            '--activity-days',
            type=int,
            default=90,
            help='Delete AdminActivity logs older than N days (default: 90).',
        )
        parser.add_argument(
            '--session-days',
            type=int,
            default=30,
            help='Delete inactive AdminSession records older than N days (default: 30).',
        )
        parser.add_argument(
            '--search-days',
            type=int,
            default=7,
            help='Delete AdminSearch records older than N days (default: 7).',
        )
        parser.add_argument(
            '--export-days',
            type=int,
            default=3,
            help='Delete expired DataExport/ReportExport files older than N days (default: 3).',
        )
        parser.add_argument(
            '--insight-days',
            type=int,
            default=14,
            help='Delete dismissed AdminInsight records older than N days (default: 14).',
        )
        parser.add_argument(
            '--skip-activity',
            action='store_true',
            default=False,
            help='Skip activity log cleanup.',
        )
        parser.add_argument(
            '--skip-sessions',
            action='store_true',
            default=False,
            help='Skip session cleanup.',
        )
        parser.add_argument(
            '--skip-exports',
            action='store_true',
            default=False,
            help='Skip export cleanup.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — nothing will be deleted.\n'))

        total_deleted = 0

        # 1. AdminActivity
        if not options['skip_activity']:
            cutoff = now - timedelta(days=options['activity_days'])
            total_deleted += self._cleanup(
                model_path='api.admin_panel.models.activity.AdminActivity',
                filter_kwargs={'created_at__lt': cutoff},
                label=f'AdminActivity (>{options["activity_days"]} days)',
                dry_run=dry_run,
            )

        # 2. AdminSession (inactive only)
        if not options['skip_sessions']:
            session_cutoff = now - timedelta(days=options['session_days'])
            total_deleted += self._cleanup(
                model_path='api.admin_panel.models.activity.AdminSession',
                filter_kwargs={'is_active': False, 'started_at__lt': session_cutoff},
                label=f'AdminSession inactive (>{options["session_days"]} days)',
                dry_run=dry_run,
            )

        # 3. AdminSearch
        search_cutoff = now - timedelta(days=options['search_days'])
        total_deleted += self._cleanup(
            model_path='api.admin_panel.models.activity.AdminSearch',
            filter_kwargs={'created_at__lt': search_cutoff},
            label=f'AdminSearch (>{options["search_days"]} days)',
            dry_run=dry_run,
        )

        # 4. DataExport (expired or failed)
        if not options['skip_exports']:
            export_cutoff = now - timedelta(days=options['export_days'])
            total_deleted += self._cleanup_exports(
                model_path='api.admin_panel.models.reports.DataExport',
                cutoff=export_cutoff,
                label=f'DataExport expired/failed (>{options["export_days"]} days)',
                dry_run=dry_run,
            )
            total_deleted += self._cleanup_exports(
                model_path='api.admin_panel.models.reports.ReportExport',
                cutoff=export_cutoff,
                label=f'ReportExport expired/failed (>{options["export_days"]} days)',
                dry_run=dry_run,
            )

        # 5. AdminInsight (dismissed + old)
        insight_cutoff = now - timedelta(days=options['insight_days'])
        total_deleted += self._cleanup(
            model_path='api.admin_panel.models.reports.AdminInsight',
            filter_kwargs={'is_dismissed': True, 'updated_at__lt': insight_cutoff},
            label=f'AdminInsight dismissed (>{options["insight_days"]} days)',
            dry_run=dry_run,
        )

        # 6. Expired AdminInsight (auto-expired)
        total_deleted += self._cleanup(
            model_path='api.admin_panel.models.reports.AdminInsight',
            filter_kwargs={'expires_at__lt': now},
            label='AdminInsight auto-expired',
            dry_run=dry_run,
        )

        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN complete. Would delete {total_deleted} records.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'✅ Cleanup complete. Deleted {total_deleted} records total.'))

    def _cleanup(self, model_path: str, filter_kwargs: dict, label: str, dry_run: bool) -> int:
        """Generic cleanup for a model with given filters."""
        try:
            import importlib
            parts = model_path.rsplit('.', 1)
            module = importlib.import_module(parts[0])
            Model = getattr(module, parts[1])
            qs = Model.objects.filter(**filter_kwargs)
            count = qs.count()
            if dry_run:
                self.stdout.write(f'  WOULD DELETE {count:>6} — {label}')
            else:
                deleted, _ = qs.delete()
                self.stdout.write(f'  Deleted {deleted:>6} — {label}')
                return deleted
            return count
        except Exception as e:
            self.stderr.write(f'  ERROR cleaning {label}: {e}')
            return 0

    def _cleanup_exports(self, model_path: str, cutoff, label: str, dry_run: bool) -> int:
        """Cleanup export files and records."""
        import os
        try:
            import importlib
            parts = model_path.rsplit('.', 1)
            module = importlib.import_module(parts[0])
            Model = getattr(module, parts[1])

            from django.db.models import Q
            qs = Model.objects.filter(
                Q(expires_at__lt=timezone.now()) | Q(status='failed'),
                created_at__lt=cutoff,
            )
            count = qs.count()

            if not dry_run:
                # Delete files first
                deleted_files = 0
                for export in qs:
                    if hasattr(export, 'file_path') and export.file_path:
                        if os.path.exists(export.file_path):
                            try:
                                os.remove(export.file_path)
                                deleted_files += 1
                            except OSError as e:
                                self.stderr.write(f'  File delete error: {e}')
                deleted_records, _ = qs.delete()
                self.stdout.write(f'  Deleted {deleted_records:>6} records + {deleted_files} files — {label}')
                return deleted_records
            else:
                self.stdout.write(f'  WOULD DELETE {count:>6} — {label}')
            return count
        except Exception as e:
            self.stderr.write(f'  ERROR cleaning {label}: {e}')
            return 0