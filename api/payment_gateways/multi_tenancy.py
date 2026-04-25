# api/payment_gateways/multi_tenancy.py
# Multi-tenant support for payment_gateways (enterprise feature)
import logging
from django.core.cache import cache
logger = logging.getLogger(__name__)

class TenantManager:
    def get_current_tenant(self, request):
        host = request.get_host().split(':')[0]
        cache_key = f'tenant:{host}'
        cached = cache.get(cache_key)
        if cached: return cached
        try:
            from api.tenants.models import Tenant
            tenant = Tenant.objects.get(domain=host, is_active=True)
            data = {'id':tenant.id,'name':tenant.name,'domain':host,'schema':tenant.schema_name}
            cache.set(cache_key, data, 300)
            return data
        except: return {'id':None,'name':'default','domain':host,'schema':'public'}
    def get_tenant_gateway_config(self, tenant_id, gateway):
        if not tenant_id: return {}
        try:
            from api.payment_gateways.models.gateway_config import GatewayCredential
            cred = GatewayCredential.objects.get(tenant_id=tenant_id, gateway__name=gateway, is_active=True)
            return {'api_key':cred.api_key,'api_secret':cred.api_secret,'merchant_id':cred.merchant_id,'is_test':cred.is_test_mode}
        except: return {}
    def is_feature_enabled_for_tenant(self, tenant_id, feature):
        if not tenant_id: return True
        from api.payment_gateways.feature_flags import feature_flags
        return feature_flags.is_enabled(feature)
tenant_manager = TenantManager()
