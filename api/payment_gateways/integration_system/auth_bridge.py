# api/payment_gateways/integration_system/auth_bridge.py
# Cross-module permission checking — unified auth across all payment_gateways sub-modules

from typing import Optional
import logging
from .integ_exceptions import AuthBridgeError

logger = logging.getLogger(__name__)


class AuthBridge:
    """
    Cross-module permission checking for payment_gateways.

    Centralizes all permission logic so sub-modules don't need to
    duplicate auth checks.

    Integrates with:
        - Django's built-in permission system
        - Your api.users permission model
        - Publisher/Advertiser role checks
        - KYC verification status
        - Account suspension status

    Usage:
        auth = AuthBridge()
        auth.require_permission(user, 'can_withdraw')
        auth.require_publisher(user)
        auth.require_kyc(user)
    """

    # Permission constants
    CAN_DEPOSIT        = 'payment_gateways.can_deposit'
    CAN_WITHDRAW       = 'payment_gateways.can_withdraw'
    CAN_VIEW_ANALYTICS = 'payment_gateways.view_analytics'
    CAN_MANAGE_OFFERS  = 'payment_gateways.manage_offers'
    CAN_MANAGE_GATEWAY = 'payment_gateways.manage_gateway'
    IS_PUBLISHER       = 'payment_gateways.is_publisher'
    IS_ADVERTISER      = 'payment_gateways.is_advertiser'

    def check(self, user, permission: str) -> bool:
        """Check if user has a specific permission. Returns bool (no raise)."""
        try:
            return self._check_permission(user, permission)
        except Exception as e:
            logger.warning(f'AuthBridge.check failed: {e}')
            return False

    def require(self, user, permission: str):
        """Check permission and raise AuthBridgeError if denied."""
        if not self.check(user, permission):
            raise AuthBridgeError(user, permission)

    def require_active(self, user):
        """Require user account is active and not banned."""
        if not user or not user.is_active:
            raise AuthBridgeError(user, 'active_account')
        if getattr(user, 'is_banned', False):
            raise AuthBridgeError(user, 'not_banned')

    def require_publisher(self, user):
        """Require user has an active publisher profile."""
        self.require_active(user)
        try:
            from api.payment_gateways.publisher.models import PublisherProfile
            profile = PublisherProfile.objects.get(user=user)
            if profile.status != 'active':
                raise AuthBridgeError(user, f'publisher_active (status={profile.status})')
        except AuthBridgeError:
            raise
        except Exception:
            # If publisher profile doesn't exist — check your api.publisher_tools
            try:
                from api.publisher_tools.models import Publisher
                Publisher.objects.get(user=user, is_active=True)
            except Exception:
                raise AuthBridgeError(user, 'publisher_profile')

    def require_advertiser(self, user):
        """Require user has an active advertiser profile."""
        self.require_active(user)
        try:
            from api.payment_gateways.publisher.models import AdvertiserProfile
            profile = AdvertiserProfile.objects.get(user=user)
            if profile.status != 'active':
                raise AuthBridgeError(user, f'advertiser_active (status={profile.status})')
        except AuthBridgeError:
            raise
        except Exception:
            try:
                from api.advertiser_portal.models import Advertiser
                Advertiser.objects.get(user=user, is_active=True)
            except Exception:
                raise AuthBridgeError(user, 'advertiser_profile')

    def require_kyc(self, user, level: int = 1):
        """Require KYC verification at minimum level."""
        try:
            bridge = __import__(
                'api.payment_gateways.integration_system.data_bridge',
                fromlist=['DataBridgeSync']
            ).DataBridgeSync()
            kyc = bridge.pull_kyc_status(user)
            if not kyc.get('is_verified', False):
                raise AuthBridgeError(user, f'kyc_level_{level}')
        except AuthBridgeError:
            raise
        except Exception:
            pass  # KYC not enforced if module unavailable

    def require_sufficient_balance(self, user, amount):
        """Require user has sufficient balance for withdrawal."""
        from decimal import Decimal
        try:
            from api.payment_gateways.integration_system.data_bridge import DataBridgeSync
            balance = DataBridgeSync().pull_user_balance(user)
        except Exception:
            balance = Decimal(str(getattr(user, 'balance', '0') or '0'))

        if balance < Decimal(str(amount)):
            raise AuthBridgeError(user, f'sufficient_balance (need {amount}, have {balance})')

    def get_user_capabilities(self, user) -> dict:
        """Get all payment capabilities for a user."""
        caps = {
            'can_deposit':        False,
            'can_withdraw':       False,
            'is_publisher':       False,
            'is_advertiser':      False,
            'kyc_verified':       False,
            'is_fast_pay':        False,
        }
        if not user or not user.is_active:
            return caps

        caps['can_deposit']  = True
        caps['can_withdraw'] = not getattr(user, 'is_banned', False)

        try:
            from api.payment_gateways.publisher.models import PublisherProfile
            p = PublisherProfile.objects.get(user=user)
            caps['is_publisher'] = p.status == 'active'
            caps['is_fast_pay']  = p.is_fast_pay_eligible
        except Exception:
            pass

        try:
            from api.payment_gateways.publisher.models import AdvertiserProfile
            AdvertiserProfile.objects.get(user=user, status='active')
            caps['is_advertiser'] = True
        except Exception:
            pass

        try:
            from api.payment_gateways.integration_system.data_bridge import DataBridgeSync
            kyc = DataBridgeSync().pull_kyc_status(user)
            caps['kyc_verified'] = kyc.get('is_verified', False)
        except Exception:
            pass

        return caps

    def _check_permission(self, user, permission: str) -> bool:
        if not user or not user.is_active:
            return False
        if user.is_superuser or user.is_staff:
            return True
        # Django standard permission
        if hasattr(user, 'has_perm'):
            return user.has_perm(permission)
        return False
