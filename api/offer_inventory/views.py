# api/offer_inventory/views.py
import logging
from decimal import Decimal
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.utils import timezone
from django.core.cache import cache

from .models import (
    Offer, OfferNetwork, OfferCategory, Click, Conversion,
    WithdrawalRequest, PaymentMethod, WalletTransaction,
    UserProfile, UserKYC, Notification, BlacklistedIP,
    FraudAttempt, UserRiskProfile, FraudRule,
    DailyStat, NetworkStat, Campaign, MasterSwitch,
    SystemSetting, FeedbackTicket, SmartLink,
    SubID, PostbackLog, ABTestGroup, AuditLog,
    Achievement, UserReferral,
)
from .serializers import (
    OfferListSerializer, OfferDetailSerializer, OfferWriteSerializer,
    OfferNetworkSerializer, OfferCategorySerializer,
    ClickSerializer, ConversionSerializer, PostbackInputSerializer,
    WithdrawalCreateSerializer, WithdrawalRequestSerializer,
    PaymentMethodSerializer, PaymentMethodCreateSerializer,
    WalletTransactionSerializer, WalletAuditSerializer,
    UserProfileSerializer, UserKYCSerializer,
    UserReferralSerializer, AchievementSerializer,
    NotificationSerializer, UserRiskProfileSerializer,
    BlacklistedIPSerializer, FraudAttemptSerializer,
    DailyStatSerializer, NetworkStatSerializer,
    MasterSwitchSerializer, SystemSettingSerializer,
    CampaignSerializer, SmartLinkSerializer, ABTestGroupSerializer,
    FeedbackTicketSerializer,
)
from .services import (
    OfferService, ClickService, ConversionService,
    FraudService, WithdrawalService, PostbackService,
)
from .exceptions import (
    OfferNotFoundException, FraudDetectedException,
    InvalidPostbackException,
)
from .validators import validate_postback_signature
from .permissions import (
    IsOfferAdmin, IsTenantUser, IsVerifiedUser,
)
from .filters import (
    OfferFilter, ConversionFilter, WithdrawalFilter,
    FraudAttemptFilter, ClickFilter,
)
from .utils import get_client_meta

logger = logging.getLogger(__name__)


class StandardPagination(PageNumberPagination):
    page_size            = 20
    page_size_query_param= 'page_size'
    max_page_size        = 100


def ok(data=None, message='', status_code=status.HTTP_200_OK):
    return Response({'success': True, 'message': message, 'data': data}, status=status_code)


