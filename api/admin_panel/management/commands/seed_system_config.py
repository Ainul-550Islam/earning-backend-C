# api/admin_panel/management/commands/seed_system_config.py
"""Seed default SystemConfig entries for CPAlead-style earning platform."""
from django.core.management.base import BaseCommand


DEFAULT_CONFIGS = [
    # Earning
    ('referral_bonus_points', '500', 'integer', 'earning', 'Referral Bonus Points'),
    ('daily_login_bonus', '50', 'integer', 'earning', 'Daily Login Bonus Points'),
    ('welcome_bonus_points', '1000', 'integer', 'earning', 'Welcome Bonus Points'),
    ('ad_click_points', '10', 'integer', 'earning', 'Points Per Ad Click'),
    ('video_watch_points', '50', 'integer', 'earning', 'Points Per Video Watch'),
    ('task_complete_points', '75', 'integer', 'earning', 'Points Per Task Completion'),
    ('survey_complete_points', '100', 'integer', 'earning', 'Points Per Survey'),
    ('point_value', '0.01', 'float', 'earning', 'Point Value (in BDT)'),
    # Payment
    ('min_withdrawal_amount', '100', 'float', 'payment', 'Minimum Withdrawal Amount'),
    ('max_withdrawal_amount', '10000', 'float', 'payment', 'Maximum Withdrawal Amount'),
    ('withdrawal_fee_percentage', '2.5', 'float', 'payment', 'Withdrawal Fee %'),
    ('withdrawal_cooldown_hours', '24', 'integer', 'payment', 'Withdrawal Cooldown Hours'),
    # Security
    ('max_accounts_per_ip', '3', 'integer', 'security', 'Max Accounts Per IP'),
    ('max_daily_ads', '100', 'integer', 'security', 'Max Daily Ads Per User'),
    ('min_ad_watch_time', '30', 'integer', 'security', 'Min Ad Watch Time (seconds)'),
    ('suspicious_click_speed', '5', 'integer', 'security', 'Suspicious Click Speed'),
    # Referral
    ('referral_percentage_level1', '10.0', 'float', 'referral', 'Referral Commission Level 1 %'),
    ('referral_percentage_level2', '5.0', 'float', 'referral', 'Referral Commission Level 2 %'),
    ('referral_percentage_level3', '2.5', 'float', 'referral', 'Referral Commission Level 3 %'),
    ('referral_levels', '3', 'integer', 'referral', 'Referral Levels'),
    # General
    ('site_name', 'Earning Platform', 'string', 'general', 'Site Name'),
    ('currency_code', 'BDT', 'string', 'general', 'Currency Code'),
    ('currency_symbol', '৳', 'string', 'general', 'Currency Symbol'),
    ('log_retention_days', '30', 'integer', 'general', 'Log Retention Days'),
    ('cache_timeout', '300', 'integer', 'general', 'Default Cache Timeout (seconds)'),
    # API
    ('api_rate_limit_per_minute', '60', 'integer', 'api', 'API Rate Limit Per Minute'),
    ('api_rate_limit_per_hour', '1000', 'integer', 'api', 'API Rate Limit Per Hour'),
]


class Command(BaseCommand):
    help = 'Seed default SystemConfig entries for the earning platform.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite', action='store_true',
            help='Overwrite existing config values.'
        )

    def handle(self, *args, **options):
        from api.admin_panel.models.config import SystemConfig
        overwrite = options['overwrite']
        created = 0
        skipped = 0

        for key, value, value_type, group, label in DEFAULT_CONFIGS:
            exists = SystemConfig.objects.filter(key=key).exists()
            if exists and not overwrite:
                skipped += 1
                continue
            SystemConfig.objects.update_or_create(
                key=key,
                defaults={
                    'value': value,
                    'value_type': value_type,
                    'group': group,
                    'label': label,
                    'is_public': group in ('general',),
                }
            )
            created += 1
            self.stdout.write(f'  {"Updated" if exists else "Created"}: {key} = {value}')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Created/Updated: {created}, Skipped: {skipped}'
        ))