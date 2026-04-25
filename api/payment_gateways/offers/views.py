# api/payment_gateways/offers/views.py
from rest_framework import filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q
from core.views import BaseViewSet
from .models import Offer, Campaign, PublisherOfferApplication, OfferCreative
from .serializers import (OfferListSerializer, OfferDetailSerializer, OfferCreateSerializer,
                           CampaignSerializer, PublisherApplicationSerializer, OfferCreativeSerializer)


class OfferViewSet(BaseViewSet):
    """
    Full offer management.
        - Publishers: browse + promote offers
        - Advertisers: create + manage own offers
        - Admin: full CRUD + approve/reject
    """
    queryset         = Offer.objects.all().select_related('advertiser').order_by('-created_at')
    permission_classes = [IsAuthenticated]
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status','offer_type','category','currency']
    search_fields    = ['name','description','app_name','app_id']
    ordering_fields  = ['publisher_payout','total_clicks','conversion_rate','epc','created_at']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return OfferCreateSerializer
        if self.action in ('list', 'browse'):
            return OfferListSerializer
        return OfferDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs   = super().get_queryset()
        if user.is_staff:
            return qs
        # Publisher: see active public offers + their approved private ones
        if self.action in ('list', 'browse', 'retrieve'):
            return qs.filter(
                Q(status='active', is_public=True)
                | Q(status='active', allowed_publishers=user)
                | Q(advertiser=user)  # Own offers
            ).distinct()
        # Advertiser: only own offers for CUD
        return qs.filter(advertiser=user)

    def perform_create(self, serializer):
        serializer.save(advertiser=self.request.user, created_by=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def browse(self, request):
        """Publisher: browse all available active offers."""
        qs = self.get_queryset().filter(status='active')

        # Filter by GEO
        country = request.GET.get('country')
        if country:
            qs = qs.filter(
                Q(target_countries=[]) | Q(target_countries__contains=[country])
            ).exclude(blocked_countries__contains=[country])

        # Filter by device
        device = request.GET.get('device')
        if device:
            qs = qs.filter(Q(target_devices=[]) | Q(target_devices__contains=[device]))

        # Filter by offer type
        offer_type = request.GET.get('type')
        if offer_type:
            qs = qs.filter(offer_type=offer_type)

        # Sort by highest payout by default
        qs = qs.order_by('-epc', '-publisher_payout')

        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(OfferListSerializer(page, many=True).data)
        return self.success_response(data=OfferListSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        """Publisher applies to run a private offer."""
        offer = self.get_object()
        if not offer.requires_approval:
            return self.error_response(message='This offer does not require approval.', status_code=400)
        existing = PublisherOfferApplication.objects.filter(offer=offer, publisher=request.user).first()
        if existing:
            return self.success_response(
                data=PublisherApplicationSerializer(existing).data,
                message=f'Application already exists: {existing.status}'
            )
        app = PublisherOfferApplication.objects.create(
            offer=offer, publisher=request.user,
            message=request.data.get('message', '')
        )
        return self.success_response(
            data=PublisherApplicationSerializer(app).data,
            message='Application submitted. Advertiser will review within 24 hours.'
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Admin: activate a pending offer."""
        offer        = self.get_object()
        offer.status = 'active'
        offer.save()
        return self.success_response(message=f'Offer "{offer.name}" approved and activated.')

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        """Admin: reject an offer."""
        offer        = self.get_object()
        offer.status = 'rejected'
        offer.save()
        return self.success_response(message='Offer rejected.')

    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Advertiser or admin: pause an active offer."""
        offer = self.get_object()
        if not request.user.is_staff and offer.advertiser != request.user:
            return self.error_response(message='Permission denied.', status_code=403)
        offer.status = 'paused'
        offer.save()
        return self.success_response(message='Offer paused.')

    @action(detail=True, methods=['get'])
    def tracking_link(self, request, pk=None):
        """
        Get publisher's unique tracking link for this offer.
        Link format: /tracking/click/{offer_id}/?sub1={sub1}
        """
        offer   = self.get_object()
        allowed, reason = offer.can_publisher_run(request.user)
        if not allowed:
            return self.error_response(message=reason, status_code=403)

        from django.conf import settings
        base = getattr(settings, 'SITE_URL', 'https://yourdomain.com')
        link = f'{base}/api/payment/tracking/click/{offer.id}/'

        return self.success_response(data={
            'offer_id':    offer.id,
            'offer_name':  offer.name,
            'tracking_link': link,
            'with_subs':   f'{link}?sub1=YOUR_ID&sub2=CAMPAIGN',
            'payout':      str(offer.publisher_payout),
            'currency':    offer.currency,
            'postback_guide': {
                'your_postback_url': f'{base}/api/payment/tracking/postback/?click_id={{click_id}}&payout={{payout}}&status=approved',
                'macros': ['{click_id}', '{payout}', '{cost}', '{status}', '{sub1}'],
            }
        })

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Publisher: stats for a specific offer."""
        from django.db.models import Sum, Count
        offer = self.get_object()
        from tracking.models import Click, Conversion
        data = {
            'clicks':      Click.objects.filter(offer=offer, publisher=request.user).count(),
            'conversions': Conversion.objects.filter(offer=offer, publisher=request.user,
                                                     status='approved').count(),
            'revenue':     float(Conversion.objects.filter(
                offer=offer, publisher=request.user, status='approved'
            ).aggregate(r=Sum('payout'))['r'] or 0),
        }
        return self.success_response(data=data)


class CampaignViewSet(BaseViewSet):
    """Advertiser campaign management."""
    queryset           = Campaign.objects.all().order_by('-created_at')
    serializer_class   = CampaignSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['status']

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(advertiser=self.request.user)

    def perform_create(self, serializer):
        serializer.save(advertiser=self.request.user)

    @action(detail=True, methods=['post'])
    def add_offer(self, request, pk=None):
        campaign  = self.get_object()
        offer_ids = request.data.get('offer_ids', [])
        offers    = Offer.objects.filter(id__in=offer_ids, advertiser=request.user)
        campaign.offers.add(*offers)
        return self.success_response(message=f'Added {offers.count()} offer(s) to campaign.')


class PublisherApplicationViewSet(BaseViewSet):
    """Manage publisher offer applications."""
    queryset           = PublisherOfferApplication.objects.all().order_by('-created_at')
    serializer_class   = PublisherApplicationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['status']

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(
            Q(publisher=user) | Q(offer__advertiser=user)
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        app = self.get_object()
        if not request.user.is_staff and app.offer.advertiser != request.user:
            return self.error_response(message='Permission denied.', status_code=403)
        app.status = 'approved'
        app.reviewed_by = request.user
        app.save()
        app.offer.allowed_publishers.add(app.publisher)
        return self.success_response(message='Application approved. Publisher can now run this offer.')

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        app            = self.get_object()
        app.status     = 'rejected'
        app.admin_notes = request.data.get('reason', '')
        app.reviewed_by = request.user
        app.save()
        return self.success_response(message='Application rejected.')
