# api/referral/dependencies.py
# DRF dependency injection helpers — common patterns across views
# ============================================================

import logging
from typing import Optional
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import Request

logger = logging.getLogger(__name__)


def get_referral_settings():
    """Get active ReferralSettings, raise if not configured."""
    from django.core.cache import cache
    settings = cache.get('referral_settings')
    if not settings:
        from api.referral.models import ReferralSettings
        settings = ReferralSettings.objects.first()
        if settings:
            cache.set('referral_settings', settings, timeout=300)
    if not settings:
        from api.referral.exceptions import ReferralConfigError
        raise ReferralConfigError('ReferralSettings not configured. Create one in admin.')
    return settings


def get_active_campaign():
    """Get active campaign if any."""
    from django.core.cache import cache
    from django.utils import timezone
    campaign = cache.get('referral_active_campaign')
    if campaign is None:
        from api.referral.models import ReferralCampaign
        campaign = ReferralCampaign.objects.filter(
            is_active=True,
            start_date__lte=timezone.now(),
            end_date__gte=timezone.now(),
        ).first()
        cache.set('referral_active_campaign', campaign, timeout=300)
    return campaign


def get_user_referral_code(user, create_if_missing: bool = True):
    """Get user's primary referral code object."""
    from api.referral.models import ReferralCode
    code = ReferralCode.objects.filter(
        user=user, is_primary=True, is_active=True
    ).first()
    if not code and create_if_missing:
        from api.referral.services.ReferralCodeService import ReferralCodeService
        code = ReferralCodeService.get_or_create_primary_code(user)
    return code


def get_referral_or_404(referral_id: int):
    """Get Referral by ID or raise NotFound."""
    from api.referral.models import Referral
    try:
        return Referral.objects.get(id=referral_id)
    except Referral.DoesNotExist:
        raise NotFound(detail='Referral not found.')


def get_commission_log_or_404(commission_id: int, user=None):
    """Get CommissionLog by ID or raise NotFound. Optionally check ownership."""
    from api.referral.models import CommissionLog
    try:
        log = CommissionLog.objects.get(id=commission_id)
    except CommissionLog.DoesNotExist:
        raise NotFound(detail='Commission not found.')
    if user and not user.is_staff and log.user_id != user.id:
        raise PermissionDenied(detail='You do not own this commission.')
    return log


def require_referral_program_active():
    """Raise if referral program is inactive."""
    settings = get_referral_settings()
    if not settings.is_active:
        from api.referral.exceptions import ReferralProgramInactiveError
        raise ReferralProgramInactiveError()


def get_commission_rate_for_user(user, level: int = 1):
    """
    Get effective commission rate for a user at given level.
    Checks UserCommissionTier first, falls back to ReferralSettings.
    """
    from decimal import Decimal
    try:
        from api.referral.models import UserCommissionTier
        tier = UserCommissionTier.objects.filter(user=user).first()
        if tier:
            rate_map = {1: tier.effective_l1_rate,
                        2: tier.effective_l2_rate,
                        3: tier.effective_l3_rate}
            return rate_map.get(level, Decimal('0'))
    except Exception:
        pass
    settings = get_referral_settings()
    return settings.get_rate_for_level(level)


def get_referral_bridge():
    """Get the integration bridge singleton."""
    from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
    return get_bridge()


def get_request_ip(request: Request) -> str:
    """Extract real IP from request."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def get_referral_code_from_cookie(request: Request) -> Optional[str]:
    """Read referral code from tracking cookie."""
    from django.conf import settings as django_settings
    cookie_name = getattr(django_settings, 'REFERRAL_COOKIE_NAME', 'ref_code')
    return request.COOKIES.get(cookie_name)