# api/offer_inventory/dependencies.py
"""
DRF dependencies — request থেকে common objects extract।
"""
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from django.core.cache import cache


def get_current_tenant(request):
    """Request থেকে tenant।"""
    return getattr(request, 'tenant', None)


def get_validated_user(request):
    """Authenticated user।"""
    if not request.user or not request.user.is_authenticated:
        raise AuthenticationFailed('লগইন করুন।')
    return request.user


def get_active_user(request):
    """Active + not suspended user।"""
    user = get_validated_user(request)
    from .models import UserRiskProfile
    try:
        risk = UserRiskProfile.objects.get(user=user)
        if risk.is_suspended:
            raise PermissionDenied('আপনার অ্যাকাউন্ট সাসপেন্ড।')
    except UserRiskProfile.DoesNotExist:
        pass
    return user


def get_kyc_verified_user(request):
    """KYC verified user।"""
    user = get_active_user(request)
    from .models import UserKYC
    if not UserKYC.objects.filter(user=user, status='approved').exists():
        raise PermissionDenied('KYC যাচাই প্রয়োজন।')
    return user


def check_feature_enabled(feature: str, request):
    """Feature flag check।"""
    from .repository import FeatureFlagRepository
    tenant = get_current_tenant(request)
    if not FeatureFlagRepository.is_enabled(feature, tenant):
        from .exceptions import FeatureDisabledException
        raise FeatureDisabledException()


def get_client_ip(request) -> str:
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')
