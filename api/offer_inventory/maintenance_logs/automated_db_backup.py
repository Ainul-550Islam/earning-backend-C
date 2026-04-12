# api/offer_inventory/maintenance_logs/automated_db_backup.py
"""
Maintenance & Logs Package — all 10 modules.
Automated DB backup, cleanup service, system updates,
emergency shutdown, user feedback logger, API documentation,
security audit report, crash report handler, legacy API bridge, master switch.
"""
import logging
import json
import os
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════
# 1. AUTOMATED DB BACKUP
# ════════════════════════════════════════════════════════

class AutomatedDBBackup:
    """Scheduled database backup with retention management."""

    BACKUP_DIR        = '/tmp/backups'
    RETENTION_DAYS    = 30
    BACKUP_SCHEDULE   = 'daily'  # 'daily' | 'hourly' | 'weekly'

    @classmethod
    def run(cls, backup_type: str = 'db') -> dict:
        """Execute a database backup."""
        from api.offer_inventory.system_devops import BackupManager
        os.makedirs(cls.BACKUP_DIR, exist_ok=True)
        result = BackupManager.create_db_backup(destination=cls.BACKUP_DIR)
        logger.info(f'Automated backup: {result}')
        return result

    @classmethod
    def cleanup_old_backups(cls) -> int:
        """Remove backup files older than retention period."""
        cutoff = timezone.now() - timedelta(days=cls.RETENTION_DAYS)
        removed = 0
        try:
            for fname in os.listdir(cls.BACKUP_DIR):
                fpath = os.path.join(cls.BACKUP_DIR, fname)
                if os.path.isfile(fpath):
                    mtime = os.path.getmtime(fpath)
                    if mtime < cutoff.timestamp():
                        os.remove(fpath)
                        removed += 1
        except Exception as e:
            logger.error(f'Backup cleanup error: {e}')
        return removed

    @classmethod
    def get_backup_status(cls) -> dict:
        from api.offer_inventory.system_devops import BackupManager
        history = BackupManager.get_backup_history(limit=5)
        last    = history[0] if history else None
        return {
            'last_backup'    : last,
            'retention_days' : cls.RETENTION_DAYS,
            'backup_dir'     : cls.BACKUP_DIR,
            'total_history'  : len(history),
        }


# ════════════════════════════════════════════════════════
# 2. CLEANUP SERVICE
# ════════════════════════════════════════════════════════

class CleanupService:
    """Periodic cleanup of expired/stale data."""

    @staticmethod
    def run_all(dry_run: bool = False) -> dict:
        """Run all cleanup tasks."""
        results = {}

        # 1. Log rotation
        from api.offer_inventory.system_devops import LogRotator
        if not dry_run:
            results['log_rotation'] = LogRotator.rotate_all(days_to_keep=90)
        else:
            results['log_rotation'] = LogRotator.get_log_sizes()

        # 2. Expired cache objects
        results['cache_objects'] = CleanupService._cleanup_cache_objects(dry_run)

        # 3. Expired IP blocks
        results['expired_ip_blocks'] = CleanupService._cleanup_expired_ip_blocks(dry_run)

        # 4. Old conversion pixel logs
        results['pixel_logs'] = CleanupService._cleanup_pixel_logs(dry_run)

        # 5. Stale session data
        results['sdk_sessions'] = CleanupService._cleanup_sdk_sessions()

        total = sum(v if isinstance(v, int) else 0 for v in results.values())
        logger.info(f'Cleanup completed: {total} records affected')
        return results

    @staticmethod
    def _cleanup_cache_objects(dry_run: bool) -> int:
        from api.offer_inventory.models import CacheObject
        expired = CacheObject.objects.filter(expires_at__lt=timezone.now())
        count   = expired.count()
        if not dry_run:
            expired.delete()
        return count

    @staticmethod
    def _cleanup_expired_ip_blocks(dry_run: bool) -> int:
        from api.offer_inventory.security_fraud import IPBlacklistManager
        if not dry_run:
            return IPBlacklistManager.cleanup_expired()
        from api.offer_inventory.models import BlacklistedIP
        return BlacklistedIP.objects.filter(
            is_permanent=False, expires_at__lt=timezone.now()
        ).count()

    @staticmethod
    def _cleanup_pixel_logs(dry_run: bool) -> int:
        from api.offer_inventory.models import PixelLog
        cutoff  = timezone.now() - timedelta(days=30)
        expired = PixelLog.objects.filter(created_at__lt=cutoff, is_fired=True)
        count   = expired.count()
        if not dry_run:
            expired.delete()
        return count

    @staticmethod
    def _cleanup_sdk_sessions() -> int:
        """SDK sessions expire automatically in Redis — just log count."""
        return 0


