# api/offer_inventory/maintenance_logs/master_switch.py
"""Master Switch Controller — Global feature flag management."""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

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


class MasterSwitchController:
    """Toggle any platform feature on/off without deployment."""

    @classmethod
    def toggle(cls, feature: str, enabled: bool,
                tenant=None, user=None) -> dict:
        """Toggle a feature on or off."""
        if feature not in CORE_FEATURES:
            raise ValueError(f'Unknown feature: {feature}. Available: {CORE_FEATURES}')

        from api.offer_inventory.repository import FeatureFlagRepository
        FeatureFlagRepository.set_feature(feature, enabled, tenant, user)

        action = 'ENABLED' if enabled else 'DISABLED'
        logger.info(
            f'Feature {action}: {feature} | tenant={tenant} | by={user}'
        )
        return {
            'feature': feature,
            'enabled': enabled,
            'tenant' : str(tenant.id) if tenant else None,
            'changed_at': timezone.now().isoformat(),
        }

    @classmethod
    def get_all(cls, tenant=None) -> list:
        """Get status of all core features."""
        from api.offer_inventory.repository import FeatureFlagRepository
        return [
            {
                'feature': f,
                'enabled': FeatureFlagRepository.is_enabled(f, tenant),
            }
            for f in CORE_FEATURES
        ]

    @classmethod
    def disable_non_essential(cls, tenant=None, user=None) -> list:
        """Disable all non-essential features (maintenance mode)."""
        non_essential = [
            'marketing_emails', 'push_notifications',
            'referral', 'smartlink', 'analytics_tracking',
        ]
        disabled = []
        for f in non_essential:
            cls.toggle(f, False, tenant, user)
            disabled.append(f)
        logger.warning(f'Non-essential features disabled: {disabled}')
        return disabled

    @classmethod
    def enable_all(cls, tenant=None, user=None) -> list:
        """Re-enable all core features (end of maintenance)."""
        restored = []
        for f in CORE_FEATURES:
            cls.toggle(f, True, tenant, user)
            restored.append(f)
        logger.info(f'All features restored: {restored}')
        return restored

    @classmethod
    def get_disabled_features(cls, tenant=None) -> list:
        """List only currently disabled features."""
        return [
            item['feature']
            for item in cls.get_all(tenant)
            if not item['enabled']
        ]
