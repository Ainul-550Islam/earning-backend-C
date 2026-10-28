# api/cms/adapters/payment_tenants.py
"""
Adapters for api.payment_gateways and api.tenants

  PaymentGatewayAdapter — payment initiation, status checks for CMS reward payouts
  TenantAdapter         — multi-tenant context, tenant-scoped content filtering
"""
import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List

from .base import BaseAdapter

logger = logging.getLogger('api.cms.adapters')


# ══════════════════════════════════════════════════════════════════════════════
# PAYMENT GATEWAY ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class PaymentGatewayAdapter(BaseAdapter):
    """CMS → api.payment_gateways interface."""

    _system_name = 'api.payment_gateways'

    @classmethod
    def _check_available(cls):
        import api.payment_gateways  # noqa

    @classmethod
    def initiate_payout(
        cls,
        user,
        amount_usd: Decimal,
        gateway: str,
        account_id: str,
        ref_id: str = '',
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """
        Initiate a payout via the given payment gateway.
        Returns {'success': bool, 'transaction_id': str, 'status': str}
        """
        try:
            from api.payment_gateways.services import PaymentGatewayService
            result = PaymentGatewayService.payout(
                user=user,
                amount=amount_usd,
                gateway=gateway,
                account_id=account_id,
                ref_id=ref_id,
                metadata=metadata or {},
            )
            return result or {'success': False, 'status': 'error'}
        except ImportError:
            return cls._unavailable('initiate_payout', {'success': False, 'status': 'unavailable'})
        except Exception as e:
            logger.error("[CMS→PaymentGateway] initiate_payout failed: %s", e)
            return {'success': False, 'status': 'error', 'reason': str(e)}

    @classmethod
    def get_transaction_status(cls, transaction_id: str) -> str:
        """Return transaction status: 'pending'|'completed'|'failed'|'unknown'."""
        try:
            from api.payment_gateways.services import PaymentGatewayService
            return PaymentGatewayService.get_status(transaction_id=transaction_id) or 'unknown'
        except ImportError:
            return 'unknown'
        except Exception as e:
            logger.warning("[CMS→PaymentGateway] get_transaction_status failed: %s", e)
            return 'unknown'

    @classmethod
    def get_available_gateways(cls) -> List[Dict]:
        """Return a list of configured, active payment gateways."""
        try:
            from api.payment_gateways.models import PaymentGateway
            gateways = PaymentGateway.objects.filter(is_active=True).values(
                'slug', 'name', 'logo_url', 'min_payout_usd', 'max_payout_usd',
            )
            return list(gateways)
        except ImportError:
            return cls._unavailable('get_available_gateways', [])
        except Exception as e:
            logger.warning("[CMS→PaymentGateway] get_available_gateways failed: %s", e)
            return []

    @classmethod
    def verify_account(cls, gateway: str, account_id: str) -> bool:
        """Verify that an account ID is valid for the given gateway."""
        try:
            from api.payment_gateways.services import PaymentGatewayService
            return PaymentGatewayService.verify_account(gateway=gateway, account_id=account_id)
        except ImportError:
            return True  # assume valid if gateway system not installed
        except Exception:
            return False

    @classmethod
    def get_fees(cls, gateway: str, amount_usd: Decimal) -> Decimal:
        """Calculate processing fees for a given gateway and amount."""
        try:
            from api.payment_gateways.services import PaymentGatewayService
            fee = PaymentGatewayService.calculate_fee(gateway=gateway, amount=amount_usd)
            return Decimal(str(fee or 0))
        except (ImportError, Exception):
            return Decimal('0')


# ══════════════════════════════════════════════════════════════════════════════
# TENANT ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class TenantAdapter(BaseAdapter):
    """CMS → api.tenants interface — multi-tenant content isolation."""

    _system_name = 'api.tenants'

    @classmethod
    def _check_available(cls):
        import api.tenants  # noqa

    @classmethod
    def get_current_tenant(cls, request=None) -> Optional[Dict]:
        """
        Resolve the current tenant from the request.
        Returns {'id': str, 'slug': str, 'name': str, 'domain': str} or None.
        """
        try:
            from api.tenants.middleware import get_current_tenant
            tenant = get_current_tenant(request)
            if tenant:
                return {
                    'id': str(tenant.pk),
                    'slug': getattr(tenant, 'slug', ''),
                    'name': getattr(tenant, 'name', ''),
                    'domain': getattr(tenant, 'domain', ''),
                }
            return None
        except ImportError:
            return None
        except Exception as e:
            logger.debug("[CMS→Tenants] get_current_tenant failed: %s", e)
            return None

    @classmethod
    def get_tenant_id(cls, request=None) -> str:
        """Return the current tenant ID string, or '' if not multi-tenant."""
        tenant = cls.get_current_tenant(request)
        return tenant.get('id', '') if tenant else ''

    @classmethod
    def filter_queryset_for_tenant(cls, qs, request=None):
        """
        Apply tenant filtering to a queryset if the model has a 'tenant' field.
        Returns qs unchanged if tenants unavailable or not multi-tenant.
        """
        try:
            tenant_id = cls.get_tenant_id(request)
            if tenant_id and hasattr(qs.model, 'tenant'):
                return qs.filter(tenant_id=tenant_id)
            return qs
        except Exception:
            return qs

    @classmethod
    def get_tenant_settings(cls, tenant_id: str) -> Dict:
        """Fetch per-tenant CMS settings (e.g. theme, feature flags)."""
        try:
            from api.tenants.models import TenantSettings
            settings = TenantSettings.objects.filter(tenant_id=tenant_id).first()
            return settings.settings_data if settings else {}
        except ImportError:
            return {}
        except Exception as e:
            logger.debug("[CMS→Tenants] get_tenant_settings failed: %s", e)
            return {}

    @classmethod
    def get_tenant_branding(cls, tenant_id: str) -> Dict:
        """Return branding config (logo, colors, custom CSS) for a tenant."""
        try:
            from api.tenants.models import TenantBranding
            branding = TenantBranding.objects.filter(tenant_id=tenant_id).first()
            if branding:
                return {
                    'logo_url': getattr(branding, 'logo_url', ''),
                    'primary_color': getattr(branding, 'primary_color', ''),
                    'custom_css': getattr(branding, 'custom_css', ''),
                }
            return {}
        except ImportError:
            return {}
        except Exception:
            return {}

    @classmethod
    def is_feature_enabled(cls, tenant_id: str, feature: str) -> bool:
        """Check if a specific feature is enabled for a tenant."""
        settings = cls.get_tenant_settings(tenant_id)
        features = settings.get('features', {})
        return features.get(feature, True)  # default: enabled