# ════════════════════════════════════════════════════════
# 3. SYSTEM UPDATES
# ════════════════════════════════════════════════════════

class SystemUpdater:
    """Manage system configuration updates and migrations."""

    @staticmethod
    def update_system_setting(key: str, value: str, value_type: str = 'string',
                               description: str = '', tenant=None) -> object:
        """Update or create a system setting."""
        from api.offer_inventory.models import SystemSetting
        obj, created = SystemSetting.objects.update_or_create(
            key=key, tenant=tenant,
            defaults={
                'value'      : value,
                'value_type' : value_type,
                'description': description,
            }
        )
        cache.delete(f'setting:{key}:{tenant}')
        action = 'Created' if created else 'Updated'
        logger.info(f'{action} system setting: {key}={value}')
        return obj

    @staticmethod
    def get_system_setting(key: str, default=None, tenant=None):
        """Get a system setting value."""
        from api.offer_inventory.models import SystemSetting
        cache_key = f'setting:{key}:{tenant}'
        cached    = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            setting = SystemSetting.objects.get(key=key, tenant=tenant)
            val = setting.value
            if setting.value_type == 'int':
                val = int(val)
            elif setting.value_type == 'bool':
                val = val.lower() in ('true', '1', 'yes')
            elif setting.value_type == 'json':
                val = json.loads(val)
            cache.set(cache_key, val, 300)
            return val
        except Exception:
            return default

    @staticmethod
    def bulk_update_settings(settings_dict: dict, tenant=None) -> int:
        """Update multiple settings at once."""
        count = 0
        for key, value in settings_dict.items():
            SystemUpdater.update_system_setting(key, str(value), tenant=tenant)
            count += 1
        return count

    @staticmethod
    def run_post_update_tasks():
        """Tasks to run after a system update/deployment."""
        from api.offer_inventory.optimization_scale import QueryOptimizer
        from api.offer_inventory.system_devops import DBIndexer

        # Warm caches
        QueryOptimizer.warm_offer_cache()
        # Analyze tables
        DBIndexer.analyze_tables()
        logger.info('Post-update tasks completed')


# ════════════════════════════════════════════════════════
# 4. EMERGENCY SHUTDOWN
# ════════════════════════════════════════════════════════

