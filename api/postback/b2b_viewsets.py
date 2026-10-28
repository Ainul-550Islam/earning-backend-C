"""b2b_viewsets.py — ViewSets for all B2B models."""
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .permissions import IsPostbackAdmin
from .b2b_models import (
    OrganizationAccount, B2BAPIKey, OrganizationRole, OrganizationMember,
    RevenueShareRule, AdvertiserBudgetCap, B2BContract, B2BInvoice,
    OutboundWebhookSubscription, WhiteLabelConfig,
    ImpersonationLog, PartnerCreditLedger,
)
from .b2b_serializers import (
    OrganizationAccountSerializer, B2BAPIKeyListSerializer, B2BAPIKeyCreateSerializer,
    OrganizationRoleSerializer, OrganizationMemberSerializer,
    RevenueShareRuleSerializer, AdvertiserBudgetCapSerializer,
    B2BContractSerializer, B2BInvoiceSerializer,
    OutboundWebhookSubSerializer, WhiteLabelConfigSerializer,
    ImpersonationLogSerializer, PartnerCreditLedgerSerializer, CreditTopupSerializer,
)

logger = logging.getLogger(__name__)


class OrganizationAccountViewSet(viewsets.ModelViewSet):
    queryset = OrganizationAccount.objects.all()
    serializer_class = OrganizationAccountSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["account_type", "status", "country_code"]
    search_fields = ["name", "slug", "contact_email"]
    ordering_fields = ["name", "created_at"]

    def get_permissions(self):
        if self.action in ["create", "destroy"]:
            return [IsPostbackAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return OrganizationAccount.objects.all()
        return OrganizationAccount.objects.filter(members__user=user, members__status="active")

    def perform_create(self, serializer):
        org = serializer.save(owner=self.request.user)
        # Auto-create Owner role + membership
        role = OrganizationRole.objects.create(
            organization=org, name="Owner", preset="owner",
            permissions=["all"], is_system=True,
        )
        OrganizationMember.objects.create(
            organization=org, user=self.request.user,
            role=role, status="active", joined_at=__import__("django.utils.timezone", fromlist=["timezone"]).timezone.now(),
        )

    @action(detail=True, methods=["get"], url_path="dashboard")
    def dashboard(self, request, pk=None):
        """Summary metrics for a partner dashboard."""
        from django.db.models import Sum, Count
        from postback.models import PostbackLog
        org = self.get_object()
        networks = org.networks.values_list("id", flat=True) if hasattr(org, "networks") else []
        logs = PostbackLog.objects.filter(network_id__in=networks)
        return Response({
            "organization": org.name,
            "account_type": org.account_type,
            "total_conversions": logs.filter(status="rewarded").count(),
            "total_payout_bdt": logs.filter(status="rewarded").aggregate(t=Sum("payout"))["t"] or 0,
            "active_members": org.members.filter(status="active").count(),
            "active_api_keys": org.api_keys.filter(is_active=True).count(),
            "open_invoices": org.invoices.filter(status__in=["sent", "overdue"]).count(),
            "credit_balance": str(PartnerCreditLedger.get_balance(org)),
        })

    @action(detail=True, methods=["post"], url_path="suspend", permission_classes=[IsPostbackAdmin])
    def suspend(self, request, pk=None):
        org = self.get_object()
        org.status = "suspended"
        org.save(update_fields=["status"])
        logger.info("Org %s suspended by %s", org.pk, request.user)
        return Response({"status": "suspended"})

    @action(detail=True, methods=["post"], url_path="activate", permission_classes=[IsPostbackAdmin])
    def activate(self, request, pk=None):
        org = self.get_object()
        org.status = "active"
        org.save(update_fields=["status"])
        return Response({"status": "active"})


class B2BAPIKeyViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["organization", "is_active"]

    def get_serializer_class(self):
        if self.action == "create":
            return B2BAPIKeyCreateSerializer
        return B2BAPIKeyListSerializer

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return B2BAPIKey.objects.select_related("organization").all()
        org_ids = OrganizationMember.objects.filter(
            user=user, status="active"
        ).values_list("organization_id", flat=True)
        return B2BAPIKey.objects.filter(organization_id__in=org_ids)

    def create(self, request, *args, **kwargs):
        serializer = B2BAPIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org_id = request.data.get("organization")
        try:
            org = OrganizationAccount.objects.get(pk=org_id)
        except OrganizationAccount.DoesNotExist:
            return Response({"detail": "Organization not found."}, status=404)
        instance, raw_key = B2BAPIKey.generate(
            organization=org,
            name=serializer.validated_data["name"],
            scopes=serializer.validated_data["scopes"],
            created_by=request.user,
            expires_at=serializer.validated_data.get("expires_at"),
        )
        return Response({
            "id": str(instance.pk),
            "key": raw_key,
            "key_prefix": instance.key_prefix,
            "scopes": instance.scopes,
            "warning": "Save this key — it will never be shown again.",
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        key = self.get_object()
        key.is_active = False
        key.save(update_fields=["is_active"])
        logger.info("API key %s revoked by %s", key.key_prefix, request.user)
        return Response({"status": "revoked", "key_prefix": key.key_prefix})

    @action(detail=False, methods=["post"], url_path="verify")
    def verify(self, request):
        raw_key = request.data.get("key", "")
        key = B2BAPIKey.verify(raw_key)
        if not key:
            return Response({"valid": False}, status=401)
        return Response({
            "valid": True,
            "organization": key.organization.name,
            "scopes": key.scopes,
        })


class OrganizationRoleViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationRoleSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["organization", "preset"]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return OrganizationRole.objects.all()
        org_ids = OrganizationMember.objects.filter(
            user=user, status="active"
        ).values_list("organization_id", flat=True)
        return OrganizationRole.objects.filter(organization_id__in=org_ids)

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system:
            return Response({"detail": "System roles cannot be deleted."}, status=400)
        return super().destroy(request, *args, **kwargs)


class OrganizationMemberViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationMemberSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["organization", "status", "role"]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return OrganizationMember.objects.select_related("user", "role", "organization").all()
        org_ids = OrganizationMember.objects.filter(
            user=user, status="active"
        ).values_list("organization_id", flat=True)
        return OrganizationMember.objects.filter(organization_id__in=org_ids)

    def perform_create(self, serializer):
        serializer.save(invited_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, pk=None):
        membership = self.get_object()
        if membership.user != request.user:
            return Response({"detail": "Forbidden."}, status=403)
        membership.accept_invitation()
        return Response({"status": "accepted"})

    @action(detail=True, methods=["post"], url_path="remove", permission_classes=[IsPostbackAdmin])
    def remove(self, request, pk=None):
        membership = self.get_object()
        membership.status = "suspended"
        membership.save(update_fields=["status"])
        return Response({"status": "suspended"})


class RevenueShareRuleViewSet(viewsets.ModelViewSet):
    queryset = RevenueShareRule.objects.select_related("organization", "network").all()
    serializer_class = RevenueShareRuleSerializer
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["organization", "network", "rule_type", "is_active"]

    @action(detail=True, methods=["post"], url_path="calculate")
    def calculate(self, request, pk=None):
        """Preview publisher payout for a given gross amount."""
        rule = self.get_object()
        gross = request.data.get("gross_payout_bdt", 0)
        conversions = request.data.get("conversions_this_month", 0)
        try:
            from decimal import Decimal
            payout = rule.calculate_publisher_payout(Decimal(str(gross)), int(conversions))
        except Exception as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({
            "gross_payout_bdt": str(gross),
            "publisher_payout_bdt": str(payout),
            "platform_share_bdt": str(Decimal(str(gross)) - payout),
        })


class AdvertiserBudgetCapViewSet(viewsets.ModelViewSet):
    queryset = AdvertiserBudgetCap.objects.select_related("organization", "network").all()
    serializer_class = AdvertiserBudgetCapSerializer
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["organization", "network", "period", "is_active"]

    @action(detail=True, methods=["post"], url_path="reset")
    def reset(self, request, pk=None):
        cap = self.get_object()
        cap.current_spend = 0
        cap.current_conversions = 0
        cap.save(update_fields=["current_spend", "current_conversions"])
        return Response({"status": "reset", "remaining_bdt": str(cap.remaining_bdt)})


class B2BContractViewSet(viewsets.ModelViewSet):
    queryset = B2BContract.objects.select_related("organization", "revenue_share_rule").all()
    serializer_class = B2BContractSerializer
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["organization", "status"]
    search_fields = ["contract_number", "title"]

    @action(detail=True, methods=["post"], url_path="sign")
    def sign(self, request, pk=None):
        from django.utils import timezone
        contract = self.get_object()
        contract.status = "signed"
        contract.signed_at = timezone.now()
        contract.save(update_fields=["status", "signed_at"])
        return Response(B2BContractSerializer(contract).data)

    @action(detail=True, methods=["post"], url_path="terminate")
    def terminate(self, request, pk=None):
        contract = self.get_object()
        contract.status = "terminated"
        contract.save(update_fields=["status"])
        return Response({"status": "terminated"})


class B2BInvoiceViewSet(viewsets.ModelViewSet):
    queryset = B2BInvoice.objects.select_related("organization").all()
    serializer_class = B2BInvoiceSerializer
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["organization", "status", "invoice_type"]
    ordering = ["-period_start"]

    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, pk=None):
        invoice = self.get_object()
        invoice.mark_paid(request.data.get("payment_reference", ""))
        return Response(B2BInvoiceSerializer(invoice).data)

    @action(detail=True, methods=["post"], url_path="send")
    def send_invoice(self, request, pk=None):
        from django.utils import timezone
        invoice = self.get_object()
        invoice.status = "sent"
        invoice.issued_at = timezone.now()
        invoice.save(update_fields=["status", "issued_at"])
        # TODO: wire to email task
        return Response({"status": "sent", "invoice_number": invoice.invoice_number})

    @action(detail=False, methods=["post"], url_path="generate-monthly", permission_classes=[IsPostbackAdmin])
    def generate_monthly(self, request):
        """Trigger monthly invoice generation task."""
        from .b2b_tasks import generate_monthly_invoices
        generate_monthly_invoices.delay()
        return Response({"status": "queued"})


class OutboundWebhookSubViewSet(viewsets.ModelViewSet):
    queryset = OutboundWebhookSubscription.objects.select_related("organization").all()
    serializer_class = OutboundWebhookSubSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["organization", "is_active"]

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return OutboundWebhookSubscription.objects.all()
        org_ids = OrganizationMember.objects.filter(
            user=user, status="active"
        ).values_list("organization_id", flat=True)
        return OutboundWebhookSubscription.objects.filter(organization_id__in=org_ids)

    @action(detail=True, methods=["post"], url_path="test-ping")
    def test_ping(self, request, pk=None):
        """Send a test ping to the webhook endpoint."""
        sub = self.get_object()
        from .b2b_tasks import dispatch_outbound_webhook
        dispatch_outbound_webhook.delay(
            subscription_id=str(sub.pk),
            event_type="test_ping",
            payload={"event": "test_ping", "message": "Webhook endpoint verified."},
        )
        return Response({"status": "ping_queued", "endpoint": sub.endpoint_url})


class WhiteLabelConfigViewSet(viewsets.ModelViewSet):
    queryset = WhiteLabelConfig.objects.select_related("organization").all()
    serializer_class = WhiteLabelConfigSerializer
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["organization", "is_active"]

    @action(detail=True, methods=["post"], url_path="verify-domain")
    def verify_domain(self, request, pk=None):
        import socket
        config = self.get_object()
        if not config.custom_domain:
            return Response({"detail": "No custom domain set."}, status=400)
        try:
            ip = socket.gethostbyname(config.custom_domain)
            config.ssl_verified = True
            config.save(update_fields=["ssl_verified"])
            return Response({"verified": True, "resolved_ip": ip})
        except socket.gaierror:
            return Response({"verified": False, "detail": "DNS resolution failed."})


class ImpersonationLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ImpersonationLog.objects.select_related(
        "admin_user", "impersonated_user", "organization"
    ).all()
    serializer_class = ImpersonationLogSerializer
    permission_classes = [IsPostbackAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["admin_user", "impersonated_user", "organization"]
    ordering = ["-started_at"]

    @action(detail=False, methods=["post"], url_path="start")
    def start(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        target_id = request.data.get("user_id")
        reason = request.data.get("reason", "")
        if not reason:
            return Response({"detail": "reason is required."}, status=400)
        try:
            target = User.objects.get(pk=target_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=404)
        log = ImpersonationLog.start_session(
            admin_user=request.user,
            impersonated_user=target,
            reason=reason,
            source_ip=request.META.get("REMOTE_ADDR"),
        )
        logger.warning("IMPERSONATION STARTED: admin=%s target=%s reason=%s",
                       request.user.pk, target_id, reason)
        return Response({
            "session_id": str(log.pk),
            "session_token": log.session_token,
            "impersonated": target.username,
        })

    @action(detail=True, methods=["post"], url_path="end")
    def end(self, request, pk=None):
        log = self.get_object()
        log.end_session()
        return Response({"status": "ended", "duration_minutes": log.duration_minutes})


class PartnerCreditLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PartnerCreditLedgerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["organization", "entry_type"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return PartnerCreditLedger.objects.select_related("organization").all()
        org_ids = OrganizationMember.objects.filter(
            user=user, status="active"
        ).values_list("organization_id", flat=True)
        return PartnerCreditLedger.objects.filter(organization_id__in=org_ids)

    @action(detail=False, methods=["get"], url_path="balance/(?P<org_id>[^/.]+)")
    def balance(self, request, org_id=None):
        try:
            org = OrganizationAccount.objects.get(pk=org_id)
        except OrganizationAccount.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        return Response({"organization": org.name, "balance_bdt": str(PartnerCreditLedger.get_balance(org))})

    @action(detail=False, methods=["post"], url_path="topup", permission_classes=[IsPostbackAdmin])
    def topup(self, request):
        s = CreditTopupSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        org_id = request.data.get("organization")
        try:
            org = OrganizationAccount.objects.get(pk=org_id)
        except OrganizationAccount.DoesNotExist:
            return Response({"detail": "Organization not found."}, status=404)
        entry = PartnerCreditLedger.credit(
            organization=org,
            amount_bdt=s.validated_data["amount_bdt"],
            entry_type="topup",
            reference=s.validated_data.get("reference", ""),
            note=s.validated_data.get("note", ""),
            performed_by=request.user,
        )
        logger.info("Credit topup: org=%s amount=%s by=%s", org, entry.amount_bdt, request.user)
        return Response(PartnerCreditLedgerSerializer(entry).data, status=201)
