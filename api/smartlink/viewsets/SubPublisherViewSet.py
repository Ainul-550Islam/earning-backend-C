"""
SmartLink SubPublisher ViewSet
================================
Publisher self-serve referral chain management.

Publishers can:
  - Get their unique referral code / referral link
  - See who they've referred (their sub-publishers)
  - View their referral commission earnings
  - Deactivate a sub-publisher relationship

Publishers who were referred can:
  - See who referred them and the commission structure

Admin can:
  - View and manage all sub-publisher relationships
  - Approve/reject referral relationships
  - Override commission rates

Endpoints:
  GET    /api/smartlink/publisher/sub-publishers/             — list my sub-publishers
  GET    /api/smartlink/publisher/sub-publishers/earnings/    — commission earnings summary
  GET    /api/smartlink/publisher/sub-publishers/referral-link/ — my referral code + link
  POST   /api/smartlink/publisher/sub-publishers/join/        — join via referral code
  DELETE /api/smartlink/publisher/sub-publishers/{id}/deactivate/ — deactivate a referral

  Admin:
  GET    /api/smartlink/admin/sub-publishers/              — all relationships
  POST   /api/smartlink/admin/sub-publishers/{id}/approve/ — approve pending referral
  PATCH  /api/smartlink/admin/sub-publishers/{id}/         — edit commission rates
"""
import logging
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from api.smartlink.models.publisher import SubPublisher
from api.smartlink.serializers.SubPublisherSerializer import (
    SubPublisherReadSerializer,
    SubPublisherCreateSerializer,
    SubPublisherAdminSerializer,
    SubPublisherEarningsSerializer,
)

User = get_user_model()
logger = logging.getLogger('smartlink.viewsets.sub_publisher')


