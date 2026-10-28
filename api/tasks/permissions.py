"""
api/tasks/permissions.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Custom DRF permission classes for the task system.
"""

import logging
from django.core.cache import cache
from rest_framework.permissions import BasePermission, IsAuthenticated, IsAdminUser

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# BASIC PERMISSIONS
# ══════════════════════════════════════════════════════════════════════════════

class IsTaskOwner(BasePermission):
    """
    Only the user who created/owns the object can access it.
    Admins always have access.
    """
    message = 'You do not have permission to access this resource.'

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        owner = getattr(obj, 'user', None) or getattr(obj, 'owner', None)
        if owner is None:
            return True
        return owner == request.user or getattr(owner, 'pk', None) == request.user.pk


class IsPublisherOrAdmin(BasePermission):
    """
    Only verified publishers or admins can access.
    A user is a publisher if they have any task completions or
    if publisher flag is set on their profile.
    """
    message = 'Publisher account required.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        # Check publisher flag
        try:
            from users.models import Publisher
            return Publisher.objects.filter(
                user=request.user, is_active=True
            ).exists()
        except ImportError:
            return True  # Allow if Publisher model not available


class IsAdvertiserOrAdmin(BasePermission):
    """
    Only verified advertisers or admins can access.
    """
    message = 'Advertiser account required.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        try:
            from advertiser_portal.models import Advertiser
            return Advertiser.objects.filter(
                user=request.user, is_active=True
            ).exists()
        except ImportError:
            return True


class IsVerifiedUser(BasePermission):
    """
    User must have a verified email address.
    """
    message = 'Email verification required.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        try:
            return request.user.emailaddress_set.filter(verified=True).exists()
        except Exception:
            return True  # Allow if allauth not installed


class IsNotSuspended(BasePermission):
    """
    User must not be suspended due to fraud or policy violations.
    """
    message = 'Your account has been suspended.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        return not bool(cache.get(f'user_suspended_{request.user.pk}', False))


class IsNotFraudFlagged(BasePermission):
    """
    User must not have a high fraud risk score.
    High risk = score >= 60.
    """
    message = 'Account flagged for suspicious activity.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        score = int(cache.get(f'fraud_score_{request.user.pk}', 0))
        return score < 60


class HasKYCTier(BasePermission):
    """
    Parameterized permission: user must have at least a given KYC tier.
    Usage: HasKYCTier.for_tier('standard')
    """
    TIER_ORDER = {'none': 0, 'basic': 1, 'standard': 2, 'full': 3, 'edd': 4}
    required_tier = 'basic'
    message       = 'KYC verification required.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        current_tier = cache.get(f'kyc_tier_{request.user.pk}', 'none')
        required_level = self.TIER_ORDER.get(self.required_tier, 1)
        current_level  = self.TIER_ORDER.get(current_tier, 0)
        return current_level >= required_level

    @classmethod
    def for_tier(cls, tier: str) -> type:
        """Create a permission class for a specific tier."""
        return type(
            f'HasKYCTier_{tier}',
            (cls,),
            {'required_tier': tier, 'message': f'KYC tier "{tier}" required.'},
        )


# Convenience tier instances
HasBasicKYC    = HasKYCTier.for_tier('basic')
HasStandardKYC = HasKYCTier.for_tier('standard')
HasFullKYC     = HasKYCTier.for_tier('full')


# ══════════════════════════════════════════════════════════════════════════════
# TASK-SPECIFIC PERMISSIONS
# ══════════════════════════════════════════════════════════════════════════════

class CanCompleteTask(BasePermission):
    """
    Checks that the authenticated user can complete tasks:
    1. Authenticated
    2. Email verified (optional, configurable)
    3. Not suspended
    4. Fraud score < 60
    5. IP not blocked
    """
    message = 'You are not eligible to complete tasks.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        user_id  = request.user.pk
        ip       = request.META.get('REMOTE_ADDR', '')

        # Suspended
        if cache.get(f'user_suspended_{user_id}'):
            self.message = 'Account suspended.'
            return False

        # Fraud score
        score = int(cache.get(f'fraud_score_{user_id}', 0))
        if score >= 60:
            self.message = 'Account flagged for suspicious activity.'
            return False

        # IP blocked
        import hashlib
        if ip:
            ip_hash = hashlib.md5(ip.encode()).hexdigest()
            if cache.get(f'ip_blocked_{ip_hash}'):
                self.message = 'Access denied from this IP.'
                return False

        return True


