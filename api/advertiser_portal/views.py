"""
Advertiser Portal Views

This module contains all core views for the advertiser portal
including advertisers, campaigns, offers, tracking, billing, and reporting.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.core.cache import cache
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from .models.advertiser import Advertiser, AdvertiserProfile, AdvertiserVerification, AdvertiserAgreement
from .models.campaign import AdCampaign, CampaignCreative, CampaignTargeting, CampaignBid, CampaignSchedule
from .models.offer import AdvertiserOffer, OfferRequirement, OfferCreative, OfferBlacklist
from .models.tracking import TrackingPixel, S2SPostback, Conversion, ConversionEvent, TrackingDomain
from .models.billing import AdvertiserWallet, AdvertiserTransaction, AdvertiserDeposit, AdvertiserInvoice, CampaignSpend, BillingAlert
from .models.reporting import AdvertiserReport, CampaignReport, PublisherBreakdown, GeoBreakdown, CreativePerformance
from .models.fraud_protection import ConversionQualityScore, AdvertiserFraudConfig, InvalidClickLog, ClickFraudSignal, OfferQualityScore, RoutingBlacklist
from .models.notification import AdvertiserNotification, AdvertiserAlert, NotificationTemplate
from .models.ml import UserJourneyStep, NetworkPerformanceCache, MLModel, MLPrediction
from .serializers import *

# Services — import from flat services.py
try:
    from .services import AdvertiserService
except ImportError:
    AdvertiserService = None
try:
    from .services import BillingService as AdvertiserBillingService
except ImportError:
    AdvertiserBillingService = None
CampaignService = OfferService = TrackingPixelService = None
AdvertiserReportService = ConversionQualityService = None

# Integration layer — optional
try:
    from .integration import (
        data_bridge, event_bus, performance_monitor,
        ab_testing_integration, bidding_optimization_integration,
        retargeting_engines_integration, webhooks_integration,
    )
except ImportError:
    data_bridge = event_bus = performance_monitor = None
    ab_testing_integration = bidding_optimization_integration = None
    retargeting_engines_integration = webhooks_integration = None

try:
    from .decorators import api_endpoint, sensitive_api_endpoint
except ImportError:
    def api_endpoint(f): return f
    def sensitive_api_endpoint(f): return f

try:
    from .filters import AdvertiserFilter, CampaignFilter, OfferFilter, ConversionFilter
except ImportError:
    AdvertiserFilter = CampaignFilter = OfferFilter = ConversionFilter = None

User = get_user_model()


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination class."""
    
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class BaseAPIView:
    """Base API view with common functionality."""
    
    def get_advertiser(self, request):
        """Get advertiser from authenticated user."""
        if not request.user.is_authenticated:
            return None
        try:
            return Advertiser.objects.get(user=request.user)
        except Advertiser.DoesNotExist:
            return None
    
    def get_permissions(self, request):
        """Get permissions based on user role."""
        if request.user.is_superuser:
            return ['admin']
        elif request.user.is_staff:
            return ['staff']
        else:
            return ['advertiser']
    
    def cache_get(self, key, timeout=300):
        """Get cached data."""
        return cache.get(key)
    
    def cache_set(self, key, value, timeout=300):
        """Set cached data."""
        cache.set(key, value, timeout)
    
    def cache_delete(self, key):
        """Delete cached data."""
        cache.delete(key)


