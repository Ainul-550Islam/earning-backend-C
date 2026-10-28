from typing import Dict, List, Any, Optional, Tuple, Union
# api/cms/viewsets/ExtrasViewSets.py
"""
ViewSets for extra CPAlead CMS models:
- NotificationViewSet
- AnnouncementViewSet
- TestimonialViewSet
- SocialLinkViewSet
- EmailTemplateViewSet
- UserInteractionViewSet
- CPALeadWebhookView (postback handler)
- EarningCapViewSet
"""
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# NotificationViewSet
# ─────────────────────────────────────────────

class NotificationViewSet(viewsets.ModelViewSet):
    """
    In-app notifications for users.

    GET    /api/cms/notifications/              - List my notifications
    GET    /api/cms/notifications/unread_count/ - Get unread count
    POST   /api/cms/notifications/{id}/mark_read/ - Mark as read
    POST   /api/cms/notifications/mark_all_read/ - Mark all read
    DELETE /api/cms/notifications/{id}/         - Delete notification
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models_new.extras import Notification
        user = self.request.user
        if user.is_staff and self.request.query_params.get('user_id'):
            return Notification.objects.filter(
                user_id=self.request.query_params['user_id'], is_active=True
            )
        return Notification.objects.filter(user=user, is_active=True)

    def get_serializer_class(self):
        from api.cms.serializers import NotificationSerializer
        return NotificationSerializer

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        unread_only = request.query_params.get('unread_only') == 'true'
        if unread_only:
            qs = qs.filter(is_read=False)
        notif_type = request.query_params.get('type')
        if notif_type:
            qs = qs.filter(notification_type=notif_type)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(self.get_serializer(qs, many=True).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user != request.user and not request.user.is_staff:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        instance.is_active = False
        instance.save(update_fields=['is_active'])
        cache.delete(f'notif_unread_{request.user.id}')
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        from api.cms.services_new.NotificationService import NotificationService
        count = NotificationService.get_unread_count(request.user)
        return Response({'unread_count': count})

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        from api.cms.services_new.NotificationService import NotificationService
        success = NotificationService.mark_read(int(pk), request.user)
        if success:
            return Response({'marked_read': True})
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        from api.cms.services_new.NotificationService import NotificationService
        count = NotificationService.mark_all_read(request.user)
        return Response({'marked_read': count})

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def broadcast(self, request):
        """Preview broadcast — admin only."""
        from api.cms.models_new.extras import Notification
        total_users = Notification.objects.values('user').distinct().count()
        return Response({'total_users': total_users, 'note': 'POST to /broadcast/ to send'})

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def send_broadcast(self, request):
        """Broadcast notification to all users."""
        from api.cms.services_new.NotificationService import NotificationService
        from django.contrib.auth import get_user_model
        User = get_user_model()
        title = request.data.get('title', '')
        message = request.data.get('message', '')
        notif_type = request.data.get('type', 'system')
        if not title or not message:
            return Response({'error': 'title and message required'}, status=status.HTTP_400_BAD_REQUEST)
        user_ids = list(User.objects.filter(is_active=True).values_list('id', flat=True)[:5000])
        from api.cms.models_new.extras import Notification
        Notification.bulk_create_for_users(user_ids, notif_type, title, message)
        return Response({'sent': len(user_ids)})


# ─────────────────────────────────────────────
# AnnouncementViewSet
# ─────────────────────────────────────────────

class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    Site-wide announcements.

    GET    /api/cms/announcements/          - List active (public)
    POST   /api/cms/announcements/          - Create (admin)
    GET    /api/cms/announcements/active/   - Active announcements (public)
    POST   /api/cms/announcements/{id}/dismiss/ - Dismiss (auth)
    """
    authentication_classes = [JWTAuthentication]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'message']
    ordering_fields = ['priority', 'created_at', 'is_pinned']
    ordering = ['-is_pinned', '-priority', '-created_at']

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'active'):
            return [AllowAny()]
        if self.action == 'dismiss':
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        from api.cms.models_new.extras import Announcement
        if self.request.user.is_staff if hasattr(self.request, 'user') and self.request.user.is_authenticated else False:
            return Announcement.objects.all()
        return Announcement.objects.filter(is_active=True)

    def get_serializer_class(self):
        from api.cms.serializers import AnnouncementSerializer
        return AnnouncementSerializer

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def active(self, request):
        from api.cms.models_new.extras import Announcement
        user = request.user if request.user.is_authenticated else None
        announcements = Announcement.get_active(user=user, limit=10)
        return Response(self.get_serializer(announcements, many=True).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def dismiss(self, request, pk=None):
        announcement = self.get_object()
        announcement.record_dismiss()
        return Response({'dismissed': True})


# ─────────────────────────────────────────────
# TestimonialViewSet
# ─────────────────────────────────────────────

class TestimonialViewSet(viewsets.ModelViewSet):
    """Earning site testimonials."""
    authentication_classes = [JWTAuthentication]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['content', 'author_name']
    ordering_fields = ['sort_order', 'rating', 'earning_amount']
    ordering = ['-is_featured', 'sort_order', '-created_at']

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'featured'):
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        from api.cms.models_new.extras import Testimonial
        return Testimonial.objects.filter(is_active=True).select_related('user')

    def get_serializer_class(self):
        from api.cms.serializers import TestimonialSerializer
        return TestimonialSerializer

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def featured(self, request):
        from api.cms.models_new.extras import Testimonial
        limit = int(request.query_params.get('limit', 6))
        testimonials = Testimonial.get_featured(limit=limit)
        return Response(self.get_serializer(testimonials, many=True).data)