def err(message='Error', errors=None, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({'success': False, 'message': message, 'errors': errors}, status=status_code)


# ══════════════════════════════════════════════════════
# OFFER VIEWS
# ══════════════════════════════════════════════════════

class OfferViewSet(viewsets.ModelViewSet):
    """
    GET    /api/offer-inventory/offers/          → list
    GET    /api/offer-inventory/offers/{id}/     → detail
    POST   /api/offer-inventory/offers/          → create (admin)
    PATCH  /api/offer-inventory/offers/{id}/     → update (admin)
    DELETE /api/offer-inventory/offers/{id}/     → delete (admin)
    POST   /api/offer-inventory/offers/{id}/click/ → record click
    """
    queryset         = Offer.objects.all()
    pagination_class = StandardPagination
    filterset_class  = OfferFilter

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return OfferWriteSerializer
        if self.action == 'retrieve':
            return OfferDetailSerializer
        return OfferListSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [permissions.IsAuthenticated(), IsOfferAdmin()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        tenant = getattr(self.request, 'tenant', None)
        qs = Offer.objects.select_related('network', 'category').prefetch_related('tags', 'caps')
        if not self.request.user.is_staff:
            qs = qs.filter(status='active')
        if tenant:
            qs = qs.filter(tenant=tenant)
        return qs

    def retrieve(self, request, *args, **kwargs):
        offer = self.get_object()
        serializer = self.get_serializer(offer)
        return ok(serializer.data)

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        serializer = OfferListSerializer(page, many=True, context={'request': request})
        return self.get_paginated_response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = OfferWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        offer = serializer.save(tenant=getattr(request, 'tenant', None))
        from .models import OfferLog
        OfferLog.objects.create(offer=offer, changed_by=request.user,
                                new_status=offer.status, note='Created')
        return ok(OfferDetailSerializer(offer).data, 'অফার তৈরি হয়েছে।', status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        offer = self.get_object()
        old_status = offer.status
        serializer = OfferWriteSerializer(offer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        offer = serializer.save()
        if old_status != offer.status:
            from .models import OfferLog
            OfferLog.objects.create(offer=offer, changed_by=request.user,
                                    old_status=old_status, new_status=offer.status)
        return ok(OfferDetailSerializer(offer).data, 'অফার আপডেট হয়েছে।')

    @action(detail=True, methods=['post'], url_path='click')
    def record_click(self, request, pk=None):
        """অফারে click রেকর্ড করো।"""
        offer = self.get_object()
        meta  = get_client_meta(request)
        try:
            click = ClickService.record_click(str(offer.id), request.user, meta)
            return ok({
                'click_token': click.click_token,
                'offer_url'  : offer.offer_url,
            }, 'Click রেকর্ড হয়েছে।')
        except Exception as e:
            logger.warning(f'Click error: {e}')
            return err(str(e))

    @action(detail=True, methods=['get'], url_path='logs')
    def logs(self, request, pk=None):
        """Offer status change logs।"""
        offer = self.get_object()
        from .serializers import OfferLogSerializer
        data = OfferLogSerializer(offer.logs.all()[:20], many=True).data
        return ok(data)

    @action(detail=False, methods=['get'], url_path='featured')
    def featured(self, request):
        """Featured অফার list।"""
        qs = self.get_queryset().filter(is_featured=True)[:10]
        data = OfferListSerializer(qs, many=True, context={'request': request}).data
        return ok(data)


class OfferNetworkViewSet(viewsets.ModelViewSet):
    queryset         = OfferNetwork.objects.all()
    serializer_class = OfferNetworkSerializer
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    @action(detail=True, methods=['post'], url_path='ping')
    def ping(self, request, pk=None):
        """Network health ping।"""
        import requests as req
        network = self.get_object()
        try:
            start = timezone.now()
            resp  = req.get(network.base_url, timeout=5)
            ms    = (timezone.now() - start).total_seconds() * 1000
            from .models import NetworkPinger
            NetworkPinger.objects.create(
                network=network, response_code=resp.status_code,
                response_time=ms, is_up=resp.ok,
            )
            return ok({'status': resp.status_code, 'ms': round(ms, 2)})
        except Exception as e:
            return err(str(e))


class OfferCategoryViewSet(viewsets.ModelViewSet):
    queryset           = OfferCategory.objects.filter(is_active=True)
    serializer_class   = OfferCategorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [permissions.IsAuthenticated(), IsOfferAdmin()]
        return [permissions.IsAuthenticated()]


# ══════════════════════════════════════════════════════
# CLICK & CONVERSION VIEWS
# ══════════════════════════════════════════════════════

class ConversionViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin conversion management।"""
    serializer_class   = ConversionSerializer
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    pagination_class   = StandardPagination
    filterset_class    = ConversionFilter

    def get_queryset(self):
        return Conversion.objects.select_related(
            'offer', 'user', 'click', 'status'
        ).order_by('-created_at')

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        conversion = self.get_object()
        try:
            ConversionService.approve_conversion(str(conversion.id))
            return ok(message='Conversion অনুমোদিত হয়েছে।')
        except Exception as e:
            return err(str(e))

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        conversion = self.get_object()
        reason = request.data.get('reason', 'Manual rejection')
        from .repository import ConversionRepository
        ConversionRepository.reject_conversion(str(conversion.id), reason)
        return ok(message='Conversion বাতিল করা হয়েছে।')


class PostbackView(APIView):
    """
    Network S2S postback endpoint।
    POST /api/offer-inventory/postback/
    GET  /api/offer-inventory/postback/  (some networks use GET)
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return self._handle(request)

    def post(self, request):
        return self._handle(request)

    def _handle(self, request):
        data = {**request.query_params.dict(), **request.data}
        serializer = PostbackInputSerializer(data=data)
        if not serializer.is_valid():
            return Response({'status': 'error', 'errors': serializer.errors}, status=400)

        validated = serializer.validated_data
        try:
            # Signature verify (if secret set)
            raw = request.META.get('QUERY_STRING', '')
            sig = validated.get('signature', '')
            if sig:
                from .models import OfferNetwork
                # Try to find network from click
                click = ClickService.validate_click_token(validated['click_id'])
                secret = click.offer.network.api_secret if click.offer.network else ''
                if secret and not validate_postback_signature(raw, sig, secret):
                    raise InvalidPostbackException()

            conversion = ConversionService.process_conversion(
                click_token   = validated['click_id'],
                transaction_id= validated['transaction_id'],
                payout        = validated['payout'],
                raw_data      = data,
            )
            return Response({'status': 'ok', 'conversion_id': str(conversion.id)})
        except Exception as e:
            logger.warning(f'Postback error: {e} | data={data}')
            return Response({'status': 'error', 'message': str(e)}, status=400)


class MyConversionsView(APIView):
    """User নিজের conversions।"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        page      = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        from .repository import ConversionRepository
        conversions = ConversionRepository.get_user_conversions(request.user.id, page, page_size)
        data = ConversionSerializer(conversions, many=True).data
        return ok(data)


# ══════════════════════════════════════════════════════
# WALLET / WITHDRAWAL VIEWS
# ══════════════════════════════════════════════════════

class PaymentMethodViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return PaymentMethodCreateSerializer
        return PaymentMethodSerializer

    def get_queryset(self):
        return PaymentMethod.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = PaymentMethodCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        method = serializer.save(user=request.user)
        return ok(PaymentMethodSerializer(method).data,
                  'Payment method যোগ করা হয়েছে।', status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='set-primary')
    def set_primary(self, request, pk=None):
        PaymentMethod.objects.filter(user=request.user).update(is_primary=False)
        self.get_object().save()
        PaymentMethod.objects.filter(id=pk, user=request.user).update(is_primary=True)
        return ok(message='Primary method সেট হয়েছে।')


class WithdrawalViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class   = StandardPagination

    def get_queryset(self):
        if self.request.user.is_staff:
            return WithdrawalRequest.objects.select_related('user', 'payment_method').all()
        return WithdrawalRequest.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return WithdrawalCreateSerializer
        return WithdrawalRequestSerializer

    def create(self, request, *args, **kwargs):
        serializer = WithdrawalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant = getattr(request, 'tenant', None)
        try:
            wr = WithdrawalService.create_withdrawal(
                user=request.user,
                amount=serializer.validated_data['amount'],
                payment_method_id=str(serializer.validated_data['payment_method_id']),
                tenant=tenant,
            )
            return ok(WithdrawalRequestSerializer(wr).data,
                      'উইথড্রয়াল অনুরোধ পাঠানো হয়েছে।', status.HTTP_201_CREATED)
        except Exception as e:
            return err(str(e))

    @action(detail=True, methods=['post'], url_path='approve',
            permission_classes=[permissions.IsAuthenticated, IsOfferAdmin])
    def approve(self, request, pk=None):
        try:
            wr = WithdrawalService.approve_withdrawal(str(pk), request.user)
            return ok(WithdrawalRequestSerializer(wr).data, 'উইথড্রয়াল অনুমোদিত।')
        except Exception as e:
            return err(str(e))

    @action(detail=True, methods=['post'], url_path='reject',
            permission_classes=[permissions.IsAuthenticated, IsOfferAdmin])
    def reject(self, request, pk=None):
        reason = request.data.get('reason', '')
        try:
            wr = WithdrawalService.reject_withdrawal(str(pk), request.user, reason)
            return ok(WithdrawalRequestSerializer(wr).data, 'উইথড্রয়াল বাতিল।')
        except Exception as e:
            return err(str(e))


class TransactionHistoryView(APIView):
    """User wallet transaction history।"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('page_size', 20))
        start = (page - 1) * size
        qs   = WalletTransaction.objects.filter(user=request.user)[start:start + size]
        return ok(WalletTransactionSerializer(qs, many=True).data)


# ══════════════════════════════════════════════════════
# NOTIFICATION VIEWS
# ══════════════════════════════════════════════════════

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class   = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        from .repository import NotificationRepository
        NotificationRepository.mark_all_read(request.user.id)
        cache.delete(f'notif_unread:{request.user.id}')
        return ok(message='সব notification পড়া হয়েছে।')

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        from .repository import NotificationRepository
        count = NotificationRepository.unread_count(request.user.id)
        return ok({'count': count})


# ══════════════════════════════════════════════════════
# USER PROFILE VIEWS
# ══════════════════════════════════════════════════════

class MyProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return ok(UserProfileSerializer(profile).data)


class MyKYCView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            kyc = UserKYC.objects.get(user=request.user)
            return ok(UserKYCSerializer(kyc).data)
        except UserKYC.DoesNotExist:
            return ok(None, 'KYC submit করা হয়নি।')

    def post(self, request):
        if UserKYC.objects.filter(user=request.user, status='approved').exists():
            return err('আপনার KYC ইতিমধ্যে অনুমোদিত হয়েছে।')
        kyc, _ = UserKYC.objects.get_or_create(user=request.user)
        serializer = UserKYCSerializer(kyc, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        kyc = serializer.save(status='pending')
        return ok(UserKYCSerializer(kyc).data, 'KYC submit হয়েছে। পর্যালোচনার জন্য অপেক্ষা করুন।')


class AchievementsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = Achievement.objects.filter(is_active=True, is_hidden=False)
        data = AchievementSerializer(qs, many=True, context={'request': request}).data
        return ok(data)


class ReferralsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        referrals = UserReferral.objects.filter(referrer=request.user).select_related('referred')
        return ok(UserReferralSerializer(referrals, many=True).data)


# ══════════════════════════════════════════════════════
# FRAUD / SECURITY VIEWS (Admin)
# ══════════════════════════════════════════════════════

class BlacklistedIPViewSet(viewsets.ModelViewSet):
    queryset           = BlacklistedIP.objects.all()
    serializer_class   = BlacklistedIPSerializer
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    pagination_class   = StandardPagination

    @action(detail=False, methods=['post'], url_path='bulk-block')
    def bulk_block(self, request):
        ips    = request.data.get('ips', [])
        reason = request.data.get('reason', 'Bulk block')
        count  = 0
        for ip in ips:
            try:
                BlacklistedIP.objects.get_or_create(
                    ip_address=ip, defaults={'reason': reason, 'source': 'manual'}
                )
                count += 1
            except Exception:
                pass
        return ok({'blocked': count}, f'{count}টি IP block হয়েছে।')


class FraudAttemptViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = FraudAttempt.objects.select_related('rule', 'user').all()
    serializer_class   = FraudAttemptSerializer
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    pagination_class   = StandardPagination
    filterset_class    = FraudAttemptFilter

    @action(detail=True, methods=['post'], url_path='resolve')
    def resolve(self, request, pk=None):
        attempt = self.get_object()
        attempt.is_resolved = True
        attempt.resolved_by = request.user
        attempt.resolved_at = timezone.now()
        attempt.save()
        return ok(message='Fraud attempt resolved।')


class UserRiskProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = UserRiskProfile.objects.select_related('user').all()
    serializer_class   = UserRiskProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    pagination_class   = StandardPagination

    @action(detail=True, methods=['post'], url_path='suspend')
    def suspend(self, request, pk=None):
        profile = self.get_object()
        reason  = request.data.get('reason', '')
        profile.is_suspended      = True
        profile.suspension_reason = reason
        profile.save()
        return ok(message=f'User {profile.user.username} সাসপেন্ড হয়েছে।')

    @action(detail=True, methods=['post'], url_path='unsuspend')
    def unsuspend(self, request, pk=None):
        profile = self.get_object()
        profile.is_suspended = False
        profile.suspension_reason = ''
        profile.save()
        return ok(message='User সাসপেন্ড প্রত্যাহার হয়েছে।')

    @action(detail=True, methods=['post'], url_path='reset-score')
    def reset_score(self, request, pk=None):
        profile = self.get_object()
        profile.risk_score  = 0.0
        profile.risk_level  = 'low'
        profile.total_flags = 0
        profile.save()
        return ok(message='Risk score reset হয়েছে।')


# ══════════════════════════════════════════════════════
# ANALYTICS VIEWS
# ══════════════════════════════════════════════════════

class DashboardStatsView(APIView):
    """Admin dashboard-এর summary stats।"""
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        cache_key = f'dashboard_stats:{getattr(request, "tenant", "global")}'
        cached = cache.get(cache_key)
        if cached:
            return ok(cached)

        today = timezone.now().date()
        from .repository import AnalyticsRepository
        days = int(request.query_params.get('days', 7))
        stats = AnalyticsRepository.get_daily_stats(days=days)
        top   = AnalyticsRepository.get_top_offers(days=days)
        nets  = AnalyticsRepository.get_network_performance(days=days)

        data = {
            'daily_stats': DailyStatSerializer(stats, many=True).data,
            'top_offers': top,
            'network_performance': nets,
        }
        cache.set(cache_key, data, 300)
        return ok(data)


class NetworkStatViewSet(viewsets.ReadOnlyModelViewSet):
    queryset           = NetworkStat.objects.select_related('network').all()
    serializer_class   = NetworkStatSerializer
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]


# ══════════════════════════════════════════════════════
# SYSTEM / ADMIN VIEWS
# ══════════════════════════════════════════════════════

class MasterSwitchViewSet(viewsets.ModelViewSet):
    queryset           = MasterSwitch.objects.all()
    serializer_class   = MasterSwitchSerializer
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def perform_update(self, serializer):
        serializer.save(toggled_by=self.request.user)
        from .repository import FeatureFlagRepository
        cache.delete(f'feature:{serializer.instance.tenant_id}:{serializer.instance.feature}')

    @action(detail=False, methods=['post'], url_path='toggle')
    def toggle(self, request):
        feature = request.data.get('feature')
        enabled = request.data.get('enabled', True)
        tenant  = getattr(request, 'tenant', None)
        from .repository import FeatureFlagRepository
        obj = FeatureFlagRepository.set_feature(feature, enabled, tenant, request.user)
        return ok(MasterSwitchSerializer(obj).data)


class SystemSettingViewSet(viewsets.ModelViewSet):
    queryset           = SystemSetting.objects.all()
    serializer_class   = SystemSettingSerializer
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]


class CampaignViewSet(viewsets.ModelViewSet):
    queryset           = Campaign.objects.select_related('advertiser', 'network').all()
    serializer_class   = CampaignSerializer
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    pagination_class   = StandardPagination

    @action(detail=True, methods=['post'], url_path='pause')
    def pause(self, request, pk=None):
        Campaign.objects.filter(id=pk).update(status='paused')
        return ok(message='Campaign paused।')

    @action(detail=True, methods=['post'], url_path='resume')
    def resume(self, request, pk=None):
        Campaign.objects.filter(id=pk).update(status='live')
        return ok(message='Campaign live।')


class SmartLinkViewSet(viewsets.ModelViewSet):
    queryset           = SmartLink.objects.prefetch_related('offers').all()
    serializer_class   = SmartLinkSerializer
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]


class SmartLinkRedirectView(APIView):
    """SmartLink-এ hit করলে best offer-এ redirect।"""
    permission_classes = [permissions.AllowAny]

    def get(self, request, slug):
        try:
            link = SmartLink.objects.prefetch_related('offers').get(slug=slug, is_active=True)
        except SmartLink.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        from django.db.models import F
        SmartLink.objects.filter(id=link.id).update(click_count=F('click_count') + 1)

        offers = link.offers.filter(status='active')
        if not offers.exists():
            return Response({'error': 'No offers available'}, status=404)

        if link.algorithm == 'highest_payout':
            best = offers.order_by('-payout_amount').first()
        elif link.algorithm == 'best_cvr':
            best = offers.order_by('-conversion_rate').first()
        else:
            import random
            best = random.choice(list(offers))

        from django.shortcuts import redirect
        return redirect(best.offer_url)


class FeedbackTicketViewSet(viewsets.ModelViewSet):
    serializer_class = FeedbackTicketSerializer
    pagination_class = StandardPagination

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'update', 'partial_update'):
            if self.request.user.is_staff:
                return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if self.request.user.is_staff:
            return FeedbackTicket.objects.select_related('user', 'assigned_to').all()
        return FeedbackTicket.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        import uuid
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket_no = f'TKT-{str(uuid.uuid4())[:6].upper()}'
        ticket = serializer.save(user=request.user, ticket_no=ticket_no)
        return ok(self.get_serializer(ticket).data, 'Ticket submit হয়েছে।', status.HTTP_201_CREATED)


class ABTestViewSet(viewsets.ModelViewSet):
    queryset           = ABTestGroup.objects.all()
    serializer_class   = ABTestGroupSerializer
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        ABTestGroup.objects.filter(id=pk).update(status='running', started_at=timezone.now())
        return ok(message='A/B Test শুরু হয়েছে।')

    @action(detail=True, methods=['post'], url_path='end')
    def end(self, request, pk=None):
        winner = request.data.get('winner', '')
        ABTestGroup.objects.filter(id=pk).update(
            status='completed', ended_at=timezone.now(), winner=winner
        )
        return ok(message='A/B Test শেষ হয়েছে।')


class HealthCheckView(APIView):
    """System health check।"""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        checks = {}
        # DB
        try:
            from django.db import connection
            connection.ensure_connection()
            checks['database'] = 'ok'
        except Exception:
            checks['database'] = 'error'
        # Cache
        try:
            cache.set('health_ping', '1', 5)
            checks['cache'] = 'ok' if cache.get('health_ping') == '1' else 'error'
        except Exception:
            checks['cache'] = 'error'

        all_ok = all(v == 'ok' for v in checks.values())
        return Response({
            'status' : 'healthy' if all_ok else 'degraded',
            'checks' : checks,
            'timestamp': timezone.now().isoformat(),
        }, status=200 if all_ok else 207)


# ══════════════════════════════════════════════════════
# PIXEL VIEWS
# ══════════════════════════════════════════════════════

class PixelImpressionView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request, offer_id):
        from .webhooks.pixel_tracking import PixelEndpointHandler
        return PixelEndpointHandler.handle_impression(request, offer_id)

