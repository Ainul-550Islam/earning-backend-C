# api/djoyalty/viewsets/advanced/MembershipViewSet.py
"""
MembershipViewSet -- Paid Membership API (Amazon Prime / Costco style)।

AUDIT FIX (Architecture -- Critical):
  Previously imported from paid_membership.py directly in 8 action methods:
    from ...paid_membership import MembershipPlan          # direct model import
    from ...paid_membership import CustomerMembership      # direct model import
    from ...paid_membership import MembershipBenefitsManager
    MembershipPlan.objects.filter(...)                     # ORM in viewset
    CustomerMembership.objects.create(...)                 # ORM in viewset

  This violates the "One task, one owner" service layer principle।

  NOW: ALL business logic delegated to SubscriptionLoyaltyService।
  Viewset only handles:
    - Input validation via serializers
    - Customer resolution
    - HTTP response shaping
    - Permission checks

  SubscriptionLoyaltyService is the single owner of:
    - Plan queries          (get_active_plans, get_plan_by_id)
    - Membership queries    (get_active_membership, get_membership_benefits,
                             get_all_active_memberships)
    - Mutations             (subscribe_to_plan, renew_membership,
                             cancel_membership, credit_monthly_bonus)

Endpoints (preserved -- no endpoint removed):
  GET  /memberships/plans/                   -- list all active plans
  GET  /memberships/plans/{id}/              -- plan detail
  GET  /memberships/my/                      -- customer's active membership
  POST /memberships/subscribe/               -- subscribe to a plan
  POST /memberships/my/renew/                -- renew membership
  POST /memberships/my/cancel/               -- cancel membership
  GET  /memberships/my/benefits/             -- active benefits summary
  GET  /memberships/admin/active/            -- admin: all active memberships
  POST /memberships/admin/{id}/credit-bonus/ -- admin: credit monthly bonus
"""
import logging

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...permissions import IsLoyaltyAdmin
from ...serializers.MembershipSerializer import (
    AdminCreditBonusSerializer,
    CustomerMembershipSerializer,
    MembershipBenefitsSerializer,
    MembershipPlanSerializer,
    MembershipRenewSerializer,
    MembershipSubscribeSerializer,
)
from ...services.advanced.SubscriptionLoyaltyService import SubscriptionLoyaltyService
from ...mixins import DjoyaltyBaseViewSet

logger = logging.getLogger(__name__)


class MembershipViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _get_customer(self, request):
        customer = getattr(request, 'loyalty_customer', None)
        if customer:
            return customer
        cid = request.query_params.get('customer_id') or request.data.get('customer_id')
        if cid:
            from ...models.core import Customer
            return Customer.objects.filter(pk=cid).first()
        return None

    # ── Plans ──────────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='plans')
    def plans(self, request):
        """
        List all active membership plans।
        AUDIT FIX: was calling MembershipPlan.objects.filter() directly in view।
        NOW: delegates to SubscriptionLoyaltyService.get_active_plans()।
        """
        qs         = SubscriptionLoyaltyService.get_active_plans()
        serializer = MembershipPlanSerializer(qs, many=True)
        return Response({'plans': serializer.data, 'count': len(serializer.data)})

    @action(detail=True, methods=['get'], url_path='plans')
    def plan_detail(self, request, pk=None):
        """
        Single plan detail।
        AUDIT FIX: was calling MembershipPlan.objects.filter() directly in view।
        NOW: delegates to SubscriptionLoyaltyService.get_plan_by_id()।
        """
        plan = SubscriptionLoyaltyService.get_plan_by_id(pk)
        if not plan:
            return self.not_found('Plan not found.')
        return Response(MembershipPlanSerializer(plan).data)

    # ── My Membership ─────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='my')
    def my_membership(self, request):
        """
        Customer's active membership।
        AUDIT FIX: was calling MembershipBenefitsManager.get_active_membership() directly in view।
        NOW: delegates to SubscriptionLoyaltyService.get_active_membership()।
        """
        customer   = self._get_customer(request)
        membership = SubscriptionLoyaltyService.get_active_membership(customer)
        if not membership:
            return Response({'membership': None, 'message': 'No active membership'})
        return Response({'membership': CustomerMembershipSerializer(membership).data})

    # ── Benefits ──────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='my/benefits')
    def my_benefits(self, request):
        """
        Active membership benefits summary।
        AUDIT FIX: was computing benefits with ORM calls directly in view।
        NOW: delegates to SubscriptionLoyaltyService.get_membership_benefits()।
        """
        customer = self._get_customer(request)
        data     = SubscriptionLoyaltyService.get_membership_benefits(customer)
        return Response(MembershipBenefitsSerializer(data).data)

    # ── Subscribe ─────────────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='subscribe')
    def subscribe(self, request):
        """
        Subscribe to a plan।
        AUDIT FIX: was calling MembershipPlan.objects.filter() and
        CustomerMembership.objects.create() directly in view।
        NOW: delegates to SubscriptionLoyaltyService.subscribe_to_plan()।
        """
        input_serializer = MembershipSubscribeSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        customer = self._get_customer(request)
        if not customer:
            return self.not_found('Customer not found.')

        result = SubscriptionLoyaltyService.subscribe_to_plan(
            customer          = customer,
            plan_id           = data['plan_id'],
            payment_method    = data['payment_method'],
            payment_reference = data['payment_reference'],
            auto_renew        = data['auto_renew'],
        )

        if not result['success']:
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'status':     'subscribed',
            'membership': CustomerMembershipSerializer(result['membership']).data,
        }, status=status.HTTP_201_CREATED)

    # ── Renew ─────────────────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='my/renew')
    def renew(self, request):
        """
        Renew membership।
        AUDIT FIX: was calling membership.renew() directly in view after
        manually fetching the membership object in the view layer।
        NOW: delegates to SubscriptionLoyaltyService.renew_membership()।
        """
        input_serializer = MembershipRenewSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        customer = self._get_customer(request)
        if not customer:
            return self.not_found('Customer not found.')

        result = SubscriptionLoyaltyService.renew_membership(
            customer          = customer,
            payment_reference = input_serializer.validated_data['payment_reference'],
        )

        if not result['success']:
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'status':     'renewed',
            'membership': CustomerMembershipSerializer(result['membership']).data,
        })

    # ── Cancel ────────────────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='my/cancel')
    def cancel(self, request):
        """
        Cancel membership -- keeps access until period end।
        AUDIT FIX: was calling membership.cancel() directly in view।
        NOW: delegates to SubscriptionLoyaltyService.cancel_membership()।
        """
        customer = self._get_customer(request)
        if not customer:
            return self.not_found('Customer not found.')

        result = SubscriptionLoyaltyService.cancel_membership(customer)

        if not result['success']:
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'status':       'cancelled',
            'access_until': result['access_until'],
            'membership':   CustomerMembershipSerializer(result['membership']).data,
        })

    # ── Admin: All Active ──────────────────────────────────────────────────────
    @action(
        detail=False, methods=['get'], url_path='admin/active',
        permission_classes=[IsLoyaltyAdmin],
    )
    def admin_active(self, request):
        """
        Admin: list all active memberships।
        AUDIT FIX: was calling CustomerMembership.objects.filter() directly in view।
        NOW: delegates to SubscriptionLoyaltyService.get_all_active_memberships()।
        """
        plan_filter = request.query_params.get('plan')
        qs          = SubscriptionLoyaltyService.get_all_active_memberships(
            plan_filter=plan_filter,
        )
        serializer = CustomerMembershipSerializer(qs[:200], many=True)
        return Response({'count': len(serializer.data), 'memberships': serializer.data})

    # ── Admin: Credit Bonus ────────────────────────────────────────────────────
    @action(
        detail=True, methods=['post'], url_path='credit-bonus',
        permission_classes=[IsLoyaltyAdmin],
    )
    def credit_bonus(self, request, pk=None):
        """
        Admin: manually credit monthly bonus points।
        AUDIT FIX: was calling MembershipBenefitsManager.credit_monthly_bonus() in view।
        NOW: delegates to SubscriptionLoyaltyService.credit_monthly_bonus()。
        Membership lookup still happens here (HTTP concern -- resolving resource by PK)।
        """
        input_serializer = AdminCreditBonusSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        # Membership lookup is an HTTP concern (resolving resource by PK from URL)
        try:
            from ...paid_membership import CustomerMembership
            membership = get_object_or_404(CustomerMembership, pk=pk)
        except Exception:
            return self.not_found('Membership not found.')

        result = SubscriptionLoyaltyService.credit_monthly_bonus(
            membership = membership,
            force      = input_serializer.validated_data['force'],
        )

        if not result['success']:
            return Response({'error': result.get('error', 'Operation failed.')},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'status':     'credited' if result.get('credited') else 'skipped',
            'membership': CustomerMembershipSerializer(membership).data,
        })
