from rest_framework import serializers


class TenantUserMixin:
    """User create/filter by tenant"""

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


class PlanLimitMixin:
    """Enforce tenant plan user limits"""

    def perform_create(self, serializer):
        tenant = getattr(self.request, "tenant", None)
        if tenant:
            current_users = tenant.tenant_users.filter(is_active=True).count()
            if current_users >= tenant.max_users:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied(
                    f"User limit reached. Your plan allows {tenant.max_users} users. "
                    f"Please upgrade to add more users."
                )
            serializer.save(tenant=tenant)
        else:
            serializer.save()
