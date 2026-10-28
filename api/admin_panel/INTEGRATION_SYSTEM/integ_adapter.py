# api/admin_panel/INTEGRATION_SYSTEM/integ_adapter.py
"""
BaseIntegrationAdapter — Abstract base for all app adapters.

Every app that integrates with admin_panel MUST implement this interface.
Provides: read, write, action, health_check, bulk operations.

Example:
    class WalletAdapter(BaseIntegrationAdapter):
        app_name = 'wallet'
        capabilities = ['read', 'write', 'adjust', 'freeze']

        def read(self, resource, filters=None, **kwargs):
            from api.wallet.models import Wallet
            return list(Wallet.objects.filter(**filters or {}).values()[:100])

        def action(self, action_name, payload, **kwargs):
            if action_name == 'adjust_balance':
                ...
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from django.utils import timezone
from .integ_constants import HEALTH_STATUSES

logger = logging.getLogger(__name__)


class AdapterResponse:
    """Standard response wrapper for all adapter operations."""

    def __init__(
        self,
        success: bool,
        data: Any = None,
        error: Optional[str] = None,
        meta: Optional[Dict] = None,
    ):
        self.success = success
        self.data = data
        self.error = error
        self.meta = meta or {}
        self.timestamp = timezone.now()

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error,
            'meta': self.meta,
            'timestamp': self.timestamp.isoformat(),
        }

    @classmethod
    def ok(cls, data=None, meta=None) -> 'AdapterResponse':
        return cls(success=True, data=data, meta=meta)

    @classmethod
    def fail(cls, error: str, data=None) -> 'AdapterResponse':
        return cls(success=False, error=error, data=data)


class BaseIntegrationAdapter(ABC):
    """
    Abstract base class for all integration adapters.
    All 50 apps use this interface for admin_panel control.
    """

    app_name: str = ''
    capabilities: List[str] = ['read']
    version: str = '1.0.0'
    description: str = ''

    def __init__(self):
        self._last_call = None
        self._call_count = 0
        self._error_count = 0

    # ==================== REQUIRED METHODS ====================

    def health_check(self) -> str:
        """
        Check if the app/service is healthy.
        Returns: 'healthy' | 'degraded' | 'down'
        """
        try:
            self._verify_app_available()
            return HEALTH_STATUSES['HEALTHY']
        except Exception:
            return HEALTH_STATUSES['DOWN']

    def read(
        self,
        resource: str,
        filters: Optional[Dict] = None,
        fields: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: Optional[str] = None,
        **kwargs,
    ) -> AdapterResponse:
        """Read data from the app. Override in each adapter."""
        raise NotImplementedError(f"{self.__class__.__name__}.read() not implemented")

    def write(
        self,
        resource: str,
        data: Dict,
        method: str = 'create',  # create | update | patch
        pk: Optional[Any] = None,
        **kwargs,
    ) -> AdapterResponse:
        """Write data to the app. Override if 'write' in capabilities."""
        raise NotImplementedError(f"{self.__class__.__name__}.write() not implemented")

    def delete(
        self,
        resource: str,
        pk: Any,
        soft_delete: bool = True,
        **kwargs,
    ) -> AdapterResponse:
        """Delete a record. Override if 'delete' in capabilities."""
        raise NotImplementedError(f"{self.__class__.__name__}.delete() not implemented")

    def action(
        self,
        action_name: str,
        payload: Optional[Dict] = None,
        **kwargs,
    ) -> AdapterResponse:
        """Execute a named action. Override with app-specific actions."""
        raise NotImplementedError(
            f"{self.__class__.__name__}.action('{action_name}') not implemented"
        )

    def bulk_action(
        self,
        action_name: str,
        ids: List[Any],
        payload: Optional[Dict] = None,
        **kwargs,
    ) -> AdapterResponse:
        """Execute an action on multiple records."""
        results = []
        errors = []
        for pk in ids:
            try:
                resp = self.action(action_name, payload={**(payload or {}), 'pk': pk}, **kwargs)
                results.append({'pk': pk, 'success': resp.success})
                if not resp.success:
                    errors.append({'pk': pk, 'error': resp.error})
            except Exception as e:
                errors.append({'pk': pk, 'error': str(e)})
        return AdapterResponse.ok(
            data={'processed': len(results), 'errors': errors},
            meta={'action': action_name, 'total_ids': len(ids)},
        )

    def stats(self, period: str = 'daily', **kwargs) -> AdapterResponse:
        """Get app statistics."""
        return AdapterResponse.fail(f"{self.app_name} stats() not implemented")

    # ==================== UTILITY METHODS ====================

    def _verify_app_available(self):
        """Check if the app's models are importable."""
        import importlib
        importlib.import_module(f'api.{self.app_name}')

    def _get_model(self, model_name: str):
        """Dynamic model loader."""
        import importlib
        try:
            module = importlib.import_module(f'api.{self.app_name}.models')
            return getattr(module, model_name)
        except (ImportError, AttributeError):
            try:
                module = importlib.import_module(f'api.{self.app_name}.models.{model_name.lower()}')
                return getattr(module, model_name)
            except (ImportError, AttributeError) as e:
                raise ImportError(f"Cannot find model {model_name} in {self.app_name}: {e}")

    def _track_call(self, success: bool = True):
        self._last_call = timezone.now()
        self._call_count += 1
        if not success:
            self._error_count += 1

    def get_capabilities(self) -> List[str]:
        return self.capabilities

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} app={self.app_name} caps={self.capabilities}>"