class PixelConversionView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request, token):
        from .webhooks.pixel_tracking import PixelEndpointHandler
        return PixelEndpointHandler.handle_conversion_pixel(request, token)


# ══════════════════════════════════════════════════════
# WALLET VIEW
# ══════════════════════════════════════════════════════

class MyWalletView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        from .finance_payment.wallet_integration import WalletIntegration
        data = WalletIntegration.get_balance(request.user)
        return ok(data)


# ══════════════════════════════════════════════════════
# ANALYTICS VIEWS (new)
# ══════════════════════════════════════════════════════

class PlatformKPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def get(self, request):
        from .business.kpi_dashboard import KPIDashboard
        days   = int(request.query_params.get('days', 30))
        tenant = getattr(request, 'tenant', None)
        return ok(KPIDashboard.get_platform_kpis(days=days, tenant=tenant))

class RevenueForecastView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def get(self, request):
        from .business.kpi_dashboard import KPIDashboard
        days = int(request.query_params.get('days', 30))
        return ok(KPIDashboard.forecast_revenue(days_ahead=days))

class CohortAnalysisView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def get(self, request):
        from .business.kpi_dashboard import KPIDashboard
        months = int(request.query_params.get('months', 6))
        return ok(KPIDashboard.cohort_retention(cohort_months=months))

class NetworkROIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def get(self, request):
        from .business.kpi_dashboard import KPIDashboard
        days = int(request.query_params.get('days', 30))
        return ok(KPIDashboard.network_roi_report(days=days))


# ══════════════════════════════════════════════════════
# REPORT VIEWS
# ══════════════════════════════════════════════════════

class RevenueReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def get(self, request):
        from .business.reporting_suite import ReportingEngine
        days   = int(request.query_params.get('days', 30))
        fmt    = request.query_params.get('format', 'json')
        tenant = getattr(request, 'tenant', None)
        result = ReportingEngine.revenue_report(days=days, format=fmt, tenant=tenant)
        if fmt == 'csv':
            return result
        return ok(result)

class ConversionReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def get(self, request):
        from .business.reporting_suite import ReportingEngine
        days   = int(request.query_params.get('days', 30))
        status = request.query_params.get('status')
        fmt    = request.query_params.get('format', 'json')
        result = ReportingEngine.conversion_report(days=days, status=status, format=fmt)
        if fmt == 'csv': return result
        return ok(result)

class WithdrawalReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def get(self, request):
        from .business.reporting_suite import ReportingEngine
        days   = int(request.query_params.get('days', 30))
        status = request.query_params.get('status')
        fmt    = request.query_params.get('format', 'json')
        result = ReportingEngine.withdrawal_report(days=days, status=status, format=fmt)
        if fmt == 'csv': return result
        return ok(result)

class FraudReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def get(self, request):
        from .business.reporting_suite import ReportingEngine
        days = int(request.query_params.get('days', 30))
        return ok(ReportingEngine.fraud_report(days=days))

class NetworkComparisonView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def get(self, request):
        from .business.reporting_suite import ReportingEngine
        days = int(request.query_params.get('days', 30))
        return ok(ReportingEngine.network_comparison(days=days))

class UserEarningsReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def get(self, request):
        from .business.reporting_suite import ReportingEngine
        days  = int(request.query_params.get('days', 30))
        top_n = int(request.query_params.get('top', 100))
        fmt   = request.query_params.get('format', 'json')
        result = ReportingEngine.user_earnings_report(days=days, top_n=top_n, format=fmt)
        if fmt == 'csv': return result
        return ok(result)


# ══════════════════════════════════════════════════════
# MARKETING VIEWS
# ══════════════════════════════════════════════════════

class MarketingCampaignView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def post(self, request):
        from .marketing.campaign_manager import MarketingCampaignService
        criteria   = request.data.get('criteria', {})
        title      = request.data.get('title', '')
        body       = request.data.get('body', '')
        channel    = request.data.get('channel', 'in_app')
        action_url = request.data.get('action_url', '')

        user_ids = MarketingCampaignService.build_audience(criteria)
        if not user_ids:
            return err('No users match the criteria')

        if channel == 'in_app':
            result = MarketingCampaignService.send_in_app_campaign(
                title=title, body=body, user_ids=user_ids, action_url=action_url
            )
        elif channel == 'push':
            result = MarketingCampaignService.send_push_campaign(
                title=title, body=body, user_ids=user_ids, click_url=action_url
            )
        else:
            result = MarketingCampaignService.send_email_campaign(
                subject=title, template='emails/campaign.html', user_ids=user_ids
            )
        return ok(result, 'Campaign sent.')


class PromoCodeRedeemView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .marketing.promotional_codes import PromoCodeManager
        code = request.data.get('code', '').strip().upper()
        if not code:
            return err('Code দিন।')
        result = PromoCodeManager.redeem(code, request.user)
        if result['success']:
            return ok({'reward': str(result['reward'])}, result['message'])
        return err(result['message'])


class PushSubscribeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .marketing.push_notifications import PushNotificationService
        endpoint   = request.data.get('endpoint', '')
        p256dh     = request.data.get('p256dh', '')
        auth       = request.data.get('auth', '')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if not all([endpoint, p256dh, auth]):
            return err('endpoint, p256dh, auth প্রয়োজন।')
        sub = PushNotificationService.subscribe(
            request.user, endpoint, p256dh, auth, user_agent
        )
        return ok({'subscribed': True}, 'Push subscription সফল।')


class PushUnsubscribeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .marketing.push_notifications import PushNotificationService
        endpoint = request.data.get('endpoint', '')
        PushNotificationService.unsubscribe(endpoint)
        return ok(message='Unsubscribed.')


class LeaderboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .marketing.loyalty_program import LoyaltyManager
        board = LoyaltyManager.get_leaderboard(limit=20)
        rank  = LoyaltyManager.get_user_rank(request.user)
        return ok({'leaderboard': board, 'your_rank': rank})


# ══════════════════════════════════════════════════════
# BUSINESS VIEWS
# ══════════════════════════════════════════════════════

class ExecutiveSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .business.kpi_dashboard import KPIDashboard
        tenant  = getattr(request, 'tenant', None)
        summary = KPIDashboard.executive_summary(tenant=tenant)
        return ok(summary)


class AdvertiserPortalView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .business.advertiser_portal import AdvertiserPortalService
        top = AdvertiserPortalService.top_advertisers(days=30, limit=10)
        return ok(top)

    def post(self, request):
        from .business.advertiser_portal import AdvertiserPortalService
        from decimal import Decimal
        adv = AdvertiserPortalService.register_advertiser(
            company_name    =request.data.get('company_name', ''),
            contact_name    =request.data.get('contact_name', ''),
            contact_email   =request.data.get('contact_email', ''),
            website         =request.data.get('website', ''),
            agreed_rev_share=Decimal(str(request.data.get('rev_share', '60'))),
            tenant          =getattr(request, 'tenant', None),
        )
        return ok({'id': str(adv.id), 'company': adv.company_name}, 'Advertiser registered.')


class BillingView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .business.billing_manager import BillingManager
        alerts = BillingManager.check_budget_alerts()
        return ok(alerts)

    def post(self, request):
        from .business.billing_manager import BillingManager
        action = request.data.get('action', '')
        if action == 'generate_invoices':
            result = BillingManager.generate_monthly_invoices()
            return ok(result, f'{len(result)} invoices generated.')
        if action == 'run_dunning':
            result = BillingManager.run_dunning()
            return ok(result, 'Dunning run complete.')
        if action == 'pause_depleted':
            count = BillingManager.auto_pause_depleted_campaigns()
            return ok({'paused': count})
        return err('Unknown action.')


class GDPRView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """GDPR data export for current user."""
        from .business.compliance_manager import GDPRManager
        data = GDPRManager.export_user_data(request.user)
        return ok(data, 'Your data export is ready.')

    def delete(self, request):
        """GDPR erasure request."""
        from .business.compliance_manager import GDPRManager
        result = GDPRManager.delete_user_data(request.user, reason='gdpr_user_request')
        return ok(result, 'Your data has been anonymized.')


# ══════════════════════════════════════════════════════
# BULK OPERATION VIEWS
# ══════════════════════════════════════════════════════

class BulkOfferActivateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def post(self, request):
        from .bulk_operations import BulkOfferManager
        offer_ids = request.data.get('offer_ids', [])
        count = BulkOfferManager.bulk_activate(offer_ids)
        return ok({'activated': count})

class BulkOfferPauseView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def post(self, request):
        from .bulk_operations import BulkOfferManager
        offer_ids = request.data.get('offer_ids', [])
        reason    = request.data.get('reason', 'Bulk pause')
        count = BulkOfferManager.bulk_pause(offer_ids, reason)
        return ok({'paused': count})

class BulkConversionApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def post(self, request):
        from .bulk_operations import BulkConversionManager
        ids = request.data.get('conversion_ids', [])
        result = BulkConversionManager.bulk_approve(ids, request.user)
        return ok(result)

class BulkIPBlockView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def post(self, request):
        from .bulk_operations import BulkIPManager
        ips    = request.data.get('ips', [])
        reason = request.data.get('reason', 'Bulk block')
        hours  = int(request.data.get('hours', 72))
        count  = BulkIPManager.bulk_block_from_file(ips, reason, hours)
        return ok({'blocked': count})


# ══════════════════════════════════════════════════════
# CIRCUIT BREAKER STATUS VIEW
# ══════════════════════════════════════════════════════

class CircuitStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]
    def get(self, request):
        from .offerwall_integration import OfferWallIntegrationService
        statuses = OfferWallIntegrationService.get_circuit_statuses()
        return ok(statuses)

    def post(self, request):
        """Reset a circuit breaker."""
        slug = request.data.get('network_slug', '')
        if not slug:
            return err('network_slug required')
        from .offerwall_integration import OfferWallIntegrationService
        OfferWallIntegrationService.reset_circuit(slug)
        return ok(message=f'Circuit reset: {slug}')


# ══════════════════════════════════════════════════════
# NEW MODULE VIEWS
# ══════════════════════════════════════════════════════

