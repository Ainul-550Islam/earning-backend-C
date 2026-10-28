# api/djoyalty/integration_system/auth_bridge.py
"""
Auth Bridge -- Cross-module permission management।
Handles: API key auth, postback verification, inter-service auth।
"""
import hashlib
import hmac
import logging
import time
from functools import wraps
from typing import Optional, Tuple
from django.core.cache import cache
from .integ_exceptions import InvalidAPIKeyError, InsufficientPermissionError

logger = logging.getLogger(__name__)


class APIKeyAuth:
    """
    API key authentication for integration endpoints।
    Used by: Partner API, OfferWall postbacks, Public API।
    """

    @staticmethod
    def verify_partner_api_key(api_key: str, required_partner_id: int = None) -> Optional[object]:
        """Verify partner API key -> return PartnerMerchant or None।"""
        if not api_key:
            raise InvalidAPIKeyError('API key is required')

        cache_key = f'djoyalty:partner_key:{hashlib.md5(api_key.encode()).hexdigest()}'
        partner = cache.get(cache_key)

        if partner is None:
            try:
                from ..models.campaigns import PartnerMerchant
                partner = PartnerMerchant.objects.get(api_key=api_key, is_active=True)
                cache.set(cache_key, partner, timeout=300)  # 5 min cache
            except PartnerMerchant.DoesNotExist:
                raise InvalidAPIKeyError('Invalid or inactive API key')

        if required_partner_id and partner.id != required_partner_id:
            raise InsufficientPermissionError('API key does not match partner ID')

        return partner

    @staticmethod
    def verify_tenant_api_key(api_key: str) -> Optional[object]:
        """Verify tenant API key -> return Tenant or None।"""
        if not api_key:
            return None

        cache_key = f'djoyalty:tenant_key:{hashlib.md5(api_key.encode()).hexdigest()}'
        tenant = cache.get(cache_key)

        if tenant is None:
            try:
                from ..models.core import Tenant
                tenant = Tenant.objects.get(api_key=api_key, is_active=True)
                cache.set(cache_key, tenant, timeout=300)
            except Exception:
                return None

        return tenant

    @staticmethod
    def generate_api_key(prefix: str = '') -> str:
        """Generate a secure API key।"""
        import secrets
        key = secrets.token_urlsafe(32)
        return f'{prefix}{key}' if prefix else key


class PostbackAuth:
    """
    Postback signature verification for offerwall providers।
    """

    @staticmethod
    def verify_hmac(body: bytes, signature: str, secret: str,
                     algorithm: str = 'sha256') -> bool:
        """Verify HMAC signature।"""
        if not secret:
            logger.warning('PostbackAuth: no secret configured, skipping verification')
            return True

        if not signature:
            return False

        try:
            import hashlib as hl
            hash_fn = getattr(hl, algorithm, hl.sha256)
            expected = hmac.new(secret.encode(), body, hash_fn).hexdigest()

            # Handle "sha256=xxx" format
            sig = signature
            if '=' in sig:
                sig = sig.split('=', 1)[1]

            return hmac.compare_digest(expected.lower(), sig.lower())
        except Exception as e:
            logger.error('PostbackAuth.verify_hmac error: %s', e)
            return False

    @staticmethod
    def verify_timestamp(timestamp_str: str, max_age_seconds: int = 300) -> bool:
        """Verify request timestamp to prevent replay attacks।"""
        try:
            ts = int(timestamp_str)
            age = abs(time.time() - ts)
            return age <= max_age_seconds
        except (ValueError, TypeError):
            return False


class PermissionGuard:
    """
    Cross-module permission checks।
    Ensures operations are allowed based on tier, subscription, etc।
    """

    @staticmethod
    def can_cashout(customer) -> Tuple[bool, str]:
        """Check if customer can initiate cashout।"""
        try:
            if not customer.is_active:
                return False, 'Account not active'
            if not customer.is_verified:
                return False, 'Account not verified'

            # Check tier
            from ..models.cashout import CashoutRate
            rate = CashoutRate.objects.filter(
                is_active=True,
            ).first()

            if rate and rate.min_tier_required:
                ut = customer.user_tiers.filter(is_current=True).first()
                if not ut:
                    return False, 'No active tier'
                if ut.tier.rank < rate.min_tier_required.rank:
                    return False, f'Requires {rate.min_tier_required.label} tier'

            return True, ''
        except Exception as e:
            logger.error('PermissionGuard.can_cashout error: %s', e)
            return True, ''  # Fail open

    @staticmethod
    def can_access_offerwall(customer) -> Tuple[bool, str]:
        """Check if customer can access offerwall।"""
        if not customer.is_active:
            return False, 'Account not active'
        return True, ''

    @staticmethod
    def can_use_family_account(customer, family_account) -> Tuple[bool, str]:
        """Check if customer can use family account।"""
        member = family_account.members.filter(customer=customer, is_active=True).first()
        if not member:
            return False, 'Not a member of this family account'
        return True, ''

    @staticmethod
    def can_redeem(customer, points_required: float) -> Tuple[bool, str]:
        """Check if customer can redeem points।"""
        lp = customer.loyalty_points.first()
        if not lp or lp.balance < points_required:
            balance = lp.balance if lp else 0
            return False, f'Insufficient points: {balance} < {points_required}'
        return True, ''


def require_api_key(key_type: str = 'partner'):
    """
    Decorator for DRF views: require API key authentication।
    Usage:
        @require_api_key('partner')
        def partner_earn(request, partner_id):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            api_key = (
                request.META.get('HTTP_X_LOYALTY_API_KEY') or
                request.data.get('api_key') or
                request.query_params.get('api_key', '')
            )
            try:
                if key_type == 'partner':
                    partner_id = kwargs.get('pk') or kwargs.get('partner_id')
                    partner = APIKeyAuth.verify_partner_api_key(api_key, partner_id)
                    request.partner = partner
                elif key_type == 'tenant':
                    tenant = APIKeyAuth.verify_tenant_api_key(api_key)
                    request.api_tenant = tenant
                return view_func(request, *args, **kwargs)
            except (InvalidAPIKeyError, InsufficientPermissionError) as e:
                from rest_framework.response import Response
                from rest_framework import status
                return Response({'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
        return wrapper
    return decorator
