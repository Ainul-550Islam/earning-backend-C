# api/support/integrations/auth_bridge.py  — WORLD #1 (New)
"""
Auth Bridge — Cross-Module Permission System।
Support system ↔ Other app permissions sync।
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SupportAuthBridge:
    """
    Cross-module permission management.
    
    Support agents need permissions scoped to their tenant/department.
    This bridges support permissions with your main auth system.
    """

    def get_user_tier(self, user) -> str:
        """
        Get publisher tier for SLA prioritization.
        Checks: wallet total_earned, referral count, KYC status.
        """
        from .integ_constants import TIER_VIP, TIER_GOLD, TIER_SILVER, TIER_STANDARD, TIER_NEW
        try:
            from .integ_adapter import wallet_adapter, kyc_adapter
            wallet = wallet_adapter.get_balance(user)
            earned = wallet.get('total_earned', 0)
            verified = kyc_adapter.is_verified(user)
            if earned >= 5000 and verified:
                return TIER_VIP
            elif earned >= 1000 and verified:
                return TIER_GOLD
            elif earned >= 500:
                return TIER_SILVER
            elif earned >= 100:
                return TIER_STANDARD
            return TIER_NEW
        except Exception as e:
            logger.debug(f'get_user_tier failed: {e}')
            return 'standard'

    def get_sla_hours_for_user(self, user, base_hours: int) -> int:
        """Adjust SLA hours based on user tier (VIP gets faster response)."""
        from .integ_constants import TIER_SLA_HOURS
        tier = self.get_user_tier(user)
        tier_hours = TIER_SLA_HOURS.get(tier, base_hours)
        return min(tier_hours, base_hours)  # Never slower than base

    def can_access_ticket(self, requester, ticket) -> bool:
        """
        Check if a user/agent can access a ticket.
        Respects tenant isolation.
        """
        if requester.is_superuser:
            return True
        if requester.is_staff:
            # Agents can only access tickets in their tenant
            if hasattr(requester, 'support_agent'):
                agent = requester.support_agent
                if agent.tenant and ticket.tenant and agent.tenant != ticket.tenant:
                    return False
            return True
        # Regular users can only access own tickets
        return ticket.user == requester

    def can_auto_approve_dispute(self, agent, dispute) -> bool:
        """Check if agent has permission to auto-approve disputes."""
        if agent.is_superuser:
            return True
        try:
            support_agent = agent.support_agent
            return support_agent.role in ('senior_agent','supervisor','manager','account_manager')
        except Exception:
            return agent.is_staff

    def get_tenant_from_request(self, request) -> Optional[object]:
        """Get tenant from request — supports header, subdomain, user."""
        user = getattr(request, 'user', None)
        if user and hasattr(user, 'tenant'):
            return user.tenant
        # Try X-Tenant-ID header
        tenant_id = request.headers.get('X-Tenant-ID') or request.META.get('HTTP_X_TENANT_ID')
        if tenant_id:
            try:
                from django.apps import apps
                Tenant = apps.get_model('tenants', 'Tenant')
                return Tenant.objects.get(id=tenant_id)
            except Exception:
                pass
        return None

    def filter_by_tenant(self, queryset, user):
        """Filter queryset by user's tenant."""
        tenant = getattr(user, 'tenant', None)
        if tenant and not user.is_superuser:
            return queryset.filter(tenant=tenant)
        return queryset

    def can_manage_agents(self, user) -> bool:
        """Can this user manage support agents?"""
        if user.is_superuser:
            return True
        try:
            return user.support_agent.role in ('supervisor','manager','account_manager')
        except Exception:
            return user.is_staff

    def can_view_all_tickets(self, user) -> bool:
        """Can this user see all tickets (not just own)?"""
        return user.is_staff or user.is_superuser


auth_bridge = SupportAuthBridge()