# ── SDK ───────────────────────────────────────────────

class SDKTokenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .api_connectivity import SDKBridge
        platform  = request.data.get('platform', 'android')
        app_id    = request.data.get('app_id', '')
        device_id = request.data.get('device_id', '')
        tenant    = getattr(request, 'tenant', None)
        result    = SDKBridge.create_sdk_token(
            request.user.id, app_id, platform, device_id, tenant
        )
        return ok(result)

    def delete(self, request):
        from .api_connectivity import SDKBridge
        token = request.data.get('token', '')
        SDKBridge.revoke_sdk_token(token)
        return ok(message='SDK token revoked.')


class SDKOffersView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from .api_connectivity import SDKBridge
        token   = request.headers.get('X-SDK-Token', '')
        payload = SDKBridge.validate_sdk_token(token)
        if not payload:
            return err('Invalid or expired SDK token', status_code=401)
        offers  = SDKBridge.get_offers_for_sdk(payload)
        return ok(offers)


class SDKConfigView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from .api_connectivity import SDKBridge
        app_id   = request.query_params.get('app_id', '')
        platform = request.query_params.get('platform', 'android')
        config   = SDKBridge.get_sdk_config(app_id, platform)
        return ok(config)


# ── User Behavior Analytics ───────────────────────────

class UserHeatmapView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .user_behavior_analysis import ActivityHeatmapService
        heatmap   = ActivityHeatmapService.get_user_heatmap(request.user)
        best_time = ActivityHeatmapService.get_best_send_time(request.user)
        return ok({'heatmap': heatmap, 'best_send_time': best_time})


class EngagementScoreView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .user_behavior_analysis import EngagementScoreCalculator
        score = EngagementScoreCalculator.calculate(request.user)
        return ok(score)


class PlatformHeatmapView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .user_behavior_analysis import ActivityHeatmapService
        data = ActivityHeatmapService.get_platform_heatmap()
        return ok(data)


class RetentionView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .user_behavior_analysis import RetentionEngine
        from datetime import date, timedelta
        days_ago = int(request.query_params.get('cohort_days_ago', 30))
        cohort   = date.today() - timedelta(days=days_ago)
        curve    = RetentionEngine.get_retention_curve(cohort, days=30)
        return ok(curve)


class ChurnView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .user_behavior_analysis import ChurnPredictor
        from .models import ChurnRecord
        from django.db.models import Avg
        records = list(
            ChurnRecord.objects.filter(is_churned=True)
            .values('user__username', 'churn_probability', 'days_inactive')
            .order_by('-churn_probability')[:50]
        )
        return ok(records)

    def post(self, request):
        """Trigger churn score recompute."""
        from .tasks import recalculate_churn_scores
        recalculate_churn_scores.delay()
        return ok(message='Churn score recompute queued.')


# ── Optimization & Scale ──────────────────────────────

class WorkerPoolView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .optimization_scale import WorkerPoolManager
        return ok(WorkerPoolManager.get_recommendations())


class BandwidthView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .optimization_scale import BandwidthMonitor
        return ok(BandwidthMonitor.get_bandwidth_stats())


class QueryOptimizerView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .optimization_scale import QueryOptimizer
        return ok({
            'slow_endpoints': QueryOptimizer.get_slow_queries(),
        })

    def post(self, request):
        from .optimization_scale import QueryOptimizer
        QueryOptimizer.warm_offer_cache(
            tenant=getattr(request, 'tenant', None)
        )
        return ok(message='Cache warmed.')


# ── Affiliate Advanced ────────────────────────────────

class PayoutBumpView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def post(self, request):
        from .affiliate_advanced import PayoutBumpManager
        from decimal import Decimal
        offer_id = request.data.get('offer_id', '')
        bump_pct = Decimal(str(request.data.get('bump_pct', 10)))
        hours    = int(request.data.get('hours', 24))
        result   = PayoutBumpManager.apply_bump(offer_id, bump_pct, hours)
        return ok(result, 'Payout bump applied.')

    def delete(self, request):
        offer_id = request.data.get('offer_id', '')
        from .affiliate_advanced import PayoutBumpManager
        PayoutBumpManager.rollback_bump(offer_id)
        return ok(message='Payout bump rolled back.')


class TrackingLinkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .affiliate_advanced import TrackingLinkGenerator
        from django.conf import settings
        offer_ids = request.data.get('offer_ids', [])
        base_url  = getattr(settings, 'SITE_URL', '')
        links     = TrackingLinkGenerator.generate_batch(offer_ids, request.user.id)
        return ok(links)


class PostbackTesterView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def post(self, request):
        from .affiliate_advanced import PostbackTester
        network_id = request.data.get('network_id', '')
        result     = PostbackTester.send_test_postback(network_id, request.user.id)
        return ok(result)


class OfferSchedulerView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .affiliate_advanced import OfferSchedulerEngine
        hours    = int(request.query_params.get('hours', 24))
        upcoming = OfferSchedulerEngine.get_upcoming_schedules(hours=hours)
        return ok(upcoming)

    def post(self, request):
        from .affiliate_advanced import OfferSchedulerEngine
        from django.utils.dateparse import parse_datetime
        offer_id    = request.data.get('offer_id', '')
        activate_at = parse_datetime(request.data.get('activate_at', ''))
        deactivate_at = parse_datetime(request.data.get('deactivate_at', '')) if request.data.get('deactivate_at') else None
        if not activate_at:
            return err('activate_at is required.')
        schedules = OfferSchedulerEngine.schedule_activation(offer_id, activate_at, deactivate_at)
        return ok([str(s.id) for s in schedules], 'Scheduled.')


# ── Compliance ────────────────────────────────────────

class TOSAcceptanceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .compliance_legal import TermsValidator
        return ok({
            'accepted'          : TermsValidator.has_accepted_current(request.user),
            'current_version'   : TermsValidator.CURRENT_TOS_VERSION,
        })

    def post(self, request):
        from .compliance_legal import TermsValidator
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')
        TermsValidator.record_acceptance(request.user, ip=ip)
        return ok(message='Terms accepted.')


class PrivacyConsentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .compliance_legal import PrivacyConsentManager
        return ok(PrivacyConsentManager.get_user_consents(request.user))

    def post(self, request):
        from .compliance_legal import PrivacyConsentManager
        consent_type = request.data.get('consent_type', '')
        granted      = bool(request.data.get('granted', False))
        ip           = request.META.get('REMOTE_ADDR', '')
        PrivacyConsentManager.record_consent(request.user, consent_type, granted, ip)
        return ok(message='Consent recorded.')


class KYCVerifyView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def post(self, request):
        from .compliance_legal import KYCVerificationService
        from .models import UserKYC
        kyc_id   = request.data.get('kyc_id', '')
        action   = request.data.get('action', '')
        reason   = request.data.get('reason', '')
        try:
            kyc = UserKYC.objects.get(id=kyc_id)
        except UserKYC.DoesNotExist:
            return err('KYC record not found.')
        if action == 'approve':
            KYCVerificationService.approve(kyc, request.user)
            return ok(message='KYC approved.')
        elif action == 'reject':
            KYCVerificationService.reject(kyc, request.user, reason)
            return ok(message='KYC rejected.')
        return err('Action must be approve or reject.')


# ── Emergency / System ────────────────────────────────

class EmergencyShutdownView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .maintenance_logs import EmergencyShutdown
        return ok(EmergencyShutdown.get_status())

    def post(self, request):
        from .maintenance_logs import EmergencyShutdown
        action = request.data.get('action', '')
        if action == 'activate':
            reason = request.data.get('reason', 'Emergency shutdown')
            result = EmergencyShutdown.activate(reason, request.user)
            return ok(result, 'Emergency shutdown activated.')
        elif action == 'deactivate':
            result = EmergencyShutdown.deactivate(request.user)
            return ok(result, 'Operations restored.')
        return err('action must be activate or deactivate.')


class SecurityAuditView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .maintenance_logs import SecurityAuditReporter
        days   = int(request.query_params.get('days', 30))
        report = SecurityAuditReporter.generate_report(days=days)
        return ok(report)