# ─────────────────────────────────────────────
# SocialLinkViewSet
# ─────────────────────────────────────────────

class SocialLinkViewSet(viewsets.ModelViewSet):
    """Social media links for footer/header."""
    authentication_classes = [JWTAuthentication]
    filter_backends = [filters.OrderingFilter]
    ordering = ['sort_order', 'platform']

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'by_location'):
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        from api.cms.models_new.extras import SocialLink
        return SocialLink.objects.filter(is_active=True)

    def get_serializer_class(self):
        from api.cms.serializers import SocialLinkSerializer
        return SocialLinkSerializer

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def by_location(self, request):
        from api.cms.models_new.extras import SocialLink
        location = request.query_params.get('location', 'footer')
        links = SocialLink.get_for_location(location=location)
        return Response(self.get_serializer(links, many=True).data)


# ─────────────────────────────────────────────
# UserInteractionViewSet
# ─────────────────────────────────────────────

class UserInteractionViewSet(viewsets.ViewSet):
    """
    User content interactions: like, bookmark, share, rate.

    POST /api/cms/interactions/toggle/      - Toggle like/bookmark
    GET  /api/cms/interactions/check/       - Check if user interacted
    GET  /api/cms/interactions/counts/      - Get interaction counts
    POST /api/cms/interactions/rate/        - Rate content
    GET  /api/cms/interactions/my_bookmarks/ - Get user bookmarks
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def toggle(self, request):
        """Toggle like or bookmark for content."""
        from api.cms.models_new.extras import UserContentInteraction
        interaction_type = request.data.get('interaction_type', 'like')
        content_type = request.data.get('content_type', 'page')
        content_id = request.data.get('content_id')
        if not content_id:
            return Response({'error': 'content_id required'}, status=status.HTTP_400_BAD_REQUEST)
        obj, added = UserContentInteraction.toggle(
            user=request.user,
            interaction_type=interaction_type,
            content_type=content_type,
            content_id=int(content_id),
        )
        return Response({'action': 'added' if added else 'removed', 'interaction_type': interaction_type})

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def counts(self, request):
        """Get interaction counts for content."""
        from api.cms.models_new.extras import UserContentInteraction
        content_type = request.query_params.get('content_type', 'page')
        content_id = request.query_params.get('content_id')
        if not content_id:
            return Response({'error': 'content_id required'}, status=status.HTTP_400_BAD_REQUEST)
        counts = {}
        for itype in ['like', 'bookmark', 'helpful']:
            counts[itype] = UserContentInteraction.get_count(content_type, int(content_id), itype)
        return Response(counts)

    @action(detail=False, methods=['post'])
    def rate(self, request):
        """Rate content with 1-5 stars."""
        from api.cms.models_new.extras import ContentRating
        content_type = request.data.get('content_type', 'page')
        content_id = request.data.get('content_id')
        rating = request.data.get('rating')
        if not content_id or not rating:
            return Response({'error': 'content_id and rating required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rating_int = int(rating)
            if not 1 <= rating_int <= 5:
                raise ValueError()
        except ValueError:
            return Response({'error': 'rating must be 1-5'}, status=status.HTTP_400_BAD_REQUEST)
        obj, created = ContentRating.rate(
            user=request.user,
            content_type=content_type,
            content_id=int(content_id),
            rating=rating_int,
            review=request.data.get('review', ''),
            ip=request.META.get('REMOTE_ADDR'),
        )
        avg = ContentRating.get_average(content_type, int(content_id))
        return Response({'rated': True, 'your_rating': rating_int, **avg})

    @action(detail=False, methods=['get'])
    def my_bookmarks(self, request):
        """Get user's bookmarked content."""
        from api.cms.models_new.extras import UserContentInteraction
        content_type = request.query_params.get('content_type')
        qs = UserContentInteraction.objects.filter(
            user=request.user, interaction_type='bookmark'
        )
        if content_type:
            qs = qs.filter(content_type=content_type)
        return Response([{
            'content_type': i.content_type,
            'content_id': i.content_id,
            'created_at': i.created_at,
        } for i in qs.order_by('-created_at')[:50]])


