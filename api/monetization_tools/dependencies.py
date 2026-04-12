"""
api/monetization_tools/dependencies.py
=========================================
Reusable DRF view-level dependencies / helper functions
that can be used as get_queryset overrides or injected into views.
"""

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError


# ---------------------------------------------------------------------------
# Tenant resolution
# ---------------------------------------------------------------------------

def get_current_tenant(request):
    """
    Return the Tenant object attached to this request (set by TenantMiddleware).
    Returns None if tenant context is unavailable.
    """
    return getattr(request, 'tenant', None)


# ---------------------------------------------------------------------------
# Object-ownership guard
# ---------------------------------------------------------------------------

def require_owner_or_admin(obj, request):
    """
    Raise PermissionDenied if the requesting user is neither the owner of `obj`
    nor a staff/admin user.
    """
    if request.user.is_staff:
        return
    if getattr(obj, 'user', None) != request.user:
        raise PermissionDenied(_("You do not own this resource."))


# ---------------------------------------------------------------------------
# Active subscription guard
# ---------------------------------------------------------------------------

def require_active_subscription(user, plan_slug: str = None):
    """
    Raise PermissionDenied if the user has no active subscription.
    Optionally check against a specific plan slug.
    """
    from .models import UserSubscription
    qs = UserSubscription.objects.filter(
        user=user, status__in=['trial', 'active'],
        current_period_end__gt=timezone.now(),
    )
    if plan_slug:
        qs = qs.filter(plan__slug=plan_slug)
    if not qs.exists():
        raise PermissionDenied(_("An active subscription is required for this feature."))


# ---------------------------------------------------------------------------
# Offer availability guard
# ---------------------------------------------------------------------------

def require_offer_available(offer):
    """Raise NotFound if the offer is not currently available."""
    if not offer.is_available:
        raise NotFound(_("This offer is no longer available."))


# ---------------------------------------------------------------------------
# Date-range parser
# ---------------------------------------------------------------------------

def parse_date_range(request):
    """
    Parse ?start=YYYY-MM-DD&end=YYYY-MM-DD from request.query_params.
    Returns (start_date, end_date) as date objects or (None, None).
    """
    from datetime import datetime
    start_str = request.query_params.get('start')
    end_str   = request.query_params.get('end')
    start = end = None
    try:
        if start_str:
            start = datetime.strptime(start_str, '%Y-%m-%d').date()
        if end_str:
            end   = datetime.strptime(end_str,   '%Y-%m-%d').date()
        if start and end and start > end:
            raise ValidationError({'start': _("Start date cannot be after end date.")})
    except (ValueError, TypeError):
        raise ValidationError({'dates': _("Invalid date format. Use YYYY-MM-DD.")})
    return start, end


# ---------------------------------------------------------------------------
# Pagination params parser
# ---------------------------------------------------------------------------

def parse_pagination(request, default_page_size: int = 20, max_page_size: int = 100):
    """
    Parse ?page=1&page_size=20 from request.query_params.
    Returns (page, page_size).
    """
    try:
        page      = max(1, int(request.query_params.get('page', 1)))
        page_size = min(
            max_page_size,
            max(1, int(request.query_params.get('page_size', default_page_size)))
        )
    except (ValueError, TypeError):
        raise ValidationError({'pagination': _("Invalid pagination parameters.")})
    return page, page_size


# ---------------------------------------------------------------------------
# Country resolver
# ---------------------------------------------------------------------------

def get_user_country(request) -> str:
    """
    Resolve user country from:
      1. request.user.country (profile)
      2. CF-IPCountry header (Cloudflare)
      3. X-Country-Code custom header
      4. Fallback to empty string
    """
    user_country = getattr(request.user, 'country', '') if request.user.is_authenticated else ''
    if user_country:
        return user_country.upper()
    cf_country = request.META.get('HTTP_CF_IPCOUNTRY', '')
    if cf_country and cf_country != 'XX':
        return cf_country.upper()
    return request.META.get('HTTP_X_COUNTRY_CODE', '').upper()


# ---------------------------------------------------------------------------
# Device type resolver
# ---------------------------------------------------------------------------

def get_device_type(request) -> str:
    """
    Heuristic device type detection from User-Agent.
    Returns 'mobile' | 'tablet' | 'desktop'.
    """
    ua = request.META.get('HTTP_USER_AGENT', '').lower()
    if any(kw in ua for kw in ('ipad', 'tablet', 'android 3', 'android 4.0; tablet')):
        return 'tablet'
    if any(kw in ua for kw in ('iphone', 'android', 'mobile', 'ipod', 'blackberry', 'windows phone')):
        return 'mobile'
    return 'desktop'