class SystemRecoveryView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def post(self, request):
        from .misc_features import SystemRecovery
        action = request.data.get('action', '')
        if action == 'recover_conversions':
            result = SystemRecovery.recover_stuck_conversions()
            return ok(result)
        elif action == 'recover_payouts':
            result = SystemRecovery.recover_failed_payouts()
            return ok(result)
        elif action == 'rebuild_caps':
            result = SystemRecovery.rebuild_offer_caps()
            return ok(result)
        elif action == 'clear_caches':
            result = SystemRecovery.clear_all_caches()
            return ok(result)
        return err('Unknown action.')


# ── Reports ───────────────────────────────────────────

class ConversionSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .reporting import ReportGenerator
        days   = int(request.query_params.get('days', 30))
        tenant = getattr(request, 'tenant', None)
        return ok(ReportGenerator.conversion_summary(days=days, tenant=tenant))


class PostbackDeliveryReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .reporting import ReportGenerator
        days = int(request.query_params.get('days', 7))
        return ok(ReportGenerator.postback_delivery_report(days=days))


class UserGrowthReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .reporting import ReportGenerator
        days = int(request.query_params.get('days', 30))
        return ok(ReportGenerator.user_growth(days=days))


class UserLTVReportView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .reporting import ReportGenerator
        return ok(ReportGenerator.user_lifetime_value_distribution())


class PayoutReconciliationView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .reporting import ReportGenerator
        month = request.query_params.get('month', None)
        return ok(ReportGenerator.payout_reconciliation(month=month))


# ── Multi-language & UI ───────────────────────────────

class LanguageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .misc_features import MultiLanguageSupport
        lang    = MultiLanguageSupport.detect_language(request)
        strings = MultiLanguageSupport.get_all_strings(lang)
        return ok({'language': lang, 'strings': strings})

    def post(self, request):
        from .misc_features import MultiLanguageSupport
        lang = request.data.get('language', 'bn')
        MultiLanguageSupport.set_user_language(request.user, lang)
        return ok(message=f'Language set to {lang}.')


class ThemeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .misc_features import DarkModeAssetManager
        theme = DarkModeAssetManager.get_user_theme(request.user)
        css   = DarkModeAssetManager.get_css_variables(theme)
        return ok({'theme': theme, 'css_variables': css})

    def post(self, request):
        from .misc_features import DarkModeAssetManager
        theme = request.data.get('theme', 'dark')
        DarkModeAssetManager.set_user_theme(request.user, theme)
        return ok(message=f'Theme set to {theme}.')


# ── Full Analytics Dashboard ──────────────────────────

class FullAnalyticsDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .misc_features import AnalyticsDashboard
        days   = int(request.query_params.get('days', 7))
        tenant = getattr(request, 'tenant', None)
        return ok(AnalyticsDashboard.get_full_dashboard(tenant=tenant, days=days))


class UserAnalyticsDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .misc_features import AnalyticsDashboard
        return ok(AnalyticsDashboard.get_user_dashboard(request.user))


# ── Webhook Management ────────────────────────────────

class WebhookConfigListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .models import WebhookConfig
        configs = list(
            WebhookConfig.objects.filter(is_active=True)
            .values('id', 'name', 'url', 'events', 'last_fired', 'last_status')
        )
        return ok(configs)

    def post(self, request):
        from .models import WebhookConfig
        config = WebhookConfig.objects.create(
            name      =request.data.get('name', ''),
            url       =request.data.get('url', ''),
            events    =request.data.get('events', []),
            secret_key=request.data.get('secret', ''),
            tenant    =getattr(request, 'tenant', None),
        )
        return ok({'id': str(config.id)}, 'Webhook configured.')


class WebhookTestView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def post(self, request):
        from .webhooks import WebhookDispatcher
        event   = request.data.get('event', 'test')
        payload = request.data.get('payload', {'test': True})
        result  = WebhookDispatcher.deliver_to_all_configs(
            event, payload, tenant=getattr(request, 'tenant', None)
        )
        return ok(result)


# ── MasterSwitch ─────────────────────────────────────

class MasterSwitchListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .maintenance_logs import MasterSwitchController
        tenant = getattr(request, 'tenant', None)
        return ok(MasterSwitchController.get_all_features(tenant=tenant))

    def post(self, request):
        from .maintenance_logs import MasterSwitchController
        feature = request.data.get('feature', '')
        enabled = bool(request.data.get('enabled', True))
        tenant  = getattr(request, 'tenant', None)
        result  = MasterSwitchController.toggle_feature(
            feature, enabled, tenant, request.user
        )
        return ok(result)


# ══════════════════════════════════════════════════════
# RTB ENGINE VIEWS
# ══════════════════════════════════════════════════════

class RTBBidView(APIView):
    """OpenRTB 2.6 bid endpoint — receives bid requests from publishers."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        from .rtb_engine.bid_processor import BidProcessor, BidRequest
        from decimal import Decimal as D

        data  = request.data
        br    = BidRequest(
            request_id  =data.get('id', ''),
            publisher_id=data.get('publisher_id', '') or request.headers.get('X-Publisher-Id', ''),
            app_id      =data.get('app_id', ''),
            user_id     =data.get('user_id', ''),
            ip          =self._get_ip(request),
            user_agent  =request.META.get('HTTP_USER_AGENT', ''),
            country     =data.get('country', ''),
            device_type =data.get('device_type', 'mobile'),
            floor_price =D(str(data.get('floor_price', '0'))),
        )
        response = BidProcessor.process(br)
        if response.no_bid:
            return Response(status=204)   # OpenRTB no-bid response
        return ok({
            'id'      : response.request_id,
            'bid_id'  : response.bid_id,
            'offer_id': response.offer_id,
            'title'   : response.offer_title,
            'creative': response.creative_url,
            'click_url': response.click_url,
            'ecpm'    : str(response.ecpm),
            'win_url' : response.win_notif_url,
        })

    def _get_ip(self, request) -> str:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')


class RTBWinView(APIView):
    """RTB win notification endpoint."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from .rtb_engine.win_notifier import WinNotifier
        from decimal import Decimal as D
        bid_id = request.query_params.get('bid_id', '')
        price  = D(str(request.query_params.get('price', '0')))
        WinNotifier.notify_win(bid_id, price)
        return Response(status=200)


class RTBStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .rtb_engine.win_notifier import WinNotifier
        from .rtb_engine.ecpm_calculator import ECPMCalculator
        days = int(request.query_params.get('days', 7))
        return ok({
            'win_rate'    : WinNotifier.get_win_rate(days=days),
            'top_ecpm'    : ECPMCalculator.get_platform_ecpm_report(days=days)[:10],
        })


class RTBBidFloorView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .rtb_engine.bid_floor_manager import BidFloorManager
        return ok(BidFloorManager.get_floor_report())

    def post(self, request):
        from .rtb_engine.bid_floor_manager import BidFloorManager
        from decimal import Decimal as D
        pub_id  = request.data.get('publisher_id', '')
        floor   = D(str(request.data.get('floor', '0.5')))
        country = request.data.get('country', 'default')
        BidFloorManager.set_publisher_floor(pub_id, floor, country)
        return ok(message='Floor price updated.')


# ══════════════════════════════════════════════════════
# ML FRAUD VIEWS
# ══════════════════════════════════════════════════════

class MLFraudScoreView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def post(self, request):
        from .ml_fraud.ml_scorer import MLFraudScorer
        ip         = request.data.get('ip', '')
        user_agent = request.data.get('user_agent', '')
        rule_score = float(request.data.get('rule_score', 0))
        result     = MLFraudScorer.score(ip, user_agent=user_agent, rule_based_score=rule_score)
        return ok(result)

    def get(self, request):
        from .ml_fraud.ml_scorer import MLFraudScorer
        return ok(MLFraudScorer.get_model_info())


class MLFraudTrainView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def post(self, request):
        from .ml_fraud.model_trainer import FraudModelTrainer
        days          = int(request.data.get('days', 30))
        n_estimators  = int(request.data.get('n_estimators', 100))
        contamination = float(request.data.get('contamination', 0.1))
        result        = FraudModelTrainer.train(days, n_estimators, contamination)
        return ok(result)