# ─────────────────────────────────────────────
# CPAlead Webhook (Postback) View
# ─────────────────────────────────────────────

class CPALeadWebhookView(APIView):
    """
    CPAlead postback/webhook endpoint.
    CPAlead calls this URL when a user completes an offer.

    GET/POST /api/cms/webhooks/cpalead/
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, *args, **kwargs):
        """Handle GET postback (some networks use GET)."""
        return self._process_postback(request.GET.dict(), request)

    def post(self, request, *args, **kwargs):
        """Handle POST postback."""
        data = request.data if hasattr(request.data, 'dict') else dict(request.data)
        return self._process_postback(data, request)

    def _process_postback(self, data, request):
        from api.cms.services_new.CPALeadService import CPALeadService
        ip = request.META.get('REMOTE_ADDR', '')
        logger.info(f"CPAlead postback received from {ip}: {list(data.keys())}")
        success, message = CPALeadService.handle_postback(data, request_ip=ip)
        if success:
            # Return "1" — CPAlead expects this confirmation
            from django.http import HttpResponse
            return HttpResponse("1", content_type='text/plain', status=200)
        logger.warning(f"CPAlead postback failed: {message}")
        return Response({'status': 'error', 'message': message}, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# EarningCapViewSet (user-facing)
# ─────────────────────────────────────────────

class EarningCapViewSet(viewsets.ViewSet):
    """
    Earning cap info for CPAlead site.

    GET /api/cms/earning-cap/status/ - Current cap status for logged-in user
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get earning cap status for current user."""
        from api.cms.services_new.CPALeadService import EarningCapService
        cap_info = EarningCapService.get_cap_info(request.user)
        return Response(cap_info)


# ─────────────────────────────────────────────
# EmailTemplateViewSet
# ─────────────────────────────────────────────

class EmailTemplateViewSet(viewsets.ModelViewSet):
    """Admin management of email templates."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'subject', 'email_type']

    def get_queryset(self):
        from api.cms.models_new.extras import EmailTemplate
        return EmailTemplate.objects.all()

    def get_serializer_class(self):
        from api.cms.serializers import EmailTemplateSerializer
        return EmailTemplateSerializer

    @action(detail=True, methods=['post'])
    def test_send(self, request, pk=None):
        """Send a test email."""
        template = self.get_object()
        test_email = request.data.get('email', request.user.email)
        if not test_email:
            return Response({'error': 'email required'}, status=status.HTTP_400_BAD_REQUEST)
        from api.cms.tasks.notification_tasks import send_email_template
        send_email_template.delay(
            template_name=template.name,
            recipient_email=test_email,
            recipient_name='Test User',
            context={'user_name': 'Test User', 'amount': '5.00', 'currency': 'USD'}
        )
        return Response({'sent_to': test_email})


