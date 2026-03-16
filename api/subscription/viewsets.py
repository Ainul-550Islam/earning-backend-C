"""viewsets.py – DRF ViewSets for the subscription module."""
import logging
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from .exceptions import NoActiveSubscriptionException
from .filters import SubscriptionPaymentFilter, SubscriptionPlanFilter, UserSubscriptionFilter
from .models import SubscriptionPayment, SubscriptionPlan, UserSubscription
from .pagination import PaymentPagination, PlanPagination, SubscriptionPageNumberPagination
from .permissions import IsAdminOrReadOnly, IsOwnerOrAdmin, IsSubscriptionOwner
from .serializers import (
    CancelSubscriptionSerializer,
    ChangePlanSerializer,
    PauseSubscriptionSerializer,
    RefundPaymentSerializer,
    SubscribeSerializer,
    SubscriptionPaymentSerializer,
    SubscriptionPlanDetailSerializer,
    SubscriptionPlanListSerializer,
    SubscriptionPlanWriteSerializer,
    UserSubscriptionSerializer,
)
from .services import (
    cancel_subscription,
    change_plan,
    create_subscription,
    get_active_plans,
    pause_subscription,
    refund_payment,
    resume_subscription,
)
from .throttling import BurstSubscriptionThrottle, PaymentThrottle, SubscriptionThrottle

logger = logging.getLogger(__name__)


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """
    list:    Public list of active plans with benefits.
    retrieve:  Plan detail.
    create/update/delete: Admin only.
    """
    queryset = SubscriptionPlan.objects.all().with_benefits().ordered()
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SubscriptionPlanFilter
    search_fields = ["name", "description", "slug"]
    ordering_fields = ["price", "sort_order", "created_at", "name"]
    ordering = ["sort_order", "price"]
    pagination_class = PlanPagination
    lookup_field = "slug"

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return SubscriptionPlanWriteSerializer
        if self.action == "retrieve":
            return SubscriptionPlanDetailSerializer
        return SubscriptionPlanListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Non-staff only sees active plans
        if not self.request.user.is_staff:
            qs = qs.active()
        return qs


class UserSubscriptionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    list:      User's own subscriptions (admins see all).
    retrieve:  Single subscription detail.
    subscribe: POST /subscriptions/subscribe/
    cancel:    POST /subscriptions/{id}/cancel/
    change_plan: POST /subscriptions/{id}/change_plan/
    pause:     POST /subscriptions/{id}/pause/
    resume:    POST /subscriptions/{id}/resume/
    my_subscription: GET /subscriptions/me/
    """
    serializer_class = UserSubscriptionSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    pagination_class = SubscriptionPageNumberPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = UserSubscriptionFilter
    ordering_fields = ["created_at", "current_period_end", "status"]
    ordering = ["-created_at"]
    throttle_classes = [SubscriptionThrottle]

    def get_queryset(self):
        user = self.request.user
        qs = UserSubscription.objects.with_plan().with_payments()
        if user.is_staff:
            return qs.all()
        return qs.filter(user=user)

    # ── Custom Actions ─────────────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="me")
    def my_subscription(self, request):
        """Return the caller's current active/trialing subscription."""
        sub = UserSubscription.objects.get_active_for_user(request.user)
        if not sub:
            raise NoActiveSubscriptionException()
        serializer = self.get_serializer(sub)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["post"],
        url_path="subscribe",
        throttle_classes=[BurstSubscriptionThrottle],
    )
    def subscribe(self, request):
        """Create a new subscription for the authenticated user."""
        serializer = SubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = create_subscription(
            user=request.user,
            plan_id=serializer.validated_data["plan_id"],
            payment_method=serializer.validated_data.get("payment_method"),
            coupon_code=serializer.validated_data.get("coupon_code"),
        )
        out = UserSubscriptionSerializer(subscription, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        """Cancel the subscription (optionally at period end)."""
        subscription = self.get_object()
        serializer = CancelSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        updated = cancel_subscription(
            subscription_id=subscription.pk,
            user=request.user,
            reason=d.get("reason", ""),
            comment=d.get("comment", ""),
            at_period_end=d.get("at_period_end", True),
        )
        return Response(UserSubscriptionSerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="change-plan")
    def change_plan_action(self, request, pk=None):
        """Upgrade or downgrade to a different plan."""
        subscription = self.get_object()
        serializer = ChangePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = change_plan(subscription, serializer.validated_data["new_plan_id"])
        return Response(UserSubscriptionSerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="pause")
    def pause(self, request, pk=None):
        """Pause the subscription."""
        subscription = self.get_object()
        serializer = PauseSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = pause_subscription(
            subscription, resume_at=serializer.validated_data.get("resume_at")
        )
        return Response(UserSubscriptionSerializer(updated).data)

    @action(detail=True, methods=["post"], url_path="resume")
    def resume(self, request, pk=None):
        """Resume a paused subscription."""
        subscription = self.get_object()
        updated = resume_subscription(subscription)
        return Response(UserSubscriptionSerializer(updated).data)


class SubscriptionPaymentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    list:     Payments for the authenticated user (staff see all).
    retrieve: Single payment detail.
    refund:   POST /payments/{id}/refund/   (staff only)
    """
    serializer_class = SubscriptionPaymentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PaymentPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = SubscriptionPaymentFilter
    ordering_fields = ["created_at", "amount", "paid_at"]
    ordering = ["-created_at"]
    throttle_classes = [PaymentThrottle]

    def get_queryset(self):
        user = self.request.user
        qs = SubscriptionPayment.objects.select_related("subscription__user", "subscription__plan")
        if user.is_staff:
            return qs.all()
        return qs.filter(subscription__user=user)

    @action(
        detail=True,
        methods=["post"],
        url_path="refund",
        permission_classes=[IsAdminUser],
    )
    def refund(self, request, pk=None):
        """Issue a full or partial refund (admin only)."""
        payment = self.get_object()
        serializer = RefundPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        refunded = refund_payment(
            payment_id=payment.pk,
            amount=serializer.validated_data.get("amount"),
        )
        return Response(SubscriptionPaymentSerializer(refunded).data)

# ─── MembershipBenefit ViewSet ────────────────────────────────────────────────

class MembershipBenefitViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for plan benefits.
    list/retrieve:         public (read-only)
    create/update/delete:  admin only
    
    GET  /plans/{plan_slug}/benefits/
    POST /plans/{plan_slug}/benefits/        (admin)
    PUT  /plans/{plan_slug}/benefits/{id}/   (admin)
    DEL  /plans/{plan_slug}/benefits/{id}/   (admin)
    """
    from .models import MembershipBenefit
    from .serializers import MembershipBenefitSerializer, MembershipBenefitWriteSerializer

    queryset = MembershipBenefit.objects.select_related("plan").order_by("sort_order")
    permission_classes = [IsAdminOrReadOnly]

    def get_serializer_class(self):
        from .serializers import MembershipBenefitSerializer, MembershipBenefitWriteSerializer
        if self.request.method in ("POST", "PUT", "PATCH"):
            return MembershipBenefitWriteSerializer
        return MembershipBenefitSerializer

    def get_queryset(self):
        from .models import MembershipBenefit
        qs = MembershipBenefit.objects.select_related("plan").order_by("sort_order")
        plan_slug = self.kwargs.get("plan_slug")
        if plan_slug:
            qs = qs.filter(plan__slug=plan_slug)
        return qs

    def perform_create(self, serializer):
        plan_slug = self.kwargs.get("plan_slug")
        if plan_slug:
            plan = SubscriptionPlan.objects.get(slug=plan_slug)
            serializer.save(plan=plan)
        else:
            serializer.save()


# ─── SubscriptionPlanViewSet — override destroy for protection ─────────────────

class SafeSubscriptionPlanViewSet(SubscriptionPlanViewSet):
    """
    Extends SubscriptionPlanViewSet with:
    - DELETE protection (blocks if active subscribers exist)
    - archive action (soft-delete)
    """

    def destroy(self, request, *args, **kwargs):
        from .services import safe_delete_plan
        plan = self.get_object()
        safe_delete_plan(plan)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="archive", permission_classes=[IsAdminUser])
    def archive(self, request, slug=None):
        """Soft-delete: set plan status to archived. Safe even with active subscribers."""
        from .services import archive_plan
        plan = self.get_object()
        archive_plan(plan)
        from .serializers import SubscriptionPlanDetailSerializer
        return Response(SubscriptionPlanDetailSerializer(plan).data)

    @action(detail=True, methods=["get"], url_path="subscriber-count", permission_classes=[IsAdminUser])
    def subscriber_count(self, request, slug=None):
        """Returns active subscriber count — useful before deciding to delete/archive."""
        from .choices import SubscriptionStatus
        plan = self.get_object()
        counts = {
            "active": UserSubscription.objects.filter(plan=plan, status=SubscriptionStatus.ACTIVE).count(),
            "trialing": UserSubscription.objects.filter(plan=plan, status=SubscriptionStatus.TRIALING).count(),
            "total_all_time": UserSubscription.objects.filter(plan=plan).count(),
        }
        counts["can_delete"] = (counts["active"] + counts["trialing"]) == 0
        return Response(counts)


# ─── Coupon ViewSet ────────────────────────────────────────────────────────────

