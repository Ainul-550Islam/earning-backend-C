# api/wallet/permissions.py
from rest_framework.permissions import BasePermission


class IsWalletOwner(BasePermission):
    """Allow only the wallet owner."""
    def has_object_permission(self, request, view, obj):
        user = getattr(obj, "user", None) or getattr(getattr(obj, "wallet", None), "user", None)
        return user == request.user

class IsWalletOwnerOrAdmin(BasePermission):
    """Allow owner or admin staff."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        user = getattr(obj, "user", None) or getattr(getattr(obj, "wallet", None), "user", None)
        return user == request.user

class WalletNotLocked(BasePermission):
    """Deny if wallet is locked."""
    message = "Your wallet is locked. Please contact support."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        try:
            wallet = request.user.wallet_wallet_user
            if wallet.is_locked:
                return False
        except Exception:
            pass
        return True

class HasKYCLevel(BasePermission):
    """Require minimum KYC level (override required_level)."""
    required_level = 1

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        try:
            from .services.core.WalletService import WalletService
            return WalletService._get_kyc_level(request.user) >= self.required_level
        except Exception:
            return True  # fail-open if KYC not set up

class IsAdminOrReadOnly(BasePermission):
    """Admin can write; authenticated can read."""
    def has_permission(self, request, view):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_staff

class NoWithdrawalBlock(BasePermission):
    """Deny if user has active withdrawal block."""
    message = "Withdrawals are currently blocked on your account."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        try:
            from .models.withdrawal import WithdrawalBlock
            block = WithdrawalBlock.objects.filter(user=request.user, is_active=True).first()
            if block and block.is_currently_active():
                self.message = f"Withdrawal blocked: {block.reason}"
                return False
        except Exception:
            pass
        return True