class EmergencyShutdown:
    """
    Emergency shutdown controls.
    Gracefully disable platform features without downtime.
    """

    SHUTDOWN_KEY = 'emergency_shutdown'

    @classmethod
    def activate(cls, reason: str, activated_by_user=None,
                  disable_offers: bool = True,
                  disable_conversions: bool = True,
                  disable_withdrawals: bool = True) -> dict:
        """Activate emergency shutdown mode."""
        from api.offer_inventory.repository import FeatureFlagRepository

        disabled = []
        if disable_offers:
            FeatureFlagRepository.set_feature('offer_wall', False, user=activated_by_user)
            disabled.append('offer_wall')
        if disable_conversions:
            FeatureFlagRepository.set_feature('conversions', False, user=activated_by_user)
            disabled.append('conversions')
        if disable_withdrawals:
            FeatureFlagRepository.set_feature('withdrawals', False, user=activated_by_user)
            disabled.append('withdrawals')

        # Store shutdown record
        cache.set(cls.SHUTDOWN_KEY, {
            'active'      : True,
            'reason'      : reason,
            'activated_by': str(activated_by_user.id) if activated_by_user else 'system',
            'at'          : timezone.now().isoformat(),
            'disabled'    : disabled,
        }, 86400)

        logger.critical(f'EMERGENCY SHUTDOWN ACTIVATED: {reason} | disabled={disabled}')

        # Alert all channels
        from api.offer_inventory.notifications import SlackNotifier, EmailAlertSystem
        SlackNotifier().alert_system_error(f'EMERGENCY SHUTDOWN: {reason}')
        EmailAlertSystem.send_system_error_alert(f'EMERGENCY SHUTDOWN: {reason}')

        return {'activated': True, 'disabled': disabled, 'reason': reason}

    @classmethod
    def deactivate(cls, restored_by_user=None) -> dict:
        """Restore normal operations."""
        from api.offer_inventory.repository import FeatureFlagRepository

        FeatureFlagRepository.set_feature('offer_wall', True, user=restored_by_user)
        FeatureFlagRepository.set_feature('conversions', True, user=restored_by_user)
        FeatureFlagRepository.set_feature('withdrawals', True, user=restored_by_user)
        cache.delete(cls.SHUTDOWN_KEY)

        logger.info('Emergency shutdown deactivated — normal operations restored')
        return {'deactivated': True, 'at': timezone.now().isoformat()}

    @classmethod
    def get_status(cls) -> dict:
        """Get current shutdown status."""
        record = cache.get(cls.SHUTDOWN_KEY, {'active': False})
        return record


# ════════════════════════════════════════════════════════
# 5. USER FEEDBACK LOGGER
# ════════════════════════════════════════════════════════

class UserFeedbackLogger:
    """Log and analyze user feedback for product improvement."""

    @staticmethod
    def log(user, feedback_type: str, subject: str, message: str,
             rating: int = None) -> object:
        """Log user feedback."""
        from api.offer_inventory.models import UserFeedback
        return UserFeedback.objects.create(
            user         =user,
            feedback_type=feedback_type,
            subject      =subject,
            message      =message,
            rating       =rating,
        )

    @staticmethod
    def get_summary(days: int = 30) -> dict:
        """Feedback summary for the period."""
        from api.offer_inventory.models import UserFeedback
        from django.db.models import Count, Avg
        since = timezone.now() - timedelta(days=days)
        agg   = UserFeedback.objects.filter(created_at__gte=since).aggregate(
            total =Count('id'),
            avg_rating=Avg('rating'),
            bugs  =Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(feedback_type='bug')),
            features=Count('id', filter=__import__('django.db.models', fromlist=['Q']).Q(feedback_type='feature')),
        )
        return {
            'total'       : agg['total'],
            'avg_rating'  : round(float(agg['avg_rating'] or 0), 1),
            'bugs'        : agg['bugs'],
            'features'    : agg['features'],
            'period_days' : days,
        }

    @staticmethod
    def get_top_feature_requests(limit: int = 10) -> list:
        """Most requested features."""
        from api.offer_inventory.models import UserFeedback
        from django.db.models import Count
        return list(
            UserFeedback.objects.filter(feedback_type='feature')
            .values('subject')
            .annotate(count=Count('id'))
            .order_by('-count')[:limit]
        )


# ════════════════════════════════════════════════════════
# 6. API DOCUMENTATION
# ════════════════════════════════════════════════════════

