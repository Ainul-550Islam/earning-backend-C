# api/admin_panel/management/commands/seed_feature_flags.py
"""Seed default FeatureFlag entries."""
from django.core.management.base import BaseCommand

DEFAULT_FLAGS = [
    ('referral_system', True, 100, 'Enable/disable referral system'),
    ('leaderboard', True, 100, 'Enable/disable leaderboard feature'),
    ('daily_bonus', True, 100, 'Enable/disable daily login bonus'),
    ('push_notifications', True, 100, 'Enable/disable push notifications'),
    ('two_factor_auth', False, 0, 'Enable/disable 2FA for users'),
    ('fraud_detection', True, 100, 'Enable/disable fraud detection'),
    ('vpn_block', False, 0, 'Block VPN users'),
    ('auto_withdrawal', False, 0, 'Auto-approve withdrawals below threshold'),
    ('social_sharing', True, 100, 'Enable social sharing buttons'),
    ('gamification', True, 100, 'Enable badges and achievements'),
    ('survey_tasks', True, 100, 'Enable survey task type'),
    ('api_rate_limiting', True, 100, 'Enable API rate limiting'),
    ('maintenance_mode', False, 0, 'Enable maintenance mode'),
    ('new_user_bonus', True, 100, 'Give welcome bonus to new users'),
    ('ad_network_cpalead', True, 100, 'Enable CPAlead ad network'),
]


class Command(BaseCommand):
    help = 'Seed default FeatureFlag entries.'

    def add_arguments(self, parser):
        parser.add_argument('--overwrite', action='store_true', help='Overwrite existing flags.')

    def handle(self, *args, **options):
        from api.admin_panel.models.config import FeatureFlag
        overwrite = options['overwrite']
        created = updated = skipped = 0

        for flag_key, is_enabled, rollout_pct, description in DEFAULT_FLAGS:
            exists = FeatureFlag.objects.filter(flag_key=flag_key).exists()
            if exists and not overwrite:
                skipped += 1
                continue
            obj, was_created = FeatureFlag.objects.update_or_create(
                flag_key=flag_key,
                defaults={
                    'label': flag_key.replace('_', ' ').title(),
                    'description': description,
                    'is_enabled': is_enabled,
                    'rollout_pct': rollout_pct,
                }
            )
            if was_created:
                created += 1
            else:
                updated += 1
            self.stdout.write(f'  {"✅" if is_enabled else "❌"} {flag_key} ({rollout_pct}%)')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Created: {created}, Updated: {updated}, Skipped: {skipped}'
        ))