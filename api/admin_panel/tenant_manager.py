# api/admin_panel/tenant_manager.py
"""Multi-tenant settings and isolation admin control."""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from django.utils import timezone

logger = logging.getLogger(__name__)


class TenantManager:
    """Admin control for multi-tenant configuration."""

    @classmethod
    def get_all_tenants(cls) -> List[Dict]:
        try:
            from api.tenants.models import Tenant
            return list(Tenant.objects.values(
                'id', 'name', 'domain', 'is_active',
                'plan', 'created_at'
            ).order_by('-created_at')[:100])
        except Exception as e:
            return []

    @classmethod
    def get_tenant_stats(cls, tenant_id: Any) -> Dict:
        try:
            from api.tenants.models import Tenant, TenantSettings
            tenant = Tenant.objects.get(pk=tenant_id)
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user_count = User.objects.filter(tenant=tenant).count()
            return {
                'tenant_id': tenant_id, 'name': tenant.name,
                'user_count': user_count, 'plan': tenant.plan,
                'is_active': tenant.is_active,
            }
        except Exception as e:
            return {'tenant_id': tenant_id, 'error': str(e)}

    @classmethod
    def toggle_tenant(cls, tenant_id: Any, actor) -> Dict:
        try:
            from api.tenants.models import Tenant
            t = Tenant.objects.get(pk=tenant_id)
            t.is_active = not t.is_active
            t.save(update_fields=['is_active'])
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(actor=actor, action='toggle_tenant',
                              model_name='Tenant', object_id=str(tenant_id),
                              changes={'is_active': t.is_active, 'name': t.name})
            return {'success': True, 'tenant_id': tenant_id, 'is_active': t.is_active}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def get_tenant_billing(cls, tenant_id: Any) -> Dict:
        try:
            from api.tenants.models import TenantBilling
            billing = TenantBilling.objects.get(tenant_id=tenant_id)
            return {
                'tenant_id': tenant_id,
                'plan': billing.plan,
                'amount': float(billing.amount),
                'billing_cycle': billing.billing_cycle,
                'next_billing': str(billing.next_billing_date),
            }
        except Exception as e:
            return {'tenant_id': tenant_id, 'error': str(e)}

tenant_manager = TenantManager()