class MLAnomalyView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .ml_fraud.anomaly_detector import AnomalyDetector
        hours = int(request.query_params.get('hours', 6))
        return ok({
            'click_farms'       : AnomalyDetector.detect_click_farm(hours=hours),
            'coordinated_fraud' : AnomalyDetector.detect_coordinated_fraud(hours=hours),
            'bot_networks'      : AnomalyDetector.detect_bot_network(hours=hours),
        })

    def post(self, request):
        """Auto-block detected click farms."""
        from .ml_fraud.anomaly_detector import AnomalyDetector
        dry_run = request.data.get('dry_run', True)
        result  = AnomalyDetector.auto_block_detected(dry_run=dry_run)
        return ok(result)


# ══════════════════════════════════════════════════════
# PUBLISHER SDK VIEWS
# ══════════════════════════════════════════════════════

class PublisherRegisterView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def post(self, request):
        from .publisher_sdk.publisher_portal import PublisherPortal
        result = PublisherPortal.register_publisher(
            company_name  =request.data.get('company_name', ''),
            contact_email =request.data.get('contact_email', ''),
            website       =request.data.get('website', ''),
            app_type      =request.data.get('app_type', 'mobile'),
            tenant        =getattr(request, 'tenant', None),
        )
        return ok(result, 'Publisher registered. Pending review.')


class PublisherApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def post(self, request, publisher_id):
        from .publisher_sdk.publisher_portal import PublisherPortal
        ok_result = PublisherPortal.approve_publisher(publisher_id, request.user)
        return ok(message='Publisher approved.') if ok_result else err('Publisher not found.')


class PublisherDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .publisher_sdk.publisher_portal import PublisherPortal
        from .models import Publisher
        api_key = request.headers.get('X-Publisher-Api-Key', '')
        validation = PublisherPortal.validate_api_key(api_key)
        if not validation.get('valid'):
            return err('Invalid publisher API key.', status_code=401)
        days    = int(request.query_params.get('days', 30))
        data    = PublisherPortal.get_dashboard(validation['publisher_id'], days=days)
        return ok(data)


class PublisherAppView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .publisher_sdk.app_manager import AppManager
        from .publisher_sdk.publisher_portal import PublisherPortal
        api_key    = request.headers.get('X-Publisher-Api-Key', '')
        validation = PublisherPortal.validate_api_key(api_key)
        if not validation.get('valid'):
            return err('Invalid publisher API key.', status_code=401)
        apps = AppManager.get_publisher_apps(validation['publisher_id'])
        return ok(apps)

    def post(self, request):
        from .publisher_sdk.app_manager import AppManager
        from .publisher_sdk.publisher_portal import PublisherPortal
        api_key    = request.headers.get('X-Publisher-Api-Key', '')
        validation = PublisherPortal.validate_api_key(api_key)
        if not validation.get('valid'):
            return err('Invalid publisher API key.', status_code=401)
        result = AppManager.register_app(
            publisher_id=validation['publisher_id'],
            app_name    =request.data.get('name', ''),
            platform    =request.data.get('platform', 'android'),
            bundle_id   =request.data.get('bundle_id', ''),
            category    =request.data.get('category', ''),
        )
        return ok(result, 'App registered.')


class SDKConfigView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .publisher_sdk.sdk_config_generator import SDKConfigGenerator
        from .publisher_sdk.publisher_portal import PublisherPortal
        api_key    = request.headers.get('X-Publisher-Api-Key', '')
        validation = PublisherPortal.validate_api_key(api_key)
        if not validation.get('valid'):
            return err('Invalid publisher API key.', status_code=401)
        platform  = request.query_params.get('platform', 'android')
        app_id    = request.query_params.get('app_id', '')
        pub_id    = validation['publisher_id']
        configs   = {
            'android': SDKConfigGenerator.for_android,
            'ios'    : SDKConfigGenerator.for_ios,
            'unity'  : SDKConfigGenerator.for_unity,
            'web'    : SDKConfigGenerator.for_web,
        }
        fn = configs.get(platform, SDKConfigGenerator.for_android)
        return ok(fn(pub_id, app_id))


class PublisherPayoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .publisher_sdk.publisher_payout import PublisherPayoutManager
        from .publisher_sdk.publisher_portal import PublisherPortal
        api_key    = request.headers.get('X-Publisher-Api-Key', '')
        validation = PublisherPortal.validate_api_key(api_key)
        if not validation.get('valid'):
            return err('Invalid publisher API key.', status_code=401)
        pub_id   = validation['publisher_id']
        earnings = PublisherPayoutManager.calculate_earnings(pub_id)
        history  = PublisherPayoutManager.get_payout_history(pub_id)
        return ok({'earnings': earnings, 'history': history})

    def post(self, request):
        """Request a publisher payout."""
        from .publisher_sdk.publisher_payout import PublisherPayoutManager
        from .publisher_sdk.publisher_portal import PublisherPortal
        api_key    = request.headers.get('X-Publisher-Api-Key', '')
        validation = PublisherPortal.validate_api_key(api_key)
        if not validation.get('valid'):
            return err('Invalid publisher API key.', status_code=401)
        result = PublisherPayoutManager.process_payout(validation['publisher_id'])
        return ok(result) if result.get('success') else err(result.get('reason', 'Payout failed.'))


# ══════════════════════════════════════════════════════════════════════
# OFFER SEARCH & DISCOVERY VIEWS
# ══════════════════════════════════════════════════════════════════════

class OfferSearchView(APIView):
    """Full-text offer search with filters."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .offer_search.search_engine import OfferSearchEngine
        from decimal import Decimal as D
        result = OfferSearchEngine.search(
            query       = request.query_params.get('q', ''),
            category    = request.query_params.get('category', ''),
            network_id  = request.query_params.get('network', ''),
            min_reward  = D(request.query_params['min_reward']) if request.query_params.get('min_reward') else None,
            max_reward  = D(request.query_params['max_reward']) if request.query_params.get('max_reward') else None,
            device_type = request.query_params.get('device', ''),
            country     = request.query_params.get('country', ''),
            page        = int(request.query_params.get('page', 1)),
            page_size   = int(request.query_params.get('page_size', 20)),
            tenant      = getattr(request, 'tenant', None),
        )
        return ok(result)


class OfferAutocompleteView(APIView):
    """Fast offer title autocomplete."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .offer_search.search_engine import OfferSearchEngine
        results = OfferSearchEngine.autocomplete(
            query  = request.query_params.get('q', ''),
            limit  = int(request.query_params.get('limit', 10)),
            tenant = getattr(request, 'tenant', None),
        )
        return ok(results)


class TrendingOffersView(APIView):
    """Trending and highest-paying offers."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .offer_search.trending_offers import TrendingOffersEngine
        view_type = request.query_params.get('type', 'trending')
        limit     = int(request.query_params.get('limit', 10))
        tenant    = getattr(request, 'tenant', None)

        handlers = {
            'trending'      : lambda: TrendingOffersEngine.get_trending(limit=limit, tenant=tenant),
            'new'           : lambda: TrendingOffersEngine.get_new_offers(limit=limit, tenant=tenant),
            'highest_paying': lambda: TrendingOffersEngine.get_highest_paying(limit=limit, tenant=tenant),
        }
        data = handlers.get(view_type, handlers['trending'])()
        return ok(data)


class SearchFiltersView(APIView):
    """Return all available search filter options."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .offer_search.search_engine import OfferSearchEngine
        return ok(OfferSearchEngine.get_filters(tenant=getattr(request, 'tenant', None)))


# ══════════════════════════════════════════════════════════════════════
# OFFER APPROVAL WORKFLOW VIEWS
# ══════════════════════════════════════════════════════════════════════

class OfferSubmitReviewView(APIView):
    """Submit an offer for review (advertiser action)."""
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def post(self, request, offer_id):
        from .models import Offer as OfferModel
        from .offer_approval.approval_engine import OfferApprovalEngine
        try:
            offer  = OfferModel.objects.get(id=offer_id)
            result = OfferApprovalEngine.submit_for_review(offer, submitted_by=request.user)
            return ok(result)
        except OfferModel.DoesNotExist:
            return err('Offer not found.', status_code=404)