# ==================== BUILT-IN ADAPTERS ====================

class WalletAdapter(BaseIntegrationAdapter):
    app_name = 'wallet'
    capabilities = ['read', 'write', 'adjust', 'freeze']
    description = 'User wallet balance, transactions, adjustments'

    def read(self, resource='wallet', filters=None, limit=100, **kwargs) -> AdapterResponse:
        try:
            from api.wallet.models import Wallet
            qs = Wallet.objects.filter(**(filters or {}))
            data = list(qs.values()[:limit])
            return AdapterResponse.ok(data=data, meta={'count': len(data)})
        except Exception as e:
            return AdapterResponse.fail(str(e))

    def action(self, action_name, payload=None, **kwargs) -> AdapterResponse:
        payload = payload or {}
        if action_name == 'adjust_balance':
            try:
                from api.wallet.models import Wallet
                wallet = Wallet.objects.get(user_id=payload['user_id'])
                wallet.current_balance += payload['amount']
                wallet.save(update_fields=['balance'])
                return AdapterResponse.ok(data={'new_balance': float(wallet.current_balance)})
            except Exception as e:
                return AdapterResponse.fail(str(e))
        if action_name == 'freeze':
            try:
                from api.wallet.models import Wallet
                Wallet.objects.filter(user_id=payload['user_id']).update(is_locked=True)
                return AdapterResponse.ok()
            except Exception as e:
                return AdapterResponse.fail(str(e))
        return AdapterResponse.fail(f"Unknown action: {action_name}")


class UserAdapter(BaseIntegrationAdapter):
    app_name = 'users'
    capabilities = ['read', 'write', 'ban', 'verify', 'bulk']
    description = 'User management — ban, verify, profile, login history'

    def read(self, resource='user', filters=None, limit=100, **kwargs) -> AdapterResponse:
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            qs = User.objects.filter(**(filters or {}))
            data = list(qs.values('id', 'username', 'email', 'is_active', 'date_joined')[:limit])
            return AdapterResponse.ok(data=data, meta={'total': qs.count()})
        except Exception as e:
            return AdapterResponse.fail(str(e))

    def action(self, action_name, payload=None, **kwargs) -> AdapterResponse:
        payload = payload or {}
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if action_name == 'ban':
            try:
                User.objects.filter(pk=payload['user_id']).update(is_active=False)
                return AdapterResponse.ok(data={'banned': True})
            except Exception as e:
                return AdapterResponse.fail(str(e))
        if action_name == 'unban':
            try:
                User.objects.filter(pk=payload['user_id']).update(is_active=True)
                return AdapterResponse.ok(data={'unbanned': True})
            except Exception as e:
                return AdapterResponse.fail(str(e))
        return AdapterResponse.fail(f"Unknown action: {action_name}")


class FraudAdapter(BaseIntegrationAdapter):
    app_name = 'fraud_detection'
    capabilities = ['read', 'write', 'block_ip', 'update_settings']
    description = 'Fraud rules, risk scoring, IP blocking'

    def read(self, resource='fraud_rule', filters=None, limit=100, **kwargs) -> AdapterResponse:
        try:
            from api.fraud_detection.models import FraudRule
            data = list(FraudRule.objects.filter(**(filters or {})).values()[:limit])
            return AdapterResponse.ok(data=data)
        except Exception as e:
            return AdapterResponse.fail(str(e))

    def action(self, action_name, payload=None, **kwargs) -> AdapterResponse:
        payload = payload or {}
        if action_name == 'block_ip':
            try:
                from api.fraud_detection.models import BlockedIP
                obj, created = BlockedIP.objects.get_or_create(
                    ip_address=payload['ip'],
                    defaults={'reason': payload.get('reason', 'Admin block')}
                )
                return AdapterResponse.ok(data={'created': created})
            except Exception as e:
                return AdapterResponse.fail(str(e))
        return AdapterResponse.fail(f"Unknown action: {action_name}")


# Registry of all built-in adapters
BUILTIN_ADAPTERS = {
    'wallet': WalletAdapter,
    'users': UserAdapter,
    'fraud_detection': FraudAdapter,
}