class APIDocumentationManager:
    """Manage API documentation snippets and changelog."""

    @staticmethod
    def get_snippet(slug: str, language: str = 'en') -> dict:
        """Get a documentation snippet by slug."""
        from api.offer_inventory.models import DocumentationSnippet
        try:
            doc = DocumentationSnippet.objects.get(
                slug=slug, is_published=True, language=language
            )
            return {'title': doc.title, 'content': doc.content, 'category': doc.category}
        except DocumentationSnippet.DoesNotExist:
            return {'error': f'Documentation not found: {slug}'}

    @staticmethod
    def create_snippet(slug: str, title: str, content: str,
                        category: str = '', language: str = 'bn') -> object:
        """Create a documentation snippet."""
        from api.offer_inventory.models import DocumentationSnippet
        return DocumentationSnippet.objects.update_or_create(
            slug=slug,
            defaults={
                'title'      : title,
                'content'    : content,
                'category'   : category,
                'language'   : language,
                'is_published': True,
            }
        )[0]

    @staticmethod
    def get_api_changelog() -> list:
        """Get API changelog entries."""
        return [
            {'version': '2.0', 'date': '2025-01-01', 'changes': [
                'Added marketing/ module with campaigns, push, loyalty',
                'Added business/ module with KPI, billing, compliance',
                'Added affiliate_advanced/ with 12 modules',
                'Bulletproof conversion tracking with Redis locks',
                '100% Decimal financial calculations',
            ]},
            {'version': '1.5', 'date': '2024-07-01', 'changes': [
                'Added SmartLink AI (EPC × CVR × Availability)',
                'Added circuit breaker for offerwall integration',
                'IP whitelist + HMAC for postback security',
            ]},
            {'version': '1.0', 'date': '2024-01-01', 'changes': [
                'Initial release with 100 DB models',
                'Full offer lifecycle management',
                'Fraud detection and security modules',
            ]},
        ]


# ════════════════════════════════════════════════════════
# 7. SECURITY AUDIT REPORT
# ════════════════════════════════════════════════════════

class SecurityAuditReporter:
    """Generate security audit reports for compliance."""

    @staticmethod
    def generate_report(days: int = 30) -> dict:
        """Full security audit report."""
        from api.offer_inventory.models import (
            FraudAttempt, BlacklistedIP, SecurityIncident,
            HoneypotLog, UserRiskProfile, AuditLog,
        )
        since = timezone.now() - timedelta(days=days)

        return {
            'period'             : f'Last {days} days',
            'generated_at'       : timezone.now().isoformat(),
            'fraud_attempts'     : FraudAttempt.objects.filter(created_at__gte=since).count(),
            'ips_blocked'        : BlacklistedIP.objects.filter(created_at__gte=since).count(),
            'security_incidents' : SecurityIncident.objects.filter(created_at__gte=since).count(),
            'honeypot_triggers'  : HoneypotLog.objects.filter(created_at__gte=since).count(),
            'high_risk_users'    : UserRiskProfile.objects.filter(risk_level__in=['high', 'critical']).count(),
            'suspended_users'    : UserRiskProfile.objects.filter(is_suspended=True).count(),
            'admin_actions'      : AuditLog.objects.filter(
                created_at__gte=since,
                action__startswith='DELETE'
            ).count(),
            'top_fraud_countries': SecurityAuditReporter._top_fraud_countries(since),
        }

    @staticmethod
    def _top_fraud_countries(since) -> list:
        from api.offer_inventory.models import Click
        from django.db.models import Count
        return list(
            Click.objects.filter(is_fraud=True, created_at__gte=since)
            .exclude(country_code='')
            .values('country_code')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )


# ════════════════════════════════════════════════════════
# 8. CRASH REPORT HANDLER
# ════════════════════════════════════════════════════════

class CrashReportHandler:
    """Handle application crashes and critical errors."""

    @staticmethod
    def capture_exception(exc: Exception, context: dict = None, request=None):
        """Capture and log an exception."""
        import traceback
        from api.offer_inventory.reporting_audit import ErrorTracker
        from api.offer_inventory.notifications import SlackNotifier

        tb = traceback.format_exc()
        ErrorTracker.log(
            level='critical',
            message=str(exc)[:1000],
            traceback=tb,
            request=request,
        )

        # Alert Slack for critical errors
        if 'database' in str(exc).lower() or 'timeout' in str(exc).lower():
            SlackNotifier().alert_system_error(
                f'Critical: {type(exc).__name__}: {str(exc)[:200]}'
            )

        logger.critical(f'Crash captured: {type(exc).__name__}: {exc}', exc_info=True)

    @staticmethod
    def get_crash_summary(hours: int = 24) -> dict:
        from api.offer_inventory.reporting_audit import ErrorTracker
        return {
            'error_summary': ErrorTracker.get_error_summary(hours=hours),
            'top_errors'   : ErrorTracker.get_top_errors(limit=5),
            'period_hours' : hours,
        }


