from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import Tenant, TenantSettings, TenantBilling, TenantInvoice
from .serializers import TenantSerializer, TenantSettingsSerializer, TenantBillingSerializer
import uuid

User = get_user_model()


class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAdminUser]

    # ── Public: React Native app এ logo/color পাবে ──────────────
    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def my_tenant(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response({"error": "No tenant found"}, status=404)
        settings_obj = getattr(tenant, 'settings', None)
        return Response({
            "name": tenant.name,
            "slug": tenant.slug,
            "logo": request.build_absolute_uri(tenant.logo.url) if tenant.logo else None,
            "primary_color": tenant.primary_color,
            "secondary_color": tenant.secondary_color,
            "plan": tenant.plan,
            "max_users": tenant.max_users,
            "app_name": settings_obj.app_name if settings_obj else tenant.name,
            "enable_referral": settings_obj.enable_referral if settings_obj else True,
            "enable_offerwall": settings_obj.enable_offerwall if settings_obj else True,
            "enable_kyc": settings_obj.enable_kyc if settings_obj else True,
            "enable_leaderboard": settings_obj.enable_leaderboard if settings_obj else True,
            "min_withdrawal": str(settings_obj.min_withdrawal) if settings_obj else "5.00",
        })

    # ── Admin: Branding update ───────────────────────────────────
    @action(detail=True, methods=["patch"])
    def update_branding(self, request, pk=None):
        tenant = self.get_object()
        allowed = ["name", "logo", "primary_color", "secondary_color"]
        for key in allowed:
            if key in request.data:
                setattr(tenant, key, request.data[key])
        tenant.save()
        return Response(TenantSerializer(tenant, context={'request': request}).data)

    # ── Admin: API Key regenerate ────────────────────────────────
    @action(detail=True, methods=["post"])
    def regenerate_api_key(self, request, pk=None):
        tenant = self.get_object()
        tenant.api_key = uuid.uuid4()
        tenant.save()
        return Response({"api_key": str(tenant.api_key)})

    # ── Admin: Dashboard stats ───────────────────────────────────
    @action(detail=True, methods=["get"])
    def dashboard(self, request, pk=None):
        tenant = self.get_object()
        total_users = User.objects.filter(tenant=tenant).count()
        active_users = User.objects.filter(tenant=tenant, is_active=True).count()
        billing = getattr(tenant, 'billing', None)
        return Response({
            "tenant": tenant.name,
            "plan": tenant.plan,
            "total_users": total_users,
            "active_users": active_users,
            "user_limit": tenant.max_users,
            "user_limit_reached": tenant.is_user_limit_reached(),
            "billing_status": billing.status if billing else "unknown",
            "trial_ends_at": billing.trial_ends_at if billing else None,
            "subscription_ends_at": billing.subscription_ends_at if billing else None,
        })

    # ── Admin: Feature flags update ──────────────────────────────
    @action(detail=True, methods=["patch"])
    def update_features(self, request, pk=None):
        tenant = self.get_object()
        settings_obj, _ = TenantSettings.objects.get_or_create(tenant=tenant)
        allowed = [
            "enable_referral", "enable_offerwall", "enable_kyc",
            "enable_leaderboard", "enable_chat", "enable_push_notifications",
            "min_withdrawal", "withdrawal_fee_percent", "app_name",
            "support_email", "privacy_policy_url", "terms_url",
            "android_package_name", "ios_bundle_id", "firebase_server_key",
        ]
        for key in allowed:
            if key in request.data:
                setattr(settings_obj, key, request.data[key])
        settings_obj.save()
        return Response({"success": True, "message": "Features updated"})

    # ── Admin: All tenants overview ──────────────────────────────
    @action(detail=False, methods=["get"])
    def overview(self, request):
        tenants = Tenant.objects.all()
        data = []
        for t in tenants:
            billing = getattr(t, 'billing', None)
            data.append({
                "id": t.id,
                "name": t.name,
                "domain": t.domain,
                "plan": t.plan,
                "is_active": t.is_active,
                "users": User.objects.filter(tenant=t).count(),
                "billing_status": billing.status if billing else "unknown",
                "created_at": t.created_at,
            })
        return Response(data)

    # ── Admin: Suspend/Activate tenant ──────────────────────────
    @action(detail=True, methods=["post"])
    def toggle_active(self, request, pk=None):
        tenant = self.get_object()
        tenant.is_active = not tenant.is_active
        tenant.save()
        return Response({
            "success": True,
            "is_active": tenant.is_active,
            "message": f"Tenant {'activated' if tenant.is_active else 'suspended'}"
        })


class TenantBillingViewSet(viewsets.ViewSet):
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=["post"])
    def create_subscription(self, request):
        import stripe
        from django.conf import settings
        stripe.api_key = settings.STRIPE_SECRET_KEY
        tenant = Tenant.objects.get(pk=request.data.get("tenant_id"))
        billing, _ = TenantBilling.objects.get_or_create(tenant=tenant)

        if not billing.stripe_customer_id:
            customer = stripe.Customer.create(
                email=tenant.admin_email,
                name=tenant.name,
            )
            billing.stripe_customer_id = customer.id
            billing.save()

        return Response({"stripe_customer_id": billing.stripe_customer_id})

    @action(detail=False, methods=["post"])
    def cancel_subscription(self, request):
        import stripe
        from django.conf import settings
        stripe.api_key = settings.STRIPE_SECRET_KEY
        tenant = Tenant.objects.get(pk=request.data.get("tenant_id"))
        billing = tenant.billing
        if billing.stripe_subscription_id:
            stripe.Subscription.cancel(billing.stripe_subscription_id)
            billing.status = "cancelled"
            billing.save()
        return Response({"success": True})

    @action(detail=False, methods=["get"])
    def status(self, request):
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return Response({"error": "No tenant"}, status=404)
        billing = getattr(tenant, "billing", None)
        return Response({
            "status": billing.status if billing else "unknown",
            "is_active": billing.is_active() if billing else False,
            "trial_ends_at": billing.trial_ends_at if billing else None,
            "subscription_ends_at": billing.subscription_ends_at if billing else None,
            "plan": tenant.plan,
        })