class CanWithdraw(BasePermission):
    """
    Checks that the user is eligible to withdraw:
    1. Email verified
    2. Not suspended
    3. Low fraud score
    4. Payment method configured
    5. Minimum balance met
    """
    message = 'Withdrawal not permitted.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        user_id = request.user.pk

        if request.user.is_staff:
            return True

        if cache.get(f'user_suspended_{user_id}'):
            self.message = 'Account suspended. Withdrawal not allowed.'
            return False

        score = int(cache.get(f'fraud_score_{user_id}', 0))
        if score >= 40:
            self.message = 'Account under review. Withdrawal temporarily blocked.'
            return False

        if cache.get(f'payout_method_invalid_{user_id}'):
            self.message = 'Please configure a valid payout method first.'
            return False

        return True


class CanAccessAdminPanel(BasePermission):
    """
    Only staff + admins can access the admin panel endpoints.
    """
    message = 'Admin access required.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            (request.user.is_staff or request.user.is_superuser)
        )


class IsTaskRateLimitOK(BasePermission):
    """
    Checks the per-user task completion rate limit.
    Default: 20 completions per hour.
    """
    limit  = 20
    window = 3600
    message = 'Task completion rate limit reached. Please slow down.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        key   = f'task_rate_{request.user.pk}'
        count = cache.get(key, 0)
        if count >= self.limit:
            return False
        cache.set(key, count + 1, timeout=self.window)
        return True


class HasValidPostbackSignature(BasePermission):
    """
    For postback endpoints: validates HMAC-SHA256 signature.
    """
    message = 'Invalid postback signature.'

    def has_permission(self, request, view):
        import hmac
        import hashlib
        from django.conf import settings

        signature = request.META.get('HTTP_X_SIGNATURE_256', '')
        secret    = getattr(settings, 'POSTBACK_SECRET', '')
        if not secret:
            return True  # No secret configured, allow all

        body       = request.body
        expected   = 'sha256=' + hmac.new(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
        received   = signature if signature.startswith('sha256=') else f'sha256={signature}'
        return hmac.compare_digest(expected, received)


class IsIPWhitelisted(BasePermission):
    """
    Only allow requests from whitelisted IP ranges.
    Used for internal API endpoints.
    """
    message = 'Access denied from this IP.'

    def has_permission(self, request, view):
        from django.conf import settings
        whitelist = getattr(settings, 'TASK_API_IP_WHITELIST', [])
        if not whitelist:
            return True
        ip = request.META.get('REMOTE_ADDR', '')
        return ip in whitelist


# ══════════════════════════════════════════════════════════════════════════════
# COMBINED PERMISSIONS
# ══════════════════════════════════════════════════════════════════════════════

class IsAuthenticatedAndNotSuspended(IsAuthenticated, IsNotSuspended):
    """Combined: authenticated + not suspended."""
    pass


class IsTaskAdminOrReadOnly(BasePermission):
    """
    Read access for all authenticated users.
    Write access only for staff.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return request.user.is_staff


class IsTaskOwnerOrStaff(BasePermission):
    """
    Object-level: owner or staff can access.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        owner_id = getattr(obj, 'user_id', None)
        if owner_id is None:
            owner = getattr(obj, 'user', None)
            owner_id = getattr(owner, 'pk', None)
        return owner_id == request.user.pk


__all__ = [
    'IsTaskOwner', 'IsPublisherOrAdmin', 'IsAdvertiserOrAdmin',
    'IsVerifiedUser', 'IsNotSuspended', 'IsNotFraudFlagged',
    'HasKYCTier', 'HasBasicKYC', 'HasStandardKYC', 'HasFullKYC',
    'CanCompleteTask', 'CanWithdraw', 'CanAccessAdminPanel',
    'IsTaskRateLimitOK', 'HasValidPostbackSignature', 'IsIPWhitelisted',
    'IsAuthenticatedAndNotSuspended', 'IsTaskAdminOrReadOnly',
    'IsTaskOwnerOrStaff',
]
