# api/admin_panel/management/commands/clear_config_cache.py
"""
Management command: clear all SystemConfig, FeatureFlag, and related cache entries.
Usage:
  python manage.py clear_config_cache
  python manage.py clear_config_cache --key referral_bonus_points
  python manage.py clear_config_cache --all
"""
from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache


class Command(BaseCommand):
    help = 'Clear all SystemConfig, FeatureFlag, and admin panel cache entries.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--key',
            type=str,
            default=None,
            help='Clear cache for a specific config key only.',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            default=False,
            help='Also clear system settings, endpoint toggles, dashboard, and session cache.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Show what would be cleared without actually clearing.',
        )

    def handle(self, *args, **options):
        key = options.get('key')
        clear_all = options.get('all')
        dry_run = options.get('dry_run')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no cache will be cleared.'))

        cleared_keys = []

        # --- SystemConfig cache ---
        try:
            from api.admin_panel.models.config import SystemConfig
            if key:
                cache_key = f'admin_panel:config:{key}'
                cleared_keys.append(cache_key)
                if not dry_run:
                    cache.delete(cache_key)
                self.stdout.write(f'  Config key: {cache_key}')
            else:
                config_keys = list(SystemConfig.objects.values_list('key', flat=True))
                for k in config_keys:
                    cache_key = f'admin_panel:config:{k}'
                    cleared_keys.append(cache_key)
                    if not dry_run:
                        cache.delete(cache_key)
                    self.stdout.write(f'  Config: {cache_key}')
                all_key = 'admin_panel:config_all'
                cleared_keys.append(all_key)
                if not dry_run:
                    cache.delete(all_key)
                self.stdout.write(f'  Config all: {all_key}')
        except Exception as e:
            self.stderr.write(f'  SystemConfig cache error: {e}')

        # --- FeatureFlag cache ---
        if not key:
            try:
                from api.admin_panel.models.config import FeatureFlag
                flag_keys = list(FeatureFlag.objects.values_list('flag_key', flat=True))
                for fk in flag_keys:
                    cache_key = f'admin_panel:feature_flag:{fk}'
                    cleared_keys.append(cache_key)
                    if not dry_run:
                        cache.delete(cache_key)
                    self.stdout.write(f'  FeatureFlag: {cache_key}')
                all_flags_key = 'admin_panel:feature_flags'
                cleared_keys.append(all_flags_key)
                if not dry_run:
                    cache.delete(all_flags_key)
                self.stdout.write(f'  Flags all: {all_flags_key}')
            except Exception as e:
                self.stderr.write(f'  FeatureFlag cache error: {e}')

        # --- Additional caches if --all ---
        if clear_all and not key:
            extra_keys = [
                'system_settings',
                'admin_panel:system_settings',
                'admin_panel:endpoint_toggles',
                'admin_panel:maintenance_mode_active',
                'admin_panel:maintenance_message',
                'admin_panel:system_health',
                'admin_panel:active_notifications',
                'admin_panel:login_notifications',
                'admin_panel:site_contents_all',
                'active_notifications',
            ]
            for ek in extra_keys:
                cleared_keys.append(ek)
                if not dry_run:
                    cache.delete(ek)
                self.stdout.write(f'  Extra: {ek}')

            # Clear all dashboard metric caches
            try:
                from api.admin_panel.models.dashboard import DashboardMetric
                periods = DashboardMetric.objects.values_list('period', flat=True).distinct()
                for period in periods:
                    dk = f'admin_panel:dashboard_stats:{period}'
                    cleared_keys.append(dk)
                    if not dry_run:
                        cache.delete(dk)
                    self.stdout.write(f'  Dashboard: {dk}')
            except Exception:
                pass

        total = len(cleared_keys)
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\nDRY RUN complete. Would clear {total} cache key(s).'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Cleared {total} cache key(s) successfully.'
            ))