class SubPublisherViewSet(viewsets.ViewSet):
    """
    SubPublisher referral chain API.
    Authenticated publishers manage their own referral network.
    Admin can manage all relationships.
    """
    permission_classes = [IsAuthenticated]

    # ── Publisher: list my sub-publishers ────────────────────────────────────

    def list(self, request):
        """
        GET /api/smartlink/publisher/sub-publishers/
        Return all sub-publishers (referred by me).
        """
        qs = SubPublisher.objects.filter(
            parent_publisher=request.user,
        ).select_related('child_publisher').order_by('-created_at')

        serializer = SubPublisherReadSerializer(
            qs, many=True, context={'request': request}
        )
        return Response({
            'count':          qs.count(),
            'active_count':   qs.filter(is_active=True).count(),
            'sub_publishers': serializer.data,
        })

    def retrieve(self, request, pk=None):
        """
        GET /api/smartlink/publisher/sub-publishers/{id}/
        Detail view of a single sub-publisher relationship.
        """
        from django.shortcuts import get_object_or_404
        if request.user.is_staff:
            obj = get_object_or_404(SubPublisher, pk=pk)
        else:
            obj = get_object_or_404(
                SubPublisher, pk=pk, parent_publisher=request.user
            )
        serializer = SubPublisherReadSerializer(obj, context={'request': request})
        return Response(serializer.data)

    # ── Publisher: get referral link ──────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='referral-link')
    def referral_link(self, request):
        """
        GET /api/smartlink/publisher/sub-publishers/referral-link/
        Return the publisher's referral code and shareable signup link.
        Auto-generates a referral code if none exists.
        """
        from django.conf import settings

        # Find or create a SubPublisher stub for this publisher
        # (A publisher doesn't need a parent to have a referral code)
        existing = SubPublisher.objects.filter(
            parent_publisher=request.user,
        ).values('referral_code').first()

        if existing and existing.get('referral_code'):
            code = existing['referral_code']
        else:
            # Generate a new referral code for this publisher
            code = self._get_or_create_referral_code(request.user)

        base_url = getattr(settings, 'SMARTLINK_FRONTEND_URL', 'https://app.smartlink.io')
        referral_url = f"{base_url}/register?ref={code}"

        return Response({
            'referral_code': code,
            'referral_link': referral_url,
            'commission_info': (
                'You earn a percentage of earnings from publishers you refer. '
                'Commission rates are set by the platform admin.'
            ),
        })

    # ── Publisher: join via referral code ─────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='join')
    def join(self, request):
        """
        POST /api/smartlink/publisher/sub-publishers/join/
        Body: {"referral_code": "ABCD1234"}

        Link this publisher account to a parent via referral code.
        Only allowed once (a publisher can only be referred by one parent).
        """
        # Check not already referred by someone
        if SubPublisher.objects.filter(child_publisher=request.user).exists():
            return Response(
                {'detail': 'You are already linked to a referral partner.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SubPublisherCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['referral_code']

        # Find a SubPublisher row that has this referral code (any row for that parent)
        parent_sub = SubPublisher.objects.filter(
            referral_code=code, is_active=True
        ).first()

        if not parent_sub:
            return Response(
                {'detail': 'Invalid or inactive referral code.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prevent self-referral
        if parent_sub.parent_publisher == request.user:
            return Response(
                {'detail': 'You cannot refer yourself.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate a fresh code for this new relationship (don't duplicate the parent's code)
        fresh_code = self._get_or_create_referral_code(request.user)
        new_rel = SubPublisher.objects.create(
            parent_publisher=parent_sub.parent_publisher,
            child_publisher=request.user,
            commission_type=parent_sub.commission_type,
            commission_pct=parent_sub.commission_pct,
            commission_flat=parent_sub.commission_flat,
            referral_code=fresh_code,
            is_active=True,
        )

        logger.info(
            f"SubPublisher joined: parent={parent_sub.parent_publisher.username} "
            f"child={request.user.username} via code={code}"
        )
        return Response(
            SubPublisherReadSerializer(new_rel, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    # ── Publisher: earnings summary ───────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='earnings')
    def earnings(self, request):
        """
        GET /api/smartlink/publisher/sub-publishers/earnings/
        Return commission earnings summary for the requesting publisher.
        """
        from django.conf import settings
        from django.db.models import Sum

        qs = SubPublisher.objects.filter(parent_publisher=request.user)

        total_referred  = qs.count()
        active_referred = qs.filter(is_active=True).count()
        lifetime_earned = qs.aggregate(
            total=Sum('lifetime_earned')
        )['total'] or Decimal('0')

        # Get referral code
        first = qs.first()
        code = first.referral_code if first else self._get_or_create_referral_code(request.user)

        base_url = getattr(settings, 'SMARTLINK_FRONTEND_URL', 'https://app.smartlink.io')

        data = {
            'total_referred':         total_referred,
            'active_referred':        active_referred,
            'lifetime_commission':    lifetime_earned,
            'pending_commission':     Decimal('0'),     # placeholder (hold period)
            'this_month_commission':  Decimal('0'),     # placeholder (no per-period tracking yet)
            'referral_code':          code,
            'referral_link':          f"{base_url}/register?ref={code}",
        }
        serializer = SubPublisherEarningsSerializer(data)
        return Response(serializer.data)

    # ── Publisher: deactivate sub-publisher relationship ──────────────────────

    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        """
        POST /api/smartlink/publisher/sub-publishers/{id}/deactivate/
        Stop earning commission from this sub-publisher going forward.
        Does NOT delete the relationship or reverse past earnings.
        """
        from django.shortcuts import get_object_or_404
        obj = get_object_or_404(
            SubPublisher, pk=pk, parent_publisher=request.user
        )
        if not obj.is_active:
            return Response(
                {'detail': 'This referral relationship is already inactive.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        SubPublisher.objects.filter(pk=obj.pk).update(is_active=False)
        logger.info(
            f"SubPublisher deactivated: parent={request.user.username} "
            f"child={obj.child_publisher.username}"
        )
        return Response({'detail': 'Referral relationship deactivated.'})

    # ── Admin: list all ───────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='admin/all',
            permission_classes=[IsAuthenticated])
    def admin_list(self, request):
        """
        GET /api/smartlink/publisher/sub-publishers/admin/all/
        Admin only: list all SubPublisher relationships.
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Admin only.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = SubPublisher.objects.all().select_related(
            'parent_publisher', 'child_publisher'
        ).order_by('-created_at')

        serializer = SubPublisherAdminSerializer(qs, many=True)
        return Response({
            'count':   qs.count(),
            'results': serializer.data,
        })

    @action(detail=True, methods=['patch'], url_path='admin/update',
            permission_classes=[IsAuthenticated])
    def admin_update(self, request, pk=None):
        """
        PATCH /api/smartlink/publisher/sub-publishers/{id}/admin/update/
        Admin only: edit commission rates or active status.
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        from django.shortcuts import get_object_or_404
        obj = get_object_or_404(SubPublisher, pk=pk)
        serializer = SubPublisherAdminSerializer(
            obj, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(f"SubPublisher #{pk} updated by admin {request.user.username}")
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='admin/approve',
            permission_classes=[IsAuthenticated])
    def admin_approve(self, request, pk=None):
        """
        POST /api/smartlink/publisher/sub-publishers/{id}/admin/approve/
        Admin only: approve a pending referral relationship.
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        from django.shortcuts import get_object_or_404
        obj = get_object_or_404(SubPublisher, pk=pk)
        SubPublisher.objects.filter(pk=obj.pk).update(
            is_active=True,
            approved_at=timezone.now(),
        )
        logger.info(
            f"SubPublisher #{pk} approved by {request.user.username}: "
            f"{obj.parent_publisher.username} → {obj.child_publisher.username}"
        )
        return Response({'detail': 'Referral relationship approved and activated.'})

    # ── Helper ────────────────────────────────────────────────────────────────

    def _get_or_create_referral_code(self, user) -> str:
        """
        Get existing referral code for a publisher or generate a new one.
        Stored on the first SubPublisher row for that publisher.
        """
        import secrets
        import string
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(10):
            candidate = ''.join(secrets.choice(alphabet) for _ in range(8))
            if not SubPublisher.objects.filter(referral_code=candidate).exists():
                return candidate
        return secrets.token_urlsafe(6).upper()[:8]