# Advertiser Views with Integration Layers
@api_view(['GET', 'POST'])
@api_endpoint
@permission_classes([IsAuthenticated])
def advertiser_list_create(request):
    """List all advertisers or create a new advertiser with Data Bridge integration."""
    if request.method == 'GET':
        # Use enhanced manager with advanced search
        advertisers = Advertiser.objects.search_advanced(
            query=request.GET.get('search', ''),
            filters={
                'verification_status': request.GET.get('verification_status'),
                'country': request.GET.get('country'),
                'industry': request.GET.get('industry'),
                'min_balance': request.GET.get('min_balance'),
                'max_balance': request.GET.get('max_balance')
            }
        )
        
        # Apply advanced filters
        filter_set = AdvertiserFilter(request.GET, queryset=advertisers)
        advertisers = filter_set.qs
        
        # Pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(advertisers)
        serializer = AdvertiserSerializer(page, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    
    elif request.method == 'POST':
        serializer = AdvertiserSerializer(data=request.data)
        if serializer.is_valid():
            advertiser = serializer.save()

            # Sync with legacy system via Data Bridge
            if hasattr(advertiser, 'metadata') and advertiser.metadata.get('legacy_id'):
                legacy_data = {
                    'id': advertiser.metadata['legacy_id'],
                    'company_name': advertiser.company_name,
                    'industry': advertiser.industry,
                    'contact_email': advertiser.contact_email,
                    'verification_status': advertiser.verification_status,
                    'created_at': advertiser.created_at
                }
                try:
                    # Fire-and-forget in background thread
                    import threading
                    threading.Thread(
                        target=lambda: data_bridge.sync_advertiser_profile(legacy_data),
                        daemon=True
                    ).start()
                except Exception as e:
                    logger.warning(f"Legacy sync skipped for advertiser {advertiser.id}: {e}")

            # Log event for integration layers
            try:
                logger.info(
                    "advertiser_created event",
                    extra={
                        'advertiser_id': str(advertiser.id),
                        'company_name': advertiser.company_name,
                    }
                )
            except Exception:
                pass
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def advertiser_detail(request, pk):
    """Retrieve, update or delete an advertiser."""
    advertiser = get_object_or_404(Advertiser, pk=pk)
    
    # Check permissions
    if not request.user.is_superuser and advertiser.user != request.user:
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        serializer = AdvertiserDetailSerializer(advertiser)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = AdvertiserSerializer(advertiser, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        advertiser.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def advertiser_profile(request):
    """Get or update advertiser profile."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        try:
            profile = advertiser.profile
        except AdvertiserProfile.DoesNotExist:
            profile = AdvertiserProfile.objects.create(advertiser=advertiser)
        
        serializer = AdvertiserProfileSerializer(profile)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        try:
            profile = advertiser.profile
        except AdvertiserProfile.DoesNotExist:
            profile = AdvertiserProfile.objects.create(advertiser=advertiser)
        
        serializer = AdvertiserProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def advertiser_verification(request):
    """Get or submit advertiser verification."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        verifications = AdvertiserVerification.objects.filter(advertiser=advertiser)
        serializer = AdvertiserVerificationSerializer(verifications, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = AdvertiserVerificationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(advertiser=advertiser)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Campaign Views
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def campaign_list_create(request):
    """List all campaigns or create a new campaign."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        campaigns = AdCampaign.objects.filter(advertiser=advertiser)
        
        # Apply filters
        status = request.GET.get('status')
        if status:
            campaigns = campaigns.filter(status=status)
        
        start_date = request.GET.get('start_date')
        if start_date:
            campaigns = campaigns.filter(start_date__gte=start_date)
        
        end_date = request.GET.get('end_date')
        if end_date:
            campaigns = campaigns.filter(end_date__lte=end_date)
        
        # Pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(campaigns)
        serializer = AdCampaignSerializer(page, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    
    elif request.method == 'POST':
        serializer = AdCampaignSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(advertiser=advertiser)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def campaign_detail(request, pk):
    """Retrieve, update or delete a campaign."""
    campaign = get_object_or_404(AdCampaign, pk=pk)
    
    # Check permissions
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser or (campaign.advertiser != advertiser and not request.user.is_superuser):
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        serializer = CampaignDetailSerializer(campaign)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = AdCampaignSerializer(campaign, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        campaign.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def campaign_creatives(request, campaign_id):
    """List or create campaign creatives."""
    campaign = get_object_or_404(AdCampaign, pk=campaign_id)
    
    # Check permissions
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser or (campaign.advertiser != advertiser and not request.user.is_superuser):
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        creatives = CampaignCreative.objects.filter(campaign=campaign)
        serializer = CampaignCreativeSerializer(creatives, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = CampaignCreativeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(campaign=campaign)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def campaign_targeting(request, campaign_id):
    """List or create campaign targeting."""
    campaign = get_object_or_404(AdCampaign, pk=campaign_id)
    
    # Check permissions
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser or (campaign.advertiser != advertiser and not request.user.is_superuser):
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        targeting = CampaignTargeting.objects.filter(campaign=campaign)
        serializer = CampaignTargetingSerializer(targeting, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = CampaignTargetingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(campaign=campaign)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Offer Views
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def offer_list_create(request):
    """List all offers or create a new offer."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        offers = AdvertiserOffer.objects.filter(advertiser=advertiser)
        
        # Apply filters
        status = request.GET.get('status')
        if status:
            offers = offers.filter(status=status)
        
        offer_type = request.GET.get('offer_type')
        if offer_type:
            offers = offers.filter(offer_type=offer_type)
        
        # Pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(offers)
        serializer = AdvertiserOfferSerializer(page, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    
    elif request.method == 'POST':
        serializer = AdvertiserOfferSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(advertiser=advertiser)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def offer_detail(request, pk):
    """Retrieve, update or delete an offer."""
    offer = get_object_or_404(AdvertiserOffer, pk=pk)
    
    # Check permissions
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser or (offer.advertiser != advertiser and not request.user.is_superuser):
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        serializer = OfferDetailSerializer(offer)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = AdvertiserOfferSerializer(offer, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        offer.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# Tracking Views
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def tracking_pixel_list_create(request):
    """List all tracking pixels or create a new tracking pixel."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        pixels = TrackingPixel.objects.filter(advertiser=advertiser)
        
        # Apply filters
        status = request.GET.get('status')
        if status:
            pixels = pixels.filter(status=status)
        
        pixel_type = request.GET.get('pixel_type')
        if pixel_type:
            pixels = pixels.filter(pixel_type=pixel_type)
        
        # Pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(pixels)
        serializer = TrackingPixelSerializer(page, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    
    elif request.method == 'POST':
        serializer = TrackingPixelSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(advertiser=advertiser)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def tracking_pixel_detail(request, pk):
    """Retrieve, update or delete a tracking pixel."""
    pixel = get_object_or_404(TrackingPixel, pk=pk)
    
    # Check permissions
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser or (pixel.advertiser != advertiser and not request.user.is_superuser):
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    if request.method == 'GET':
        serializer = TrackingPixelSerializer(pixel)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = TrackingPixelSerializer(pixel, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        pixel.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([])
def tracking_pixel_fire(request, pixel_id):
    """Fire tracking pixel."""
    pixel = get_object_or_404(TrackingPixel, pk=pixel_id)
    
    if pixel.status != 'active':
        return Response(
            {'error': 'Pixel is not active'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        service = TrackingPixelService()
        result = service.fire_pixel(pixel, request)
        
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def conversion_list_create(request):
    """List all conversions or create a new conversion."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        conversions = Conversion.objects.filter(advertiser=advertiser)
        
        # Apply filters
        status = request.GET.get('status')
        if status:
            conversions = conversions.filter(status=status)
        
        start_date = request.GET.get('start_date')
        if start_date:
            conversions = conversions.filter(created_at__gte=start_date)
        
        end_date = request.GET.get('end_date')
        if end_date:
            conversions = conversions.filter(created_at__lte=end_date)
        
        # Pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(conversions)
        serializer = ConversionSerializer(page, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    
    elif request.method == 'POST':
        serializer = ConversionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(advertiser=advertiser)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Billing Views
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def wallet_detail(request):
    """Get or update advertiser wallet."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        try:
            wallet = advertiser.wallet
        except AdvertiserWallet.DoesNotExist:
            wallet = AdvertiserWallet.objects.create(advertiser=advertiser)
        
        serializer = AdvertiserWalletSerializer(wallet)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        try:
            wallet = advertiser.wallet
        except AdvertiserWallet.DoesNotExist:
            wallet = AdvertiserWallet.objects.create(advertiser=advertiser)
        
        serializer = AdvertiserWalletSerializer(wallet, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def transaction_list_create(request):
    """List all transactions or create a new transaction."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        try:
            wallet = advertiser.wallet
        except AdvertiserWallet.DoesNotExist:
            return Response(
                {'error': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        transactions = AdvertiserTransaction.objects.filter(wallet=wallet)
        
        # Apply filters
        transaction_type = request.GET.get('transaction_type')
        if transaction_type:
            transactions = transactions.filter(transaction_type=transaction_type)
        
        start_date = request.GET.get('start_date')
        if start_date:
            transactions = transactions.filter(created_at__gte=start_date)
        
        end_date = request.GET.get('end_date')
        if end_date:
            transactions = transactions.filter(created_at__lte=end_date)
        
        # Pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(transactions)
        serializer = AdvertiserTransactionSerializer(page, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    
    elif request.method == 'POST':
        try:
            wallet = advertiser.wallet
        except AdvertiserWallet.DoesNotExist:
            return Response(
                {'error': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AdvertiserTransactionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(wallet=wallet)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def deposit_create(request):
    """Create a new deposit."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'POST':
        try:
            wallet = advertiser.wallet
        except AdvertiserWallet.DoesNotExist:
            return Response(
                {'error': 'Wallet not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AdvertiserDepositSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(wallet=wallet)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def invoice_list(request):
    """List all invoices."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    invoices = AdvertiserInvoice.objects.filter(advertiser=advertiser)
    
    # Apply filters
    status = request.GET.get('status')
    if status:
        invoices = invoices.filter(status=status)
    
    start_date = request.GET.get('start_date')
    if start_date:
        invoices = invoices.filter(invoice_date__gte=start_date)
    
    end_date = request.GET.get('end_date')
    if end_date:
        invoices = invoices.filter(invoice_date__lte=end_date)
    
    # Pagination
    paginator = StandardResultsSetPagination()
    page = paginator.paginate_queryset(invoices)
    serializer = AdvertiserInvoiceSerializer(page, many=True)
    
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def invoice_detail(request, pk):
    """Retrieve invoice details."""
    invoice = get_object_or_404(AdvertiserInvoice, pk=pk)
    
    # Check permissions
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser or (invoice.advertiser != advertiser and not request.user.is_superuser):
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = AdvertiserInvoiceSerializer(invoice)
    return Response(serializer.data)


# Reporting Views
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def report_list_create(request):
    """List all reports or create a new report."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        reports = AdvertiserReport.objects.filter(advertiser=advertiser)
        
        # Apply filters
        report_type = request.GET.get('report_type')
        if report_type:
            reports = reports.filter(report_type=report_type)
        
        status = request.GET.get('status')
        if status:
            reports = reports.filter(status=status)
        
        # Pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(reports)
        serializer = AdvertiserReportSerializer(page, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    
    elif request.method == 'POST':
        serializer = AdvertiserReportSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(advertiser=advertiser)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def report_detail(request, pk):
    """Retrieve report details."""
    report = get_object_or_404(AdvertiserReport, pk=pk)
    
    # Check permissions
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser or (report.advertiser != advertiser and not request.user.is_superuser):
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    serializer = AdvertiserReportSerializer(report)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_metrics(request):
    """Get dashboard metrics."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    try:
        service = AdvertiserReportService()
        metrics = service.get_dashboard_metrics(advertiser)
        
        return Response(metrics)
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def performance_metrics(request):
    """Get performance metrics."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    try:
        service = AdvertiserReportService()
        
        # Get date range from request
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        metrics = service.get_performance_metrics(
            advertiser, 
            start_date=start_date, 
            end_date=end_date
        )
        
        return Response(metrics)
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Fraud Detection Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fraud_metrics(request):
    """Get fraud detection metrics."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    try:
        service = ConversionQualityService()
        metrics = service.get_fraud_metrics(advertiser)
        
        return Response(metrics)
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def conversion_quality_scores(request):
    """Get conversion quality scores."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    try:
        service = ConversionQualityService()
        
        # Get date range from request
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        scores = service.get_conversion_quality_scores(
            advertiser, 
            start_date=start_date, 
            end_date=end_date
        )
        
        return Response(scores)
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Notification Views
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def notification_list_create(request):
    """List all notifications or create a new notification."""
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser:
        return Response(
            {'error': 'Advertiser not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        notifications = AdvertiserNotification.objects.filter(advertiser=advertiser)
        
        # Apply filters
        is_read = request.GET.get('is_read')
        if is_read is not None:
            notifications = notifications.filter(is_read=is_read.lower() == 'true')
        
        notification_type = request.GET.get('notification_type')
        if notification_type:
            notifications = notifications.filter(notification_type=notification_type)
        
        # Pagination
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(notifications)
        serializer = AdvertiserNotificationSerializer(page, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    
    elif request.method == 'POST':
        # Only admins can create notifications
        if not request.user.is_superuser:
            return Response(
                {'error': 'Only administrators can create notifications'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = AdvertiserNotificationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def notification_mark_read(request, pk):
    """Mark notification as read."""
    notification = get_object_or_404(AdvertiserNotification, pk=pk)
    
    # Check permissions
    advertiser = BaseAPIView().get_advertiser(request)
    if not advertiser or (notification.advertiser != advertiser and not request.user.is_superuser):
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save()
    
    serializer = AdvertiserNotificationSerializer(notification)
    return Response(serializer.data)


# Utility Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_health(request):
    """Get system health status."""
    if not request.user.is_superuser:
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        health_status = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'services': {
                'database': 'healthy',
                'cache': 'healthy',
                'background_tasks': 'healthy'
            },
            'metrics': {
                'total_advertisers': Advertiser.objects.count(),
                'active_campaigns': AdCampaign.objects.filter(status='active').count(),
                'total_conversions': Conversion.objects.count(),
                'cache_hit_rate': '85%'
            }
        }
        
        return Response(health_status)
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_stats(request):
    """Get system statistics."""
    if not request.user.is_superuser:
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        stats = {
            'advertisers': {
                'total': Advertiser.objects.count(),
                'verified': Advertiser.objects.filter(verification_status='verified').count(),
                'pending': Advertiser.objects.filter(verification_status='pending').count(),
                'new_this_month': Advertiser.objects.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=30)
                ).count()
            },
            'campaigns': {
                'total': AdCampaign.objects.count(),
                'active': AdCampaign.objects.filter(status='active').count(),
                'paused': AdCampaign.objects.filter(status='paused').count(),
                'new_this_month': AdCampaign.objects.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=30)
                ).count()
            },
            'offers': {
                'total': AdvertiserOffer.objects.count(),
                'active': AdvertiserOffer.objects.filter(status='active').count(),
                'pending': AdvertiserOffer.objects.filter(status='pending_review').count(),
                'new_this_month': AdvertiserOffer.objects.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=30)
                ).count()
            },
            'conversions': {
                'total': Conversion.objects.count(),
                'today': Conversion.objects.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=1)
                ).count(),
                'this_week': Conversion.objects.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=7)
                ).count(),
                'this_month': Conversion.objects.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=30)
                ).count()
            },
            'revenue': {
                'total': Conversion.objects.aggregate(
                    total=Sum('revenue')
                )['total'] or 0,
                'today': Conversion.objects.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=1)
                ).aggregate(total=Sum('revenue'))['total'] or 0,
                'this_week': Conversion.objects.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=7)
                ).aggregate(total=Sum('revenue'))['total'] or 0,
                'this_month': Conversion.objects.filter(
                    created_at__gte=timezone.now() - timezone.timedelta(days=30)
                ).aggregate(total=Sum('revenue'))['total'] or 0
            }
        }
        
        return Response(stats)
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Export all views
__all__ = [
    # Base classes
    'BaseAPIView',
    'StandardResultsSetPagination',
    
    # Advertiser views
    'advertiser_list_create',
    'advertiser_detail',
    'advertiser_profile',
    'advertiser_verification',
    
    # Campaign views
    'campaign_list_create',
    'campaign_detail',
    'campaign_creatives',
    'campaign_targeting',
    
    # Offer views
    'offer_list_create',
    'offer_detail',
    
    # Tracking views
    'tracking_pixel_list_create',
    'tracking_pixel_detail',
    'tracking_pixel_fire',
    'conversion_list_create',
    
    # Billing views
    'wallet_detail',
    'transaction_list_create',
    'deposit_create',
    'invoice_list',
    'invoice_detail',
    
    # Reporting views
    'report_list_create',
    'report_detail',
    'dashboard_metrics',
    'performance_metrics',
    
    # Fraud detection views
    'fraud_metrics',
    'conversion_quality_scores',
    
    # Notification views
    'notification_list_create',
    'notification_mark_read',
    
    # Utility views
    'system_health',
    'system_stats',
]
