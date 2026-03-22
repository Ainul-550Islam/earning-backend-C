from rest_framework import serializers

class TenantMixin:
    """Add this to any ViewSet to automatically filter by tenant"""
    
    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, "tenant", None)
        if tenant and hasattr(qs.model, "tenant"):
            return qs.filter(tenant=tenant)
        return qs

    def perform_create(self, serializer):
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            serializer.save(tenant=tenant)
        else:
            serializer.save()

class TenantSettingsMixin:
    """Get settings based on tenant"""
    
    def get_tenant_settings(self, request):
        from api.tenants.models import Tenant
        tenant = getattr(request, "tenant", None)
        if tenant:
            return {
                "primary_color": tenant.primary_color,
                "secondary_color": tenant.secondary_color,
                "logo": tenant.logo.url if tenant.logo else None,
                "name": tenant.name,
                "plan": tenant.plan,
                "max_users": tenant.max_users,
            }
        return {}