class OfferReviewQueueView(APIView):
    """Admin: Get pending offer review queue."""
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .offer_approval.review_queue import OfferReviewQueue
        return ok({
            'queue': OfferReviewQueue.get_pending(limit=50),
            'stats': OfferReviewQueue.get_stats(),
        })


class OfferApproveRejectView(APIView):
    """Admin: Approve or reject an offer."""
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def post(self, request, offer_id):
        from .offer_approval.approval_engine import OfferApprovalEngine
        action = request.data.get('action', '')
        reason = request.data.get('reason', '')

        if action == 'approve':
            success = OfferApprovalEngine.approve(offer_id, request.user)
            return ok(message='Offer approved.') if success else err('Not found.', status_code=404)
        elif action == 'reject':
            if not reason:
                return err('Reject reason is required.')
            success = OfferApprovalEngine.reject(offer_id, request.user, reason)
            return ok(message='Offer rejected.') if success else err('Not found.', status_code=404)
        return err('action must be "approve" or "reject".')


class OfferBulkApproveView(APIView):
    """Admin: Bulk approve offers."""
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def post(self, request):
        from .offer_approval.review_queue import OfferReviewQueue
        offer_ids = request.data.get('offer_ids', [])
        if not offer_ids:
            return err('offer_ids required.')
        result = OfferReviewQueue.bulk_approve(offer_ids, request.user)
        return ok(result)


# ══════════════════════════════════════════════════════════════════════
# MULTI-CURRENCY WALLET VIEWS
# ══════════════════════════════════════════════════════════════════════

class MultiCurrencyBalanceView(APIView):
    """Get user wallet balances in all currencies."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .multi_currency.currency_wallet import MultiCurrencyWallet
        balances = MultiCurrencyWallet.get_balances(request.user)
        target   = request.query_params.get('convert_to', 'BDT')
        total    = MultiCurrencyWallet.get_total_in_currency(request.user, target)
        return ok({
            'balances'    : balances,
            'total_in'    : {target: float(total)},
            'currencies'  : ['BDT', 'USD', 'EUR', 'GBP', 'INR', 'SGD', 'AED'],
        })


class CurrencyExchangeView(APIView):
    """Exchange currency in user wallet."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from .multi_currency.currency_wallet import MultiCurrencyWallet
        from decimal import Decimal as D
        amount   = D(str(request.data.get('amount', '0')))
        from_c   = request.data.get('from_currency', 'BDT').upper()
        to_c     = request.data.get('to_currency', 'USD').upper()
        if amount <= 0:
            return err('amount must be positive.')
        try:
            result = MultiCurrencyWallet.exchange(request.user, amount, from_c, to_c)
            return ok(result)
        except Exception as e:
            return err(str(e))


class ExchangeRatesView(APIView):
    """Get live exchange rates."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .multi_currency.currency_wallet import ExchangeEngine
        base  = request.query_params.get('base', 'BDT').upper()
        rates = ExchangeEngine.get_all_rates(base)
        return ok({'base': base, 'rates': rates})


class LocalPayoutView(APIView):
    """Get reward amount in user's local currency."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .multi_currency.currency_wallet import ExchangeEngine
        from decimal import Decimal as D
        reward_bdt   = D(str(request.query_params.get('reward_bdt', '0')))
        user_country = request.query_params.get('country', 'BD').upper()
        return ok(ExchangeEngine.get_payout_in_local(reward_bdt, user_country))


# ══════════════════════════════════════════════════════════════════════
# NOTIFICATION PREFERENCES VIEW
# ══════════════════════════════════════════════════════════════════════

class NotificationPrefsView(APIView):
    """Get and update user notification preferences."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .compliance_legal.privacy_consent import PrivacyConsentManager
        consents = PrivacyConsentManager.get_user_consents(request.user)
        try:
            from .models import UserProfile
            profile = UserProfile.objects.get(user=request.user)
            prefs   = profile.notification_prefs or {}
        except Exception:
            prefs = {}
        return ok({'notification_prefs': prefs, 'consents': consents})

    def patch(self, request):
        from .models import UserProfile
        from .compliance_legal.privacy_consent import PrivacyConsentManager
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        prefs      = profile.notification_prefs or {}
        prefs.update(request.data.get('notification_prefs', {}))
        UserProfile.objects.filter(user=request.user).update(notification_prefs=prefs)
        # Update consent
        for ct, granted in request.data.get('consents', {}).items():
            try:
                PrivacyConsentManager.record_consent(
                    request.user, ct, bool(granted),
                    ip=request.META.get('REMOTE_ADDR', '')
                )
            except ValueError:
                pass
        return ok(message='Preferences updated.')


# ══════════════════════════════════════════════════════════════════════
# A/B TEST RESULTS VIEW
# ══════════════════════════════════════════════════════════════════════

class ABTestResultsView(APIView):
    """Get A/B test results for a test."""
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request, test_name):
        from .ai_optimization.a_b_testing import ABTestingEngine
        result = ABTestingEngine.get_results(test_name)
        return ok(result)

    def get_list(self, request):
        from .models import ABTestGroup
        from django.db.models import Count
        groups = list(
            ABTestGroup.objects.values('test_name')
            .annotate(variants=Count('variant', distinct=True))
            .order_by('test_name')
        )
        return ok(groups)


# ══════════════════════════════════════════════════════════════════════
# SYSTEM HEALTH + RECOVERY VIEWS
# ══════════════════════════════════════════════════════════════════════

class SystemHealthDetailView(APIView):
    """Detailed system health check."""
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .system_devops.health_check import SystemHealthChecker
        return ok(SystemHealthChecker.run_all_checks())


class SystemRecoveryView(APIView):
    """Trigger system recovery procedures."""
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .misc_features.system_recovery import SystemRecovery
        return ok(SystemRecovery.recovery_report())

    def post(self, request):
        from .misc_features.system_recovery import SystemRecovery
        action = request.data.get('action', '')
        handlers = {
            'stuck_conversions' : SystemRecovery.recover_stuck_conversions,
            'failed_payouts'    : SystemRecovery.recover_failed_payouts,
            'rebuild_caps'      : SystemRecovery.rebuild_offer_caps,
            'fix_wallets'       : SystemRecovery.fix_wallet_balances,
        }
        fn = handlers.get(action)
        if not fn:
            return err(f'Unknown action. Choose from: {list(handlers.keys())}')
        result = fn()
        return ok(result)


# ══════════════════════════════════════════════════════════════════════
# MASTER SWITCH VIEW
# ══════════════════════════════════════════════════════════════════════

class MasterSwitchView(APIView):
    """Toggle platform features on/off."""
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .maintenance_logs.master_switch import MasterSwitchController
        return ok(MasterSwitchController.get_all(getattr(request, 'tenant', None)))

    def post(self, request):
        from .maintenance_logs.master_switch import MasterSwitchController
        feature = request.data.get('feature', '')
        enabled = bool(request.data.get('enabled', True))
        try:
            result = MasterSwitchController.toggle(
                feature, enabled,
                tenant=getattr(request, 'tenant', None),
                user=request.user,
            )
            return ok(result)
        except ValueError as e:
            return err(str(e))


# ══════════════════════════════════════════════════════════════════════
# SECURITY AUDIT VIEW
# ══════════════════════════════════════════════════════════════════════

class SecurityAuditView(APIView):
    """Security audit reports."""
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .maintenance_logs.security_audit_report import SecurityAuditReporter
        days = int(request.query_params.get('days', 30))
        return ok(SecurityAuditReporter.generate_report(days=days))


# ══════════════════════════════════════════════════════════════════════
# EXPORT MANAGER VIEW
# ══════════════════════════════════════════════════════════════════════

class ExportView(APIView):
    """Data export endpoint."""
    permission_classes = [permissions.IsAuthenticated, IsOfferAdmin]

    def get(self, request):
        from .reporting_audit.export_manager import ExportManager
        return ok(ExportManager.get_available_exports())

    def post(self, request):
        from .reporting_audit.export_manager import ExportManager
        export_type = request.data.get('export_type', '')
        fmt         = request.data.get('format', 'json')
        days        = int(request.data.get('days', 30))
        try:
            result = ExportManager.export(export_type, format=fmt, days=days)
            if hasattr(result, 'status_code'):
                return result
            return ok(result)
        except ValueError as e:
            return err(str(e))
