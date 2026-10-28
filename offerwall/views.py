# offerwall/views.py
"""
DRF ViewSets for the Offerwall app.

Endpoints:
  GET  /offerwall/offers/                        — public offer list (active)
  GET  /offerwall/offers/{id}/                   — offer detail
  POST /offerwall/offers/{id}/click/             — record click + get tracked URL
  GET  /offerwall/offers/{id}/conversions/       — admin: conversions for offer
  GET  /offerwall/my-conversions/                — user's own conversions
  POST /offerwall/postback/                      — CPAlead postback (webhook)
  GET  /offerwall/admin/offers/                  — admin: all offers (any status)
  POST /offerwall/admin/offers/                  — admin: create offer
  PATCH /offerwall/admin/offers/{id}/            — admin: update offer
  DELETE /offerwall/admin/offers/{id}/           — admin: delete offer
  POST /offerwall/admin/conversions/{id}/approve/ — admin: approve conversion
  POST /offerwall/admin/conversions/{id}/reject/  — admin: reject conversion
"""
import logging
from django.utils import timezone
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from django_filters.rest_framework import DjangoFilterBackend

from .models import Offer, OfferClick, OfferConversion
from .serializers import (
    OfferListSerializer, OfferDetailSerializer,
    OfferClickSerializer, OfferConversionSerializer,
    OfferConversionAdminSerializer,
)

logger = logging.getLogger('offerwall')


class OfferViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public read-only offer feed.
    Only active, non-expired offers are returned.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['source', 'target_device', 'is_featured']
    ordering_fields = ['payout_usd', 'virtual_payout', 'total_conversions', 'created_at']
    ordering = ['-is_featured', '-payout_usd']

    def get_queryset(self):
        qs = Offer.objects.filter(status=Offer.STATUS_ACTIVE)
        # Filter out expired offers
        qs = qs.filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
        )
        # Device targeting
        user_agent = self.request.META.get('HTTP_USER_AGENT', '').lower()
        is_mobile = any(kw in user_agent for kw in ['mobile', 'android', 'iphone'])
        device = Offer.DEVICE_MOBILE if is_mobile else Offer.DEVICE_DESKTOP
        qs = qs.filter(
            models.Q(target_device=Offer.DEVICE_ALL) |
            models.Q(target_device=device)
        )
        # Level targeting
        user = self.request.user
        level = getattr(user, 'level', 0) or 0
        qs = qs.filter(min_user_level__lte=level)
        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return OfferDetailSerializer
        return OfferListSerializer

    @action(detail=True, methods=['post'])
    def click(self, request, pk=None):
        """Record click and return tracked URL."""
        offer = self.get_object()
        if not offer.is_active:
            return Response({'error': 'Offer is not active'},
                            status=status.HTTP_400_BAD_REQUEST)
        from api.cms.helpers import get_client_ip, detect_device, get_country_from_ip
        ip = get_client_ip(request)
        click = OfferClick.objects.create(
            offer=offer,
            user=request.user,
            ip_address=ip,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            country=get_country_from_ip(ip),
            device_type=detect_device(request.META.get('HTTP_USER_AGENT', '')),
            subid=str(request.user.pk),
        )
        # Increment counter atomically
        Offer.objects.filter(pk=offer.pk).update(
            total_clicks=models.F('total_clicks') + 1
        )
        # Build tracked URL
        tracked_url = f"{offer.click_url}&subid={click.subid}&clickid={click.pk}"
        return Response({
            'click_id': str(click.id),
            'tracked_url': tracked_url,
            'offer_title': offer.title,
        })

    @action(detail=True, methods=['get'],
            permission_classes=[permissions.IsAdminUser])
    def conversions(self, request, pk=None):
        """Admin: list conversions for this offer."""
        offer = self.get_object()
        qs = offer.conversions.order_by('-converted_at')[:100]
        return Response(OfferConversionAdminSerializer(qs, many=True).data)


class MyConversionsViewSet(viewsets.ReadOnlyModelViewSet):
    """User's own conversion history."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OfferConversionSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'offer']
    ordering = ['-converted_at']

    def get_queryset(self):
        return OfferConversion.objects.filter(
            user=self.request.user
        ).select_related('offer')


class AdminOfferViewSet(viewsets.ModelViewSet):
    """Admin full CRUD for offers."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAdminUser]
    serializer_class = OfferDetailSerializer
    queryset = Offer.objects.all().order_by('-created_at')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'source', 'is_featured', 'target_device']
    search_fields = ['title', 'external_id']
    ordering_fields = ['payout_usd', 'total_conversions', 'created_at']


class AdminConversionViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin: view and approve/reject conversions."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAdminUser]
    serializer_class = OfferConversionAdminSerializer
    queryset = OfferConversion.objects.select_related('offer', 'user').order_by('-converted_at')
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'offer']

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        conv = self.get_object()
        if conv.status != OfferConversion.STATUS_PENDING:
            return Response({'error': 'Only pending conversions can be approved'},
                            status=status.HTTP_400_BAD_REQUEST)
        conv.status = OfferConversion.STATUS_APPROVED
        conv.approved_at = timezone.now()
        conv.save(update_fields=['status', 'approved_at'])
        # Increment offer counter
        Offer.objects.filter(pk=conv.offer_id).update(
            total_conversions=models.F('total_conversions') + 1,
            total_paid_usd=models.F('total_paid_usd') + conv.payout_usd,
        )
        # Award virtual currency via CMS
        if conv.user and conv.virtual_awarded > 0:
            try:
                from api.cms.services_new.CPALeadService import VirtualCurrencyService
                VirtualCurrencyService.award_coins(
                    user=conv.user,
                    coins=int(conv.virtual_awarded),
                    source_type='offerwall',
                    lead_id=conv.lead_id,
                )
            except Exception as e:
                logger.error(f"Failed to award coins for conversion {conv.id}: {e}")
        return Response({'status': 'approved', 'conversion_id': str(conv.id)})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        conv = self.get_object()
        if conv.status != OfferConversion.STATUS_PENDING:
            return Response({'error': 'Only pending conversions can be rejected'},
                            status=status.HTTP_400_BAD_REQUEST)
        conv.status = OfferConversion.STATUS_REJECTED
        conv.rejected_at = timezone.now()
        conv.save(update_fields=['status', 'rejected_at'])
        return Response({'status': 'rejected', 'conversion_id': str(conv.id)})


class OfferwallPostbackView(viewsets.ViewSet):
    """
    CPAlead postback handler for the offerwall app.
    POST /offerwall/postback/
    """
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get', 'post'])
    def postback(self, request):
        """
        Handle CPAlead postback.
        Required params: user_id, payout, lead_id, hash
        """
        data = request.data if request.method == 'POST' else request.query_params
        user_id  = data.get('user_id') or data.get('subid', '')
        payout   = float(data.get('payout', 0))
        lead_id  = data.get('lead_id', '') or data.get('transaction_id', '')
        offer_id = data.get('offer_id', '')
        hash_val = data.get('hash', '')

        if not all([user_id, lead_id]):
            return Response({'error': 'Missing required params'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Deduplicate
        if OfferConversion.objects.filter(lead_id=lead_id).exists():
            return Response({'status': 'duplicate'}, status=status.HTTP_200_OK)

        # Resolve offer
        offer = None
        if offer_id:
            offer = Offer.objects.filter(external_id=str(offer_id)).first()

        # Resolve user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(pk=int(user_id))
        except (User.DoesNotExist, ValueError):
            logger.warning(f"Offerwall postback: user {user_id} not found")
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        # Fraud check
        fraud_score = 0
        fraud_reasons = []
        try:
            from api.cms.sanctions import FraudScorer
            fraud_score, fraud_reasons = FraudScorer.score(
                user_id=user.pk,
                ip=request.META.get('REMOTE_ADDR', ''),
                subid=str(user_id),
                payout_usd=payout,
            )
        except Exception:
            pass

        virtual_coins = int(payout * 100)  # 1 USD = 100 coins

        conv = OfferConversion.objects.create(
            offer=offer,
            user=user,
            lead_id=lead_id,
            payout_usd=payout,
            virtual_awarded=virtual_coins,
            status=(OfferConversion.STATUS_PENDING
                    if fraud_score >= 50 else OfferConversion.STATUS_APPROVED),
            fraud_score=fraud_score,
            fraud_reasons=fraud_reasons,
            ip_address=request.META.get('REMOTE_ADDR'),
            postback_raw=dict(data),
        )

        if conv.status == OfferConversion.STATUS_APPROVED:
            try:
                from api.cms.services_new.CPALeadService import VirtualCurrencyService
                VirtualCurrencyService.award_coins(
                    user=user, coins=virtual_coins,
                    source_type='offerwall', lead_id=lead_id,
                )
            except Exception as e:
                logger.error(f"Offerwall coin award failed: {e}")

        return Response({'status': 'ok', 'conversion_id': str(conv.id)})


# ── Import fix for Q and F objects used in views ─────────────────────────────
from django.db import models
