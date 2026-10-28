# api/djoyalty/viewsets/engagement/BadgeViewSet.py
"""
BadgeViewSet -- Badge catalog + manual award + customer badges।

FIXED: BadgeService (services/engagement/BadgeService.py) was fully
built but never called from any viewset। Only my_badges existed --
no way for admin to manually award a badge or trigger badge check।
Added: award, trigger_check, award_bulk, revoke endpoints।

Endpoints:
  GET    /badges/                     -- badge catalog
  GET    /badges/{id}/                -- badge detail
  GET    /badges/my-badges/           -- customer's earned badges
  POST   /badges/award/               -- admin: manually award a badge
  POST   /badges/award-bulk/          -- admin: award to multiple customers
  POST   /badges/trigger-check/       -- trigger automatic badge check
  DELETE /badges/{id}/revoke/         -- admin: revoke a badge
  GET    /badges/eligible/            -- badges customer is eligible for
"""
import logging
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ...models.engagement import Badge, UserBadge
from ...serializers.BadgeSerializer import BadgeSerializer, UserBadgeSerializer
from ...pagination import DjoyaltyPagePagination
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet

logger = logging.getLogger(__name__)


class BadgeViewSet(DjoyaltyBaseViewSet, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset           = Badge.objects.all().order_by('name')
    serializer_class   = BadgeSerializer
    pagination_class   = DjoyaltyPagePagination
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['name', 'trigger', 'description']
    ordering_fields    = ['name', 'threshold', 'points_reward', 'created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('active_only') == 'true':
            qs = qs.filter(is_active=True)
        trigger = self.request.query_params.get('trigger')
        if trigger:
            qs = qs.filter(trigger=trigger)
        return qs

    # ── Customer: my badges ────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='my-badges')
    def my_badges(self, request):
        """Customer's earned badges -- all time।"""
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return self.err('customer_id required')
        qs = UserBadge.objects.filter(
            customer_id=customer_id
        ).select_related('badge').order_by('-earned_at')
        return Response(UserBadgeSerializer(qs, many=True).data)

    # ── Customer: eligible badges ──────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='eligible')
    def eligible(self, request):
        """
        Badges the customer is close to earning or hasn't earned yet।
        Useful for progress UI ("You need 200 more points for Gold Badge")।
        """
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return self.err('customer_id required')
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        customer = get_object_or_404(Customer, pk=customer_id)
        lp       = customer.loyalty_points.first()
        balance  = lp.balance if lp else 0

        earned_ids = set(
            UserBadge.objects.filter(customer=customer).values_list('badge_id', flat=True)
        )
        all_badges = Badge.objects.filter(is_active=True).order_by('threshold')
        result = []
        for badge in all_badges:
            if badge.id in earned_ids:
                continue
            progress = float(balance) / float(badge.threshold) if badge.threshold else 1.0
            result.append({
                'badge':       BadgeSerializer(badge).data,
                'progress_pct': round(min(progress * 100, 99), 1),
                'points_needed': max(0, float(badge.threshold) - float(balance)),
                'earned':       False,
            })
        return Response({'eligible': result[:20]})

    # ── Admin: award single badge ──────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='award',
            permission_classes=[IsLoyaltyAdmin])
    def award(self, request):
        """
        Admin manually awards a badge to a customer।
        FIXED: BadgeService.award_specific() was built but never callable via API。
        Body: { "customer_id": 1, "badge_id": 5, "reason": "..." }
        """
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        from ...services.engagement.BadgeService import BadgeService

        customer_id = request.data.get('customer_id')
        badge_id    = request.data.get('badge_id')
        reason      = request.data.get('reason', 'Manual admin award')

        if not customer_id or not badge_id:
            return Response(
                {'error': 'customer_id and badge_id required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        customer = get_object_or_404(Customer, pk=customer_id)
        badge    = get_object_or_404(Badge, pk=badge_id)

        # Check already earned
        if UserBadge.objects.filter(customer=customer, badge=badge).exists():
            return Response(
                {'error': f'Customer already has badge: {badge.name}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ub = BadgeService.award_specific(
                customer=customer, badge=badge,
                reason=reason, tenant=customer.tenant,
            )
            logger.info('Admin awarded badge %s to %s', badge.name, customer.code)
            return Response({
                'status':  'awarded',
                'badge':   UserBadgeSerializer(ub).data,
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return self.err(str(e))

    # ── Admin: award bulk ─────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='award-bulk',
            permission_classes=[IsLoyaltyAdmin])
    def award_bulk(self, request):
        """
        Award one badge to many customers।
        Body: { "badge_id": 5, "customer_ids": [1,2,3], "reason": "..." }
        """
        from ...models.core import Customer
        from ...services.engagement.BadgeService import BadgeService

        badge_id     = request.data.get('badge_id')
        customer_ids = request.data.get('customer_ids', [])
        reason       = request.data.get('reason', 'Bulk admin award')

        if not badge_id or not customer_ids:
            return Response(
                {'error': 'badge_id and customer_ids required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        badge = Badge.objects.filter(pk=badge_id).first()
        if not badge:
            return self.not_found('Badge not found.')

        awarded, skipped = [], []
        for cid in customer_ids:
            try:
                customer = Customer.objects.get(pk=cid)
                if UserBadge.objects.filter(customer=customer, badge=badge).exists():
                    skipped.append(cid)
                    continue
                BadgeService.award_specific(
                    customer=customer, badge=badge,
                    reason=reason, tenant=customer.tenant,
                )
                awarded.append(cid)
            except Exception as e:
                logger.warning('Bulk badge award failed for customer %s: %s', cid, e)
                skipped.append(cid)

        return Response({
            'status':  'complete',
            'awarded': len(awarded),
            'skipped': len(skipped),
            'awarded_customer_ids': awarded,
        })

    # ── Admin: trigger automatic badge check ─────────────────────────────────
    @action(detail=False, methods=['post'], url_path='trigger-check',
            permission_classes=[IsLoyaltyAdmin])
    def trigger_check(self, request):
        """
        Trigger automatic badge eligibility check for a customer।
        Uses BadgeService.check_and_award() -- fires for all matching triggers。
        Body: { "customer_id": 1, "trigger": "points_balance" }
        """
        from django.shortcuts import get_object_or_404
        from decimal import Decimal
        from ...models.core import Customer
        from ...services.engagement.BadgeService import BadgeService

        customer_id = request.data.get('customer_id')
        trigger     = request.data.get('trigger', 'points_balance')
        if not customer_id:
            return self.err('customer_id required')

        customer = get_object_or_404(Customer, pk=customer_id)
        lp       = customer.loyalty_points.first()
        value    = Decimal(str(lp.lifetime_earned if lp else 0))

        try:
            awarded = BadgeService.check_and_award(
                customer=customer,
                trigger=trigger,
                current_value=value,
                tenant=customer.tenant,
            )
            return Response({
                'badges_awarded': len(awarded),
                'badges': [UserBadgeSerializer(ub).data for ub in awarded],
            })
        except Exception as e:
            return self.err(str(e), http_status=500)

    # ── Admin: revoke badge ────────────────────────────────────────────────────
    @action(detail=True, methods=['delete'], url_path='revoke',
            permission_classes=[IsLoyaltyAdmin])
    def revoke(self, request, pk=None):
        """
        Admin revokes a UserBadge (by UserBadge pk, not Badge pk)।
        Rarely needed -- only for corrective actions।
        """
        ub = UserBadge.objects.filter(pk=pk).first()
        if not ub:
            return self.not_found('UserBadge not found.')
        badge_name   = ub.badge.name
        customer_code = ub.customer.code
        ub.delete()
        logger.info('Admin revoked badge %s from %s', badge_name, customer_code)
        return Response({'status': 'revoked', 'badge': badge_name, 'customer': customer_code})