# ════════════════════════════════════════════════════════
# 9. LEGACY API BRIDGE
# ════════════════════════════════════════════════════════

class LegacyAPIBridge:
    """
    Backward compatibility bridge for older API clients.
    Maps v1 API calls to v2 equivalents.
    """

    V1_TO_V2_MAP = {
        '/api/offers/'          : '/api/offer-inventory/offers/',
        '/api/conversions/'     : '/api/offer-inventory/conversions/',
        '/api/withdrawals/'     : '/api/offer-inventory/withdrawals/',
        '/api/postback/'        : '/api/offer-inventory/postback/',
    }

    @classmethod
    def get_v2_url(cls, v1_url: str) -> str:
        """Map a v1 URL to its v2 equivalent."""
        for v1, v2 in cls.V1_TO_V2_MAP.items():
            if v1_url.startswith(v1):
                return v1_url.replace(v1, v2, 1)
        return v1_url

    @classmethod
    def transform_v1_offer(cls, v1_offer: dict) -> dict:
        """Transform v1 offer format to v2."""
        return {
            'id'           : v1_offer.get('offer_id') or v1_offer.get('id'),
            'title'        : v1_offer.get('offer_name') or v1_offer.get('title'),
            'reward_amount': v1_offer.get('currency') or v1_offer.get('reward_amount', 0),
            'offer_url'    : v1_offer.get('offer_url') or v1_offer.get('url'),
            'status'       : 'active',
        }

    @classmethod
    def handle_v1_postback(cls, params: dict) -> dict:
        """Handle postback in v1 format."""
        # Map v1 params to v2 standard
        mapped = {
            'click_id'      : params.get('snuid') or params.get('click_id', ''),
            'transaction_id': params.get('verifier') or params.get('transaction_id', ''),
            'payout'        : params.get('currency') or params.get('payout', 0),
            'status'        : 'approved',
        }
        return mapped


# ════════════════════════════════════════════════════════
# 10. MASTER SWITCH (Maintenance Mode Controller)
# ════════════════════════════════════════════════════════

class MasterSwitchController:
    """
    Global feature flag management.
    Toggle any platform feature on/off without deployment.
    """

    CORE_FEATURES = [
        'offer_wall',
        'conversions',
        'withdrawals',
        'referral',
        'kyc',
        'marketing_emails',
        'push_notifications',
        'analytics_tracking',
        'fraud_detection',
        'smartlink',
    ]

    @classmethod
    def toggle_feature(cls, feature: str, enabled: bool,
                        tenant=None, user=None) -> dict:
        """Toggle a feature on or off."""
        from api.offer_inventory.repository import FeatureFlagRepository
        obj = FeatureFlagRepository.set_feature(feature, enabled, tenant, user)
        action = 'ENABLED' if enabled else 'DISABLED'
        logger.info(f'Feature {action}: {feature} | tenant={tenant} | by={user}')
        return {
            'feature': feature,
            'enabled': enabled,
            'tenant' : str(tenant.id) if tenant else None,
        }

    @classmethod
    def get_all_features(cls, tenant=None) -> list:
        """Get status of all features."""
        from api.offer_inventory.repository import FeatureFlagRepository
        return [
            {
                'feature': f,
                'enabled': FeatureFlagRepository.is_enabled(f, tenant),
            }
            for f in cls.CORE_FEATURES
        ]

    @classmethod
    def disable_all_non_essential(cls, tenant=None, user=None) -> list:
        """Disable all non-essential features (maintenance mode)."""
        non_essential = [
            'marketing_emails', 'push_notifications',
            'referral', 'smartlink', 'analytics_tracking',
        ]
        disabled = []
        for feature in non_essential:
            cls.toggle_feature(feature, False, tenant, user)
            disabled.append(feature)
        return disabled

    @classmethod
    def restore_all_features(cls, tenant=None, user=None) -> list:
        """Re-enable all features."""
        restored = []
        for feature in cls.CORE_FEATURES:
            cls.toggle_feature(feature, True, tenant, user)
            restored.append(feature)
        return restored
