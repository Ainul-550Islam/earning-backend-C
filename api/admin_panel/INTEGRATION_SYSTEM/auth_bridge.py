# api/admin_panel/INTEGRATION_SYSTEM/auth_bridge.py
"""
AuthBridge — Cross-Module Permission System.
Controls what each admin role can do across all 50 apps.
Checks: AdminProfile role, granular permissions, app-level capabilities.

New — solves: "Can this admin user perform this action on this app?"
"""
import logging
from typing import Any, Dict, List, Optional
from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from .integ_exceptions import AuthBridgeError

logger = logging.getLogger(__name__)

# ==================== ROLE-CAPABILITY MAP ====================
# What each role can do across the integration system

ROLE_PERMISSIONS = {
    'superadmin': {
        '*': ['read', 'write', 'delete', 'action', 'bulk', 'admin'],  # Full access everywhere
    },
    'admin': {
        'users':          ['read', 'write', 'ban', 'verify', 'bulk'],
        'wallet':         ['read', 'write', 'adjust', 'freeze'],
        'fraud_detection':['read', 'write', 'block_ip', 'update_settings'],
        'payout_queue':   ['read', 'write', 'approve', 'reject', 'bulk'],
        'kyc':            ['read', 'write', 'approve', 'reject'],
        'promotions':     ['read', 'write', 'pause', 'approve'],
        'smartlink':      ['read', 'write', 'toggle'],
        'analytics':      ['read'],
        'audit_logs':     ['read'],
        'cms':            ['read', 'write'],
        'messaging':      ['read', 'write', 'broadcast'],
        'version_control':['read', 'write'],
        'djoyalty':       ['read', 'write', 'grant', 'deduct'],
        'ad_networks':    ['read', 'toggle'],
        'offer_inventory':['read', 'write', 'approve'],
        'postback':       ['read', 'retry'],
        'localization':   ['read', 'write'],
        'gamification':   ['read', 'write'],
        'auto_mod':       ['read', 'write', 'approve', 'reject'],
        'alerts':         ['read', 'acknowledge'],
        'behavior_analytics': ['read'],
        'advertiser_portal':  ['read', 'approve', 'reject'],
        'publisher_tools':    ['read', 'approve', 'reject'],
    },
    'moderator': {
        'users':          ['read', 'ban'],
        'fraud_detection':['read', 'block_ip'],
        'promotions':     ['read', 'pause'],
        'kyc':            ['read', 'approve', 'reject'],
        'auto_mod':       ['read', 'approve', 'reject'],
        'cms':            ['read', 'write'],
        'messaging':      ['read', 'broadcast'],
        'analytics':      ['read'],
        'audit_logs':     ['read'],
        'alerts':         ['read', 'acknowledge'],
    },
    'finance': {
        'wallet':         ['read', 'adjust'],
        'payout_queue':   ['read', 'approve', 'reject', 'bulk'],
        'analytics':      ['read'],
        'audit_logs':     ['read'],
        'localization':   ['read', 'write'],
        'advertiser_portal': ['read', 'approve'],
    },
    'analyst': {
        'analytics':          ['read'],
        'behavior_analytics': ['read'],
        'audit_logs':         ['read'],
        'promotions':         ['read'],
        'smartlink':          ['read'],
        'fraud_detection':    ['read'],
        'users':              ['read'],
        'wallet':             ['read'],
    },
    'support': {
        'users':    ['read'],
        'wallet':   ['read'],
        'messaging':['read', 'write'],
        'kyc':      ['read'],
    },
    'viewer': {
        '*': ['read'],  # Read-only everywhere
    },
}


class AuthBridge:
    """
    Cross-module permission checker.
    Single source of truth for: "Can admin X do action Y on app Z?"
    """

    @classmethod
    def get_admin_role(cls, user) -> str:
        """Get admin role from AdminProfile."""
        try:
            return user.admin_profile.role
        except Exception:
            if user.is_superuser:
                return 'superadmin'
            if user.is_staff:
                return 'admin'
            return 'viewer'

    @classmethod
    def can(cls, user, app: str, capability: str) -> bool:
        """
        Check if user can perform capability on app.
        Returns True/False.
        """
        if not user or not user.is_authenticated:
            return False

        role = cls.get_admin_role(user)
        permissions = ROLE_PERMISSIONS.get(role, {})

        # Wildcard: superadmin or viewer
        wildcard = permissions.get('*', [])
        if 'admin' in wildcard or capability in wildcard:
            return True

        # App-specific permissions
        app_caps = permissions.get(app, [])
        return capability in app_caps

    @classmethod
    def require(cls, user, app: str, capability: str) -> None:
        """Require permission or raise AuthBridgeError."""
        if not cls.can(user, app, capability):
            role = cls.get_admin_role(user)
            raise AuthBridgeError(
                f"Role '{role}' cannot perform '{capability}' on '{app}'",
                details={'role': role, 'app': app, 'capability': capability},
            )

    @classmethod
    def get_user_permissions(cls, user) -> Dict:
        """Return all permissions for a user as a structured dict."""
        role = cls.get_admin_role(user)
        return {
            'role': role,
            'permissions': ROLE_PERMISSIONS.get(role, {}),
            'is_superadmin': role == 'superadmin',
        }

    @classmethod
    def get_accessible_apps(cls, user) -> List[str]:
        """List all apps this user can READ."""
        role = cls.get_admin_role(user)
        permissions = ROLE_PERMISSIONS.get(role, {})

        if '*' in permissions:
            from .integ_constants import INTEGRATION_APPS
            return INTEGRATION_APPS

        return [app for app, caps in permissions.items() if 'read' in caps]

    @classmethod
    def can_bulk(cls, user, app: str) -> bool:
        return cls.can(user, app, 'bulk')

    @classmethod
    def can_delete(cls, user, app: str) -> bool:
        return cls.can(user, app, 'delete')


# ==================== DECORATOR ====================

def require_integration_permission(app: str, capability: str):
    """
    ViewSet action decorator for integration permissions.

    @action(detail=False, methods=['post'])
    @require_integration_permission('wallet', 'adjust')
    def adjust_balance(self, request):
        ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(view_instance, request, *args, **kwargs):
            try:
                AuthBridge.require(request.user, app, capability)
            except AuthBridgeError as e:
                return Response(
                    {'error': str(e), 'details': e.details},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return func(view_instance, request, *args, **kwargs)
        return wrapper
    return decorator