class CouponViewSet(viewsets.ModelViewSet):
    """
    Admin CRUD for coupons + public validate endpoint.

    GET    /coupons/               → admin list
    POST   /coupons/               → admin create
    GET    /coupons/{id}/          → admin detail
    PUT    /coupons/{id}/          → admin update
    DELETE /coupons/{id}/          → admin delete
    POST   /coupons/validate/      → public: check if a code is valid
    GET    /coupons/{id}/usages/   → admin: who used this coupon
    """
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["code", "description"]
    ordering_fields = ["created_at", "times_used", "valid_until"]
    ordering = ["-created_at"]

    def get_queryset(self):
        from .models import Coupon
        return Coupon.objects.prefetch_related("applicable_plans").all()

    def get_serializer_class(self):
        from .serializers import CouponSerializer, CouponValidateSerializer
        if self.action == "validate_coupon":
            return CouponValidateSerializer
        return CouponSerializer

    @action(
        detail=False,
        methods=["post"],
        url_path="validate",
        permission_classes=[IsAuthenticated],
    )
    def validate_coupon(self, request):
        """
        Public endpoint — any authenticated user can check a coupon.
        POST { "code": "SAVE20", "plan_id": "<uuid>" }
        Returns coupon details + discounted price if valid.
        """
        from .serializers import CouponValidateSerializer
        from .services import validate_coupon

        serializer = CouponValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        code = serializer.validated_data["code"]
        plan_id = serializer.validated_data["plan_id"]

        plan = SubscriptionPlan.objects.get(pk=plan_id)
        coupon = validate_coupon(code, plan, request.user)  # raises on invalid

        original = float(plan.discounted_price)
        final = float(coupon.calculate_discount(plan.discounted_price))

        return Response({
            "valid": True,
            "code": coupon.code,
            "description": coupon.description,
            "discount_type": coupon.discount_type,
            "discount_value": str(coupon.discount_value),
            "original_price": original,
            "discounted_price": final,
            "savings": round(original - final, 2),
            "currency": plan.currency,
        })

    @action(detail=True, methods=["get"], url_path="usages", permission_classes=[IsAdminUser])
    def usages(self, request, pk=None):
        """List all usage records for a coupon."""
        from .models import CouponUsage
        from .serializers import CouponUsageSerializer
        coupon = self.get_object()
        usages = CouponUsage.objects.filter(coupon=coupon).select_related("user", "subscription")
        serializer = CouponUsageSerializer(usages, many=True)
        return Response(serializer.data)


# ─── Admin Subscription Management ViewSet ────────────────────────────────────

class AdminSubscriptionViewSet(viewsets.GenericViewSet):
    """
    Admin-only operations for managing any user's subscription.

    POST /admin/subscriptions/grant/              → force-create subscription
    POST /admin/subscriptions/{id}/force-status/  → set any status
    GET  /admin/subscriptions/                    → all subscriptions (full list)
    GET  /admin/subscriptions/{id}/               → detail of any subscription
    """
    permission_classes = [IsAdminUser]
    serializer_class = UserSubscriptionSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ["user__username", "user__email", "plan__name"]
    ordering_fields = ["created_at", "status", "current_period_end"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return (
            UserSubscription.objects
            .select_related("user", "plan")
            .prefetch_related("payments")
            .all()
        )

    def list(self, request):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(UserSubscriptionSerializer(page, many=True).data)
        return Response(UserSubscriptionSerializer(qs, many=True).data)

    def retrieve(self, request, pk=None):
        from django.shortcuts import get_object_or_404
        sub = get_object_or_404(UserSubscription, pk=pk)
        return Response(UserSubscriptionSerializer(sub).data)

    @action(detail=False, methods=["post"], url_path="grant")
    def grant(self, request):
        """
        Force-create or override a subscription for any user.
        Bypasses payment. Cancels any existing active sub first.
        """
        from .serializers import AdminSubscriptionCreateSerializer
        from .services import admin_create_subscription

        serializer = AdminSubscriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        subscription = admin_create_subscription(
            admin_user=request.user,
            user_id=d["user_id"],
            plan_id=d["plan_id"],
            status=d.get("status", "active"),
            current_period_start=d.get("current_period_start"),
            current_period_end=d.get("current_period_end"),
            notes=d.get("notes", ""),
        )
        return Response(
            UserSubscriptionSerializer(subscription).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="force-status")
    def force_status(self, request, pk=None):
        """
        Force a subscription into any status.
        Use with caution — no payment validation is done.
        """
        from django.shortcuts import get_object_or_404
        from .serializers import AdminForceStatusSerializer
        from .services import admin_force_status

        sub = get_object_or_404(UserSubscription, pk=pk)
        serializer = AdminForceStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = admin_force_status(
            sub,
            new_status=serializer.validated_data["status"],
            reason=serializer.validated_data.get("reason", ""),
        )
        return Response(UserSubscriptionSerializer(updated).data)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        """Aggregated stats: subscriber counts per plan, revenue, churn."""
        from django.db.models import Count, Sum, Q
        from .choices import SubscriptionStatus, PaymentStatus

        plan_stats = list(
            SubscriptionPlan.objects.annotate(
                active_count=Count(
                    "subscriptions",
                    filter=Q(subscriptions__status=SubscriptionStatus.ACTIVE),
                ),
                trialing_count=Count(
                    "subscriptions",
                    filter=Q(subscriptions__status=SubscriptionStatus.TRIALING),
                ),
                cancelled_count=Count(
                    "subscriptions",
                    filter=Q(subscriptions__status=SubscriptionStatus.CANCELLED),
                ),
            ).values("name", "price", "currency", "status",
                     "active_count", "trialing_count", "cancelled_count")
        )

        from .models import SubscriptionPayment
        revenue = SubscriptionPayment.objects.total_revenue()

        status_totals = dict(
            UserSubscription.objects
            .values("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )

        return Response({
            "status_breakdown": status_totals,
            "total_revenue": str(revenue),
            "plans": plan_stats,
        })
