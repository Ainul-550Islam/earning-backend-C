# api/admin_panel/system_initializer.py
"""First-run system initialization — seeds DB with required defaults."""
from __future__ import annotations
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class SystemInitializer:
    """Initialize the platform on first run."""

    @classmethod
    def run(cls, superuser_username: str = 'admin',
            superuser_email: str = 'admin@example.com',
            superuser_password: str = 'ChangeMe123!',
            verbose: bool = True) -> Dict:
        """Run full initialization sequence."""
        results = {'steps': [], 'errors': []}

        steps = [
            ('check_migrations',      cls._check_migrations),
            ('seed_system_config',    cls._seed_system_config),
            ('seed_feature_flags',    cls._seed_feature_flags),
            ('seed_email_templates',  cls._seed_email_templates),
            ('seed_endpoint_toggles', cls._seed_endpoint_toggles),
            ('create_superuser',      lambda: cls._create_superuser(superuser_username, superuser_email, superuser_password)),
            ('warm_caches',           cls._warm_caches),
            ('check_health',          cls._check_health),
        ]

        for step_name, fn in steps:
            try:
                fn()
                results['steps'].append({'step': step_name, 'status': 'ok'})
                if verbose:
                    logger.info(f"[SystemInit] ✅ {step_name}")
            except Exception as e:
                results['errors'].append({'step': step_name, 'error': str(e)})
                if verbose:
                    logger.error(f"[SystemInit] ❌ {step_name}: {e}")

        results['ok'] = len(results['errors']) == 0
        results['initialized_at'] = timezone.now().isoformat()
        return results

    @classmethod
    def _check_migrations(cls):
        from django.db import connection
        with connection.cursor() as c:
            c.execute("SELECT 1 FROM django_migrations LIMIT 1")

    @classmethod
    def _seed_system_config(cls):
        from api.admin_panel.models.config import SystemConfig
        defaults = [
            ('site_name', 'Earning Platform', 'string', 'general'),
            ('min_payout_amount', '10', 'float', 'finance'),
            ('daily_withdrawal_limit', '50000', 'float', 'finance'),
            ('max_single_payout', '10000', 'float', 'finance'),
            ('payout_min_account_age_days', '3', 'integer', 'finance'),
            ('kyc_required_for_payout', 'false', 'boolean', 'finance'),
            ('welcome_bonus', '0', 'integer', 'promotions'),
            ('referral_commission_rate', '5', 'float', 'promotions'),
            ('task_complete_points', '10', 'integer', 'loyalty'),
            ('points_per_bdt', '10', 'integer', 'loyalty'),
        ]
        for key, val, vtype, group in defaults:
            SystemConfig.objects.get_or_create(
                key=key,
                defaults={'value': val, 'value_type': vtype, 'group': group}
            )

    @classmethod
    def _seed_feature_flags(cls):
        from api.admin_panel.models.config import FeatureFlag
        flags = [
            ('daily_payout', True, 'Enable daily payout processing'),
            ('referral_system', True, 'Multi-level referral system'),
            ('content_locker', True, 'CPAlead-style content locker'),
            ('offerwall', True, 'Offerwall monetization'),
            ('rtb_marketplace', True, 'Real-time bidding marketplace'),
            ('ai_fraud_detection', True, 'ML-based fraud detection'),
            ('websocket_dashboard', True, 'Real-time WebSocket dashboard'),
            ('admin_2fa', False, 'Two-factor authentication for admin'),
            ('openai_admin', False, 'OpenAI AI features'),
            ('push_notifications', True, 'FCM push notifications'),
            ('kyc_auto_approve', False, 'Auto-approve low-risk KYC'),
        ]
        for key, enabled, desc in flags:
            FeatureFlag.objects.get_or_create(
                flag_key=key,
                defaults={'is_enabled': enabled, 'label': key.replace('_', ' ').title(),
                          'description': desc, 'rollout_pct': 100}
            )

    @classmethod
    def _seed_email_templates(cls):
        from api.admin_panel.models.config import EmailTemplate
        templates = [
            ('withdrawal_approved', 'Withdrawal Approved', 'Your withdrawal has been approved.'),
            ('kyc_approved', 'Identity Verified', 'Your identity has been verified.'),
            ('maintenance_notice', 'Maintenance Notice', 'Scheduled maintenance upcoming.'),
            ('welcome', 'Welcome!', 'Welcome to the platform!'),
            ('admin_digest', 'Daily Admin Digest', 'Your daily platform summary.'),
        ]
        for key, subject, body in templates:
            EmailTemplate.objects.get_or_create(
                template_key=key,
                defaults={'subject': subject, 'body_text': body}
            )

    @classmethod
    def _seed_endpoint_toggles(cls):
        pass  # Done by seed_webhook_toggles management command

    @classmethod
    def _create_superuser(cls, username, email, password):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username=username, email=email, password=password)
            logger.info(f"[SystemInit] Superuser created: {username}")
        else:
            logger.info(f"[SystemInit] Superuser already exists: {username}")

    @classmethod
    def _warm_caches(cls):
        from api.admin_panel.caching import cache_manager
        cache_manager.warm_up()

    @classmethod
    def _check_health(cls):
        from api.admin_panel.INTEGRATION_SYSTEM.health_check import HealthCheck
        result = HealthCheck.check_all()
        if result.get('overall') == 'down':
            raise RuntimeError(f"Health check failed: {result}")


from typing import Dict
system_initializer = SystemInitializer()