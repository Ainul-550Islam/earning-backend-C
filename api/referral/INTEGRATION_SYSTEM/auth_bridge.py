# api/referral/INTEGRATION_SYSTEM/auth_bridge.py
# Cross-module permission bridge — referral checks permissions from admin_panel
# ============================================================

import logging
from typing import Optional
from .integ_exceptions import AuthBridgeError

logger = logging.getLogger(__name__)


class ReferralAuthBridge:
    """
    Cross-module permission checker.
    Integrates with api/admin_panel permissions system.
    """

    # ── Permission Checks ─────────────────────────────────────────────────────

    @staticmethod
    def can_view_referrals(user) -> bool:
        """Can user view referral data?"""
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return ReferralAuthBridge._has_perm(user, 'referral.view_referral')

    @staticmethod
    def can_manage_campaigns(user) -> bool:
        """Can user create/edit campaigns?"""
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        return ReferralAuthBridge._has_perm(user, 'referral.change_referralcampaign')

    @staticmethod
    def can_manage_fraud(user) -> bool:
        """Can user review/clear suspicious referrals?"""
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user.is_staff:
            return True
        return ReferralAuthBridge._has_perm(user, 'referral.change_suspiciousreferral')

    @staticmethod
    def can_process_clawbacks(user) -> bool:
        """Can user approve/reject clawbacks?"""
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        return (
            user.is_staff and
            ReferralAuthBridge._has_perm(user, 'referral.change_commissionclawback')
        )

    @staticmethod
    def can_export_data(user) -> bool:
        """Can user export referral CSV data?"""
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or user.is_superuser

    @staticmethod
    def can_view_admin_insights(user) -> bool:
        """Can user see admin analytics dashboard?"""
        if not user or not user.is_authenticated:
            return False
        return user.is_staff or user.is_superuser

    @staticmethod
    def can_manage_blacklist(user) -> bool:
        """Can user add/remove blacklist entries?"""
        if not user or not user.is_authenticated:
            return False
        return user.is_superuser or (
            user.is_staff and
            ReferralAuthBridge._has_perm(user, 'referral.add_referralblacklist')
        )

    @staticmethod
    def is_referral_module_admin(user) -> bool:
        """Is user a referral module admin?"""
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if user.is_staff:
            return True
        try:
            return user.groups.filter(
                name__in=['referral_admin', 'referral_moderator']
            ).exists()
        except Exception:
            return False

    @staticmethod
    def check_tenant_access(user, obj) -> bool:
        """
        Multi-tenant check — user can only access their tenant's data.
        Integrates with api/tenants.
        """
        if user.is_superuser:
            return True
        user_tenant = getattr(user, 'tenant', None)
        obj_tenant = getattr(obj, 'tenant', None)
        if user_tenant is None or obj_tenant is None:
            return True  # No tenant filtering
        return user_tenant == obj_tenant

    # ── Admin Panel Integration ───────────────────────────────────────────────

    @staticmethod
    def get_referral_permissions_for_user(user) -> dict:
        """
        Get all referral permissions for a user.
        Used by frontend to show/hide UI elements.
        """
        return {
            'can_view': ReferralAuthBridge.can_view_referrals(user),
            'can_manage_campaigns': ReferralAuthBridge.can_manage_campaigns(user),
            'can_manage_fraud': ReferralAuthBridge.can_manage_fraud(user),
            'can_process_clawbacks': ReferralAuthBridge.can_process_clawbacks(user),
            'can_export': ReferralAuthBridge.can_export_data(user),
            'can_view_insights': ReferralAuthBridge.can_view_admin_insights(user),
            'can_manage_blacklist': ReferralAuthBridge.can_manage_blacklist(user),
            'is_admin': ReferralAuthBridge.is_referral_module_admin(user),
        }

    # ── DRF Permission Classes ────────────────────────────────────────────────

    @staticmethod
    def get_drf_permission_class(permission_type: str):
        """
        Get a DRF permission class for use in ViewSets.
        Bridges to api/admin_panel/permissions.py patterns.
        """
        from rest_framework.permissions import BasePermission

        class DynamicReferralPermission(BasePermission):
            def has_permission(self, request, view):
                checker = getattr(ReferralAuthBridge, f'can_{permission_type}', None)
                if checker:
                    return checker(request.user)
                return request.user and request.user.is_staff

        return DynamicReferralPermission

    # ── Private ───────────────────────────────────────────────────────────────

    @staticmethod
    def _has_perm(user, perm: str) -> bool:
        """Check Django permission (with group support)."""
        try:
            return user.has_perm(perm)
        except Exception as e:
            logger.debug(f'[AuthBridge] _has_perm failed: {e}')
            return False