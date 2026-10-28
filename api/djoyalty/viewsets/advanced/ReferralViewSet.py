from ...permissions import IsLoyaltyAdmin
# api/djoyalty/viewsets/advanced/ReferralViewSet.py
"""
ReferralViewSet -- Referral link, click tracking, conversion API।
FIXED: ReferralPointsService (services/earn/ReferralPointsService.py)
was built but never called from any viewset。
Added: /convert/ action that uses ReferralPointsService to award referral points。
"""
import secrets
import string
import logging

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from ...serializers.ReferralSerializer import (
    ReferralLinkSerializer, ReferralClickSerializer, ReferralConversionSerializer,
)
from ...serializers.AnalyticsSerializer import ReferralConvertInputSerializer
from ...mixins import DjoyaltyBaseViewSet

logger = logging.getLogger(__name__)


class ReferralViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    # ── Get or create referral link ────────────────────────────────────────────
    @action(detail=False, methods=['get', 'post'])
    def my_link(self, request):
        """Get or create referral link for customer।"""
        from ...models.core import Customer
        from ...models.referral import ReferralLink

        customer_id = (
            request.data.get('customer_id')
            or request.query_params.get('customer_id')
        )
        try:
            customer = Customer.objects.get(id=customer_id, is_active=True)
        except Customer.DoesNotExist:
            return self.not_found('Customer not found')

        ref_link, created = ReferralLink.objects.get_or_create(
            customer=customer,
            defaults={
                'tenant': customer.tenant,
                'code': customer.referral_code or ''.join(
                    secrets.choice(string.ascii_uppercase + string.digits)
                    for _ in range(8)
                ),
            },
        )
        return Response(ReferralLinkSerializer(ref_link).data)

    # ── Track click ────────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def track_click(self, request):
        """Track a click on a referral link। Public endpoint।"""
        from ...models.referral import ReferralLink, ReferralClick

        code = request.query_params.get('code', '')
        try:
            ref_link = ReferralLink.objects.get(code=code.upper(), is_active=True)
        except ReferralLink.DoesNotExist:
            return self.not_found('Invalid referral code')

        ip        = request.META.get('REMOTE_ADDR', '')
        ua        = request.META.get('HTTP_USER_AGENT', '')[:500]
        is_unique = not ReferralClick.objects.filter(
            referral_link=ref_link, ip_address=ip
        ).exists()

        ReferralClick.objects.create(
            referral_link=ref_link, ip_address=ip,
            user_agent=ua, is_unique=is_unique,
        )
        ref_link.total_clicks += 1
        if is_unique:
            ref_link.unique_clicks += 1
        ref_link.save(update_fields=['total_clicks', 'unique_clicks'])

        return Response({'redirect': ref_link.destination_url or '/', 'code': code})

    # ── Convert referral ───────────────────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='convert')
    def convert(self, request):
        """
        Record a referral conversion and award points to both parties।

        FIXED: ReferralPointsService (earn/ReferralPointsService.py)
        had award_referral_points(), check_rule(), validate_referral()
        but no viewset called it -- referral conversions were tracked
        without any points being awarded。

        Body: { "referral_code": "ABC123", "customer_id": 456,
                "conversion_type": "signup", "order_value": 1500.00 }
        """
        serializer = ReferralConvertInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from ...models.referral import ReferralLink, ReferralConversion
        from ...models.core import Customer

        # Validate referral code
        code = data['referral_code'].upper()
        try:
            ref_link = ReferralLink.objects.get(code=code, is_active=True)
        except ReferralLink.DoesNotExist:
            return self.not_found('Invalid referral code')

        # Validate referred customer
        try:
            referred_customer = Customer.objects.get(
                pk=data['customer_id'], is_active=True
            )
        except Customer.DoesNotExist:
            return self.not_found('Customer not found')

        referrer = ref_link.customer

        # Prevent self-referral
        if referrer.pk == referred_customer.pk:
            return Response(
                {'error': 'Self-referral not allowed'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if already converted
        already = ReferralConversion.objects.filter(
            referral_link=ref_link,
            referred_customer=referred_customer,
        ).exists()
        if already:
            return Response(
                {'error': 'Referral already converted for this customer'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Award points using ReferralPointsService
        referrer_points    = 0
        referred_points    = 0
        award_error        = None
        try:
            from ...services.earn.ReferralPointsService import ReferralPointsService

            # Award to referrer
            referrer_points = ReferralPointsService.award_referral_points(
                customer=referrer,
                conversion_type=data['conversion_type'],
                order_value=data.get('order_value'),
                role='referrer',
                tenant=referrer.tenant,
            )
            # Award to referred customer
            referred_points = ReferralPointsService.award_referral_points(
                customer=referred_customer,
                conversion_type=data['conversion_type'],
                order_value=data.get('order_value'),
                role='referred',
                tenant=referred_customer.tenant,
            )
        except Exception as e:
            award_error = str(e)
            logger.warning('ReferralPointsService.award_referral_points error: %s', e)

        # Record conversion regardless of award result
        conversion = ReferralConversion.objects.create(
            referral_link=ref_link,
            referrer=referrer,
            referred_customer=referred_customer,
            tenant=referrer.tenant,
            conversion_type=data['conversion_type'],
            order_value=data.get('order_value'),
            referrer_points=referrer_points,
            referred_points=referred_points,
            status='completed',
        )

        # Update referral link counts
        ref_link.total_conversions += 1
        ref_link.total_points_earned += referrer_points + referred_points
        ref_link.save(update_fields=['total_conversions', 'total_points_earned'])

        response_data = {
            'status':            'converted',
            'conversion_id':     conversion.id,
            'referrer_points':   str(referrer_points),
            'referred_points':   str(referred_points),
            'conversion_type':   data['conversion_type'],
        }
        if award_error:
            response_data['award_warning'] = award_error

        return Response(response_data, status=status.HTTP_201_CREATED)

    # ── My conversions ─────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'])
    def conversions(self, request):
        """Customer's referral conversion history।"""
        from ...models.referral import ReferralConversion

        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return self.err('customer_id required')

        conversions = ReferralConversion.objects.filter(
            referrer_id=customer_id
        ).order_by('-converted_at')[:20].values(
            'id', 'conversion_type', 'referrer_points',
            'referred_points', 'status', 'converted_at',
        )
        return Response({'results': list(conversions)})

    # ── Referral stats ─────────────────────────────────────────────────────────
    @action(detail=False, methods=['get'], url_path='my-stats')
    def my_stats(self, request):
        """Customer's full referral stats -- clicks, conversions, total points earned।"""
        from ...models.referral import ReferralLink

        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return self.err('customer_id required')

        ref_link = ReferralLink.objects.filter(customer_id=customer_id).first()
        if not ref_link:
            return Response({
                'has_referral_link':  False,
                'total_clicks':       0,
                'unique_clicks':      0,
                'total_conversions':  0,
                'total_points_earned': '0',
            })

        return Response({
            'has_referral_link':    True,
            'code':                 ref_link.code,
            'short_url':            ref_link.short_url or f'/ref/{ref_link.code}',
            'total_clicks':         ref_link.total_clicks,
            'unique_clicks':        ref_link.unique_clicks,
            'total_conversions':    ref_link.total_conversions,
            'total_points_earned':  str(ref_link.total_points_earned),
        })
    @action(detail=False, methods=['get'], url_path='program')
    def program(self, request):
        """
        FIXED: ReferralProgram had NO API endpoint.
        Returns current referral program configuration.
        """
        from ...models.referral import ReferralProgram
        tenant = getattr(request, 'tenant', None)
        prog = ReferralProgram.objects.filter(is_active=True)
        if tenant: prog = prog.filter(tenant=tenant)
        prog = prog.first()
        if not prog:
            return Response({'program': None})
        return Response({'program': {
            'id': prog.id, 'name': prog.name,
            'referrer_reward_type': prog.referrer_reward_type,
            'referrer_points': str(getattr(prog, 'referrer_points', 0)),
            'referred_reward_type': prog.referred_reward_type,
            'referred_points': str(getattr(prog, 'referred_points', 0)),
            'is_active': prog.is_active,
        }})

    @action(detail=False, methods=['get'], url_path='points-rules', permission_classes=[IsLoyaltyAdmin])
    def points_rules(self, request):
        """
        FIXED: ReferralPointsRule had NO API endpoint.
        Admin can query the referral points earn rules.
        """
        from ...models.campaigns import ReferralPointsRule
        qs = ReferralPointsRule.objects.filter(is_active=True).order_by('conversion_type')
        return Response({'rules': [{
            'id': r.id, 'conversion_type': r.conversion_type,
            'referrer_points': str(r.referrer_points),
            'referred_points': str(r.referred_points),
            'min_order_value': str(getattr(r, 'min_order_value', 0)),
            'is_active': r.is_active,
        } for r in qs]})