# ─────────────────────────────────────────────
# CPALeadConfigViewSet
# ─────────────────────────────────────────────

class CPALeadConfigViewSet(viewsets.ModelViewSet):
    """Admin management of CPAlead integration config."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        from api.cms.models_new.extras import CPALeadConfig
        return CPALeadConfig.objects.all()

    def get_serializer_class(self):
        from api.cms.serializers import CPALeadConfigSerializer
        return CPALeadConfigSerializer

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get active CPAlead config."""
        from api.cms.services_new.CPALeadService import CPALeadService
        config = CPALeadService.get_config()
        if config:
            return Response(self.get_serializer(config).data)
        return Response({'error': 'No active config'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get CPAlead performance stats."""
        from api.cms.models_new.extras import CPALeadConfig
        config = CPALeadConfig.objects.filter(is_active=True).first()
        if not config:
            return Response({})
        return Response({
            'total_rewards_paid': float(config.total_rewards_paid),
            'total_clicks_tracked': config.total_clicks_tracked,
            'total_offers_completed': config.total_offers_completed,
        })


# ─────────────────────────────────────────────
# OfferWallViewSet — serve CPAlead offerwall
# ─────────────────────────────────────────────

class OfferWallViewSet(viewsets.ViewSet):
    """
    CPAlead Offerwall endpoints.
    GET /api/cms/offerwall/embed/    - Get embed code + config
    GET /api/cms/offerwall/offers/   - Get offers by IP/device
    POST /api/cms/offerwall/click/   - Track a click, get subid
    GET /api/cms/offerwall/balance/  - User's virtual balance
    GET /api/cms/offerwall/history/  - Virtual transaction history
    """
    authentication_classes = [JWTAuthentication]

    def get_permissions(self):
        if self.action in ('embed', 'offers'):
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def embed(self, request):
        """Get offerwall embed code and config for frontend."""
        from api.cms.services_new.CPALeadService import CPALeadService
        user = request.user if request.user.is_authenticated else None
        data = CPALeadService.generate_offerwall_embed(user=user)
        return Response(data)

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def offers(self, request):
        """Get list of CPAlead offers for display."""
        from api.cms.services_new.CPALeadService import CPALeadService
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
        device = request.query_params.get('device', 'desktop')
        country = request.query_params.get('country', '')
        limit = int(request.query_params.get('limit', 20))
        offer_types = request.query_params.getlist('types')
        offers = CPALeadService.fetch_offers(
            user_ip=ip, device=device, country=country,
            limit=limit, offer_types=offer_types or None
        )
        data = [{
            'offer_id': o.offer_id,
            'offer_type': o.offer_type,
            'title': o.title,
            'description': o.description,
            'payout_usd': float(o.payout_usd),
            'payout_virtual': float(o.payout_virtual),
            'icon_url': o.icon_url,
            'is_featured': o.is_featured,
            'is_quiz': o.is_quiz,
            'category': o.category,
            'estimated_time_minutes': o.estimated_time_minutes,
        } for o in offers]
        return Response({'offers': data, 'count': len(data)})

    @action(detail=False, methods=['post'])
    def click(self, request):
        """Track offer click and return click_id (used as subid for postback)."""
        from api.cms.services_new.CPALeadService import CPALeadService
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
        user = request.user if request.user.is_authenticated else None
        allowed, click_id = CPALeadService.track_click(
            user=user,
            offer_id=request.data.get('offer_id', ''),
            ip=ip,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            device=request.data.get('device', 'desktop'),
            click_source=request.data.get('source', 'offerwall'),
        )
        if not allowed:
            return Response({'error': click_id, 'allowed': False}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        from api.cms.models_new.cpalead import OfferWallConfig
        ow = OfferWallConfig.objects.filter(is_active=True).first()
        offer_url = ''
        if ow and ow.publisher_id:
            offer_url = (
                f"https://cpalead.com/o/{request.data.get('offer_id', '')}"
                f"?pub={ow.publisher_id}&subid={click_id}"
            )
        return Response({'allowed': True, 'click_id': click_id, 'redirect_url': offer_url})

    @action(detail=False, methods=['get'])
    def balance(self, request):
        """Get user's virtual currency balance."""
        from api.cms.services_new.CPALeadService import VirtualCurrencyService
        return Response(VirtualCurrencyService.get_balance(request.user))

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get user's virtual transaction history."""
        from api.cms.services_new.CPALeadService import VirtualCurrencyService
        limit = int(request.query_params.get('limit', 50))
        txs = VirtualCurrencyService.get_transaction_history(request.user, limit=limit)
        data = [{
            'id': t.id, 'tx_type': t.tx_type, 'amount': float(t.amount),
            'balance_after': float(t.balance_after), 'description': t.description,
            'created_at': t.created_at.isoformat(),
        } for t in txs]
        return Response({'transactions': data})


# ─────────────────────────────────────────────
# ContentLockerViewSet
# ─────────────────────────────────────────────

class ContentLockerViewSet(viewsets.ViewSet):
    """
    Content Locker endpoints.
    GET  /api/cms/lockers/{id}/check/   - Check if locked
    POST /api/cms/lockers/{id}/unlock/  - Unlock after offer
    GET  /api/cms/lockers/              - List lockers (admin)
    POST /api/cms/lockers/              - Create locker (admin)
    """
    authentication_classes = [JWTAuthentication]

    def get_permissions(self):
        if self.action in ('check',):
            return [AllowAny()]
        if self.action in ('unlock',):
            return [AllowAny()]
        return [IsAdminUser()]

    def list(self, request):
        from api.cms.models_new.cpalead import ContentLocker
        from api.cms.serializers import ContentLockerSerializer
        qs = ContentLocker.objects.filter(is_active=True).order_by('-created_at')
        return Response([{
            'id': l.id, 'name': l.name, 'locker_type': l.locker_type,
            'title': l.title, 'zero_hours_mode': l.zero_hours_mode,
            'unlock_mode': l.unlock_mode, 'total_views': l.total_views,
            'total_unlocks': l.total_unlocks, 'conversion_rate': l.conversion_rate,
        } for l in qs])

    @action(detail=True, methods=['get'], permission_classes=[AllowAny])
    def check(self, request, pk=None):
        """Check if content is locked for current user/session."""
        from api.cms.services_new.CPALeadService import CPALeadService
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key or ''
        result = CPALeadService.check_content_locked(
            locker_id=int(pk), user=user, session_key=session_key
        )
        return Response(result)

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def unlock(self, request, pk=None):
        """
        Unlock content after CPAlead offer completion.
        Usually called after postback has been received.
        """
        from api.cms.services_new.CPALeadService import CPALeadService
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key or ''
        ip = request.META.get('REMOTE_ADDR', '')
        result = CPALeadService.unlock_content(
            locker_id=int(pk),
            user=user,
            session_key=session_key,
            lead_id=request.data.get('lead_id', ''),
            ip=ip,
        )
        return Response(result)


# ─────────────────────────────────────────────
# ConversionLogViewSet (admin)
# ─────────────────────────────────────────────

class ConversionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin-only read access to CPAlead conversion logs.
    GET /api/cms/conversions/            - List all conversions
    GET /api/cms/conversions/{id}/       - Single conversion detail
    GET /api/cms/conversions/stats/      - Aggregate stats
    GET /api/cms/conversions/daily/      - Daily breakdown
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    filter_backends = [filters.OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models_new.cpalead import ConversionLog
        qs = ConversionLog.objects.select_related('user')
        if self.request.query_params.get('status'):
            qs = qs.filter(status=self.request.query_params['status'])
        if self.request.query_params.get('user_id'):
            qs = qs.filter(user_id=self.request.query_params['user_id'])
        if self.request.query_params.get('campaign_id'):
            qs = qs.filter(campaign_id=self.request.query_params['campaign_id'])
        return qs

    def get_serializer_class(self):
        from api.cms.serializers import ConversionLogSerializer
        return ConversionLogSerializer

    @action(detail=False, methods=['get'])
    def stats(self, request):
        from api.cms.models_new.cpalead import ConversionLog
        from django.db.models import Count, Sum, Avg, Q
        from django.utils import timezone
        from datetime import timedelta
        days = int(request.query_params.get('days', 30))
        cutoff = timezone.now() - timedelta(days=days)
        agg = ConversionLog.objects.filter(created_at__gte=cutoff).aggregate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='approved')),
            rejected=Count('id', filter=Q(status='rejected')),
            fraud=Count('id', filter=Q(status='fraud')),
            duplicate=Count('id', filter=Q(status='duplicate')),
            total_payout=Sum('payout_usd', filter=Q(status='approved')),
            total_virtual=Sum('virtual_amount_awarded', filter=Q(status='approved')),
            avg_payout=Avg('payout_usd', filter=Q(status='approved')),
        )
        return Response({**{k: float(v or 0) if v is not None else 0 for k, v in agg.items()},
                         'period_days': days})

    @action(detail=False, methods=['get'])
    def daily(self, request):
        from api.cms.models_new.cpalead import ConversionLog
        from django.db.models import Count, Sum, TruncDate
        from django.utils import timezone
        from datetime import timedelta
        days = int(request.query_params.get('days', 7))
        cutoff = timezone.now() - timedelta(days=days)
        data = (ConversionLog.objects
                .filter(created_at__gte=cutoff, status='approved')
                .annotate(date=TruncDate('created_at'))
                .values('date')
                .annotate(count=Count('id'), total_payout=Sum('payout_usd'))
                .order_by('-date'))
        return Response(list(data))


# ─────────────────────────────────────────────
# AuditLogViewSet (admin read-only)
# ─────────────────────────────────────────────

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only integration audit log for admin.
    GET /api/cms/audit-logs/         - List logs
    GET /api/cms/audit-logs/summary/ - Stats summary
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]
    filter_backends = [filters.OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        try:
            from api.cms.INTEGRATION_SYSTEM.integ_audit_logs import IntegrationAuditLog
        except ImportError:
            pass
        qs = IntegrationAuditLog.objects.select_related('user')
        qp = self.request.query_params
        if qp.get('action'):
            qs = qs.filter(action=qp['action'])
        if qp.get('success'):
            qs = qs.filter(success=qp['success'].lower() == 'true')
        if qp.get('source'):
            qs = qs.filter(source=qp['source'])
        return qs

    def get_serializer_class(self):
        from api.cms.serializers import IntegrationAuditLogSerializer
        return IntegrationAuditLogSerializer

    @action(detail=False, methods=['get'])
    def summary(self, request):
        try:
            from api.cms.INTEGRATION_SYSTEM.integ_audit_logs import AuditLogger
        except ImportError:
            pass
        days = int(request.query_params.get('days', 7))
        return Response(AuditLogger.get_stats(days=days))
