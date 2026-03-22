from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny
from .models import Tenant
from .serializers import TenantSerializer
import uuid

class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAdminUser]

    @action(detail=True, methods=["post"])
    def regenerate_api_key(self, request, pk=None):
        tenant = self.get_object()
        tenant.api_key = uuid.uuid4()
        tenant.save()
        return Response({"api_key": str(tenant.api_key)})

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def my_tenant(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response({"error": "No tenant found"}, status=404)
        return Response({
            "name": tenant.name,
            "slug": tenant.slug,
            "logo": request.build_absolute_uri(tenant.logo.url) if tenant.logo else None,
            "primary_color": tenant.primary_color,
            "secondary_color": tenant.secondary_color,
            "plan": tenant.plan,
            "max_users": tenant.max_users,
        })

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def public_settings(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response({"error": "No tenant"}, status=404)
        return Response(TenantSerializer(tenant).data)

    @action(detail=True, methods=["patch"])
    def update_branding(self, request, pk=None):
        tenant = self.get_object()
        allowed = ["name", "logo", "primary_color", "secondary_color"]
        for key in allowed:
            if key in request.data:
                setattr(tenant, key, request.data[key])
        tenant.save()
        return Response(TenantSerializer(tenant).data)
