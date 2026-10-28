# api/referral/plugins.py
# Plugin extension system — third-party integrations
# Register external services (Segment, Mixpanel, AppsFlyer, etc.)
# ============================================================

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReferralPlugin:
    """Base class for referral plugins."""
    name: str = 'unnamed'
    version: str = '1.0.0'
    enabled: bool = True

    def on_referral_created(self, referrer, referred_user, referral) -> None: pass
    def on_commission_paid(self, user, amount, level, from_user) -> None: pass
    def on_milestone_reached(self, user, milestone_value, bonus) -> None: pass
    def on_fraud_detected(self, referral, fraud_score) -> None: pass
    def on_signup(self, new_user, referral_code) -> None: pass


class PluginRegistry:
    """Central registry for all referral plugins."""
    _plugins: Dict[str, ReferralPlugin] = {}

    @classmethod
    def register(cls, plugin: ReferralPlugin) -> None:
        cls._plugins[plugin.name] = plugin
        logger.info(f'[Plugins] Registered: {plugin.name} v{plugin.version}')

    @classmethod
    def unregister(cls, name: str) -> bool:
        if name in cls._plugins:
            del cls._plugins[name]
            return True
        return False

    @classmethod
    def fire(cls, event: str, **kwargs) -> None:
        for plugin in cls._plugins.values():
            if not plugin.enabled:
                continue
            handler = getattr(plugin, event, None)
            if callable(handler):
                try:
                    handler(**kwargs)
                except Exception as e:
                    logger.warning(f'[Plugins] {plugin.name}.{event} failed: {e}')

    @classmethod
    def list_plugins(cls) -> List[Dict]:
        return [
            {'name': p.name, 'version': p.version, 'enabled': p.enabled}
            for p in cls._plugins.values()
        ]


# ── Built-in Plugins ──────────────────────────────────────────────────────────

class DjoyaltyPlugin(ReferralPlugin):
    """Sends loyalty points to api/djoyalty when referral created."""
    name = 'djoyalty'
    version = '1.0.0'

    def on_referral_created(self, referrer, referred_user, referral) -> None:
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_adapter import DjoyaltyAdapter
            DjoyaltyAdapter.award_referral_points(referrer=referrer, referee=referred_user)
        except Exception as e:
            logger.debug(f'[Plugin:djoyalty] failed: {e}')


class AnalyticsPlugin(ReferralPlugin):
    """Tracks referral events in api/analytics."""
    name = 'analytics'
    version = '1.0.0'

    def on_referral_created(self, referrer, referred_user, referral) -> None:
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_adapter import AnalyticsAdapter
            AnalyticsAdapter.track_referral_created(referrer, referred_user)
        except Exception as e:
            logger.debug(f'[Plugin:analytics] on_referral_created failed: {e}')

    def on_commission_paid(self, user, amount, level, from_user) -> None:
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_adapter import AnalyticsAdapter
            AnalyticsAdapter.track_commission_paid(user, amount, level)
        except Exception as e:
            logger.debug(f'[Plugin:analytics] on_commission_paid failed: {e}')


class AuditPlugin(ReferralPlugin):
    """Writes all events to api/audit_logs."""
    name = 'audit'
    version = '1.0.0'

    def on_commission_paid(self, user, amount, level, from_user) -> None:
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_audit_logs import ReferralAuditLogger
            ReferralAuditLogger.log_commission_paid(
                referrer_username=user.username,
                earner=from_user,
                amount=float(amount),
                level=level,
                source='plugin_event',
            )
        except Exception:
            pass

    def on_fraud_detected(self, referral, fraud_score) -> None:
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_audit_logs import ReferralAuditLogger
            ReferralAuditLogger.log_fraud_flagged(
                referral_id=referral.id,
                fraud_score=fraud_score,
                flags=[],
            )
        except Exception:
            pass


def setup_default_plugins() -> None:
    """Register all default plugins. Called from apps.py ready()."""
    PluginRegistry.register(DjoyaltyPlugin())
    PluginRegistry.register(AnalyticsPlugin())
    PluginRegistry.register(AuditPlugin())
    logger.info(f'[Plugins] Default plugins: {[p["name"] for p in PluginRegistry.list_plugins()]}')