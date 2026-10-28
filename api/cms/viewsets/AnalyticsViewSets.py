# cms/viewsets/AnalyticsViewSets.py
"""
ViewSets for 6 analytics/engagement models that were completely
disconnected from the API layer.

GAP-01  BannerClick, BannerImpression
GAP-02  FAQFeedback
GAP-07  CommentLike, ContentShare, ContentViewLog

Business impact:
  • Banner CTR, impression heatmaps, device breakdown → no API → no dashboard
  • FAQ helpfulness scores → no API → content team was flying blind
  • Content share counts, viral tracking → no API → social analytics dead
  • Avg. content view duration → no API → UX quality measurement missing
"""
import logging
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from django.core.cache import cache
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

logger = logging.getLogger('cms.viewsets.analytics')


# ─────────────────────────────────────────────────────────────────────────────
# BannerAnalyticsViewSet  (BannerClick + BannerImpression combined)
# ─────────────────────────────────────────────────────────────────────────────

class BannerAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only analytics for banner performance.
    Writes happen via record_banner_click / record_banner_impression actions.

    GET  /api/cms/banner-analytics/              admin: all clicks
    GET  /api/cms/banner-analytics/{id}/         click detail
    POST /api/cms/banner-analytics/record-click/ public: record a click
    GET  /api/cms/banner-analytics/ctr/          admin: CTR per banner
    GET  /api/cms/banner-analytics/by-device/    admin: device breakdown
    GET  /api/cms/banner-analytics/impressions/  admin: impressions list
    GET  /api/cms/banner-analytics/funnel/       admin: impression→click funnel
    """
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['banner', 'click_type', 'device_type']
    ordering_fields = ['created_at', 'conversion_value']
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models import BannerClick
        return BannerClick.objects.all().select_related('banner', 'user')

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import BannerClickSerializer
        return BannerClickSerializer

    @action(detail=False, methods=['post'],
            permission_classes=[AllowAny], url_path='record-click')
    def record_click(self, request):
        """
        POST /api/cms/banner-analytics/record-click/
        Public endpoint — called by frontend on every banner click.
        Body: { "banner_id": 5, "click_type": "user" }
        """
        from api.cms.models import BannerClick, Banner
        banner_id  = request.data.get('banner_id')
        click_type = request.data.get('click_type', 'user')
        if not banner_id:
            return Response({'error': 'banner_id required'}, status=400)
        try:
            banner = Banner.objects.get(pk=banner_id, is_active=True)
        except Banner.DoesNotExist:
            return Response({'error': 'Banner not found'}, status=404)

        BannerClick.objects.create(
            banner      = banner,
            user        = request.user if request.user.is_authenticated else None,
            click_type  = click_type,
            ip_address  = request.META.get('REMOTE_ADDR'),
            user_agent  = request.META.get('HTTP_USER_AGENT', ''),
            referrer    = request.META.get('HTTP_REFERER', ''),
            device_type = request.data.get('device_type', ''),
        )
        # Invalidate CTR cache for this banner
        cache.delete(f'banner_ctr_{banner_id}')
        return Response({'success': True, 'banner_id': banner_id})

    @action(detail=False, methods=['post'],
            permission_classes=[AllowAny], url_path='record-impression')
    def record_impression(self, request):
        """
        POST /api/cms/banner-analytics/record-impression/
        Body: { "banner_id": 5, "impression_type": "view" }
        """
        from api.cms.models import BannerImpression, Banner
        banner_id = request.data.get('banner_id')
        if not banner_id:
            return Response({'error': 'banner_id required'}, status=400)
        try:
            banner = Banner.objects.get(pk=banner_id, is_active=True)
        except Banner.DoesNotExist:
            return Response({'error': 'Banner not found'}, status=404)

        BannerImpression.objects.create(
            banner          = banner,
            user            = request.user if request.user.is_authenticated else None,
            impression_type = request.data.get('impression_type', 'view'),
            ip_address      = request.META.get('REMOTE_ADDR'),
            user_agent      = request.META.get('HTTP_USER_AGENT', ''),
            referrer        = request.META.get('HTTP_REFERER', ''),
            device_type     = request.data.get('device_type', ''),
            session_id      = request.data.get('session_id', ''),
        )
        return Response({'success': True})

    @action(detail=False, methods=['get'])
    def ctr(self, request):
        """
        GET /api/cms/banner-analytics/ctr/?days=30
        Click-through rate per banner — cached 5 min.
        """
        from api.cms.models import BannerClick, BannerImpression, Banner
        days = int(request.query_params.get('days', 30))
        since = timezone.now() - timezone.timedelta(days=days)
        cache_key = f'banner_ctr_report_{days}'
        data = cache.get(cache_key)
        if not data:
            banners = Banner.objects.filter(is_active=True)
            data = []
            for b in banners:
                clicks      = BannerClick.objects.filter(banner=b, created_at__gte=since).count()
                impressions = BannerImpression.objects.filter(banner=b, created_at__gte=since).count()
                ctr = round(clicks / impressions * 100, 2) if impressions else 0
                data.append({
                    'banner_id':   b.pk,
                    'banner_title': b.title,
                    'clicks':       clicks,
                    'impressions':  impressions,
                    'ctr_pct':      ctr,
                    'period_days':  days,
                })
            data.sort(key=lambda x: -x['ctr_pct'])
            cache.set(cache_key, data, 300)
        return Response({'banners': data, 'count': len(data), 'days': days})

    @action(detail=False, methods=['get'], url_path='by-device')
    def by_device(self, request):
        """GET /api/cms/banner-analytics/by-device/ — click breakdown by device type."""
        from api.cms.models import BannerClick
        days  = int(request.query_params.get('days', 30))
        since = timezone.now() - timezone.timedelta(days=days)
        qs = (BannerClick.objects
              .filter(created_at__gte=since)
              .values('device_type')
              .annotate(clicks=Count('id'), revenue=Sum('conversion_value'))
              .order_by('-clicks'))
        return Response({'devices': list(qs), 'days': days})

    @action(detail=False, methods=['get'])
    def impressions(self, request):
        """GET /api/cms/banner-analytics/impressions/ — impression list."""
        from api.cms.models import BannerImpression
        days  = int(request.query_params.get('days', 7))
        since = timezone.now() - timezone.timedelta(days=days)
        qs = BannerImpression.objects.filter(
            created_at__gte=since
        ).select_related('banner', 'user').order_by('-created_at')[:500]
        from api.cms.serializers_new.ContentAndFormSerializer import BannerImpressionSerializer
        return Response({
            'impressions': BannerImpressionSerializer(qs, many=True).data,
            'count': qs.count(),
        })

    @action(detail=False, methods=['get'])
    def funnel(self, request):
        """
        GET /api/cms/banner-analytics/funnel/?banner_id=5&days=30
        Impression → Click funnel for a single banner.
        """
        from api.cms.models import BannerClick, BannerImpression
        banner_id = request.query_params.get('banner_id')
        days      = int(request.query_params.get('days', 30))
        since     = timezone.now() - timezone.timedelta(days=days)
        q = Q(created_at__gte=since)
        if banner_id:
            q &= Q(banner_id=banner_id)
        impressions  = BannerImpression.objects.filter(q).count()
        clicks       = BannerClick.objects.filter(q).count()
        unique_users = BannerClick.objects.filter(q, user__isnull=False).values('user').distinct().count()
        return Response({
            'banner_id':    banner_id,
            'impressions':  impressions,
            'clicks':       clicks,
            'unique_users': unique_users,
            'ctr_pct':      round(clicks / impressions * 100, 2) if impressions else 0,
            'days':         days,
        })


# ─────────────────────────────────────────────────────────────────────────────
# FAQFeedbackViewSet
# ─────────────────────────────────────────────────────────────────────────────

class FAQFeedbackViewSet(viewsets.ReadOnlyModelViewSet):
    """
    FAQ helpfulness feedback — public writes, admin reads.

    POST /api/cms/faq-feedback/submit/       public: vote helpful/not
    GET  /api/cms/faq-feedback/summary/      admin: per-FAQ helpfulness scores
    GET  /api/cms/faq-feedback/worst-faqs/   admin: FAQs with worst ratings
    """
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['faq', 'is_helpful']
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models import FAQFeedback
        return FAQFeedback.objects.all().select_related('faq', 'user')

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import FAQFeedbackSerializer
        return FAQFeedbackSerializer

    @action(detail=False, methods=['post'],
            permission_classes=[AllowAny], url_path='submit')
    def submit(self, request):
        """
        POST /api/cms/faq-feedback/submit/
        Public — frontend calls this when user clicks 👍/👎 on an FAQ.
        Body: { "faq_id": 3, "is_helpful": true, "feedback_text": "..." }
        Rate-limited to once per user per FAQ per 24h.
        """
        from api.cms.models import FAQFeedback, FAQ
        faq_id     = request.data.get('faq_id')
        is_helpful = request.data.get('is_helpful', True)
        if not faq_id:
            return Response({'error': 'faq_id required'}, status=400)

        try:
            faq = FAQ.objects.get(pk=faq_id, is_active=True)
        except FAQ.DoesNotExist:
            return Response({'error': 'FAQ not found'}, status=404)

        # Rate-limit: one feedback per user/IP per FAQ per 24h
        user       = request.user if request.user.is_authenticated else None
        ip_address = request.META.get('REMOTE_ADDR')
        rate_key   = f'faq_feedback_{faq_id}_{user.pk if user else ip_address}'
        if cache.get(rate_key):
            return Response({'error': 'You have already submitted feedback for this FAQ.'},
                            status=429)

        FAQFeedback.objects.create(
            faq           = faq,
            user          = user,
            is_helpful    = bool(is_helpful),
            feedback_text = request.data.get('feedback_text', ''),
            ip_address    = ip_address,
            user_agent    = request.META.get('HTTP_USER_AGENT', ''),
        )
        cache.set(rate_key, True, 86400)
        return Response({'success': True, 'message': 'Thank you for your feedback!'})

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        GET /api/cms/faq-feedback/summary/
        Per-FAQ helpfulness percentage — cached 10 min.
        """
        from api.cms.models import FAQFeedback
        cache_key = 'faq_feedback_summary'
        data = cache.get(cache_key)
        if not data:
            qs = (FAQFeedback.objects
                  .values('faq', 'faq__question')
                  .annotate(
                      total=Count('id'),
                      helpful=Count('id', filter=Q(is_helpful=True)),
                  )
                  .order_by('-total'))
            data = [
                {
                    'faq_id':       row['faq'],
                    'question':     row['faq__question'],
                    'total':        row['total'],
                    'helpful':      row['helpful'],
                    'helpful_pct':  round(row['helpful'] / row['total'] * 100, 1) if row['total'] else 0,
                }
                for row in qs
            ]
            cache.set(cache_key, data, 600)
        return Response({'faqs': data, 'count': len(data)})

    @action(detail=False, methods=['get'], url_path='worst-faqs')
    def worst_faqs(self, request):
        """
        GET /api/cms/faq-feedback/worst-faqs/?limit=10
        FAQs with <50% helpful rate + at least 5 votes — content team action items.
        """
        from api.cms.models import FAQFeedback
        limit = int(request.query_params.get('limit', 10))
        qs = (FAQFeedback.objects
              .values('faq', 'faq__question', 'faq__slug')
              .annotate(
                  total=Count('id'),
                  helpful=Count('id', filter=Q(is_helpful=True)),
              )
              .filter(total__gte=5)
              .order_by('helpful'))
        worst = [
            {
                'faq_id':      r['faq'],
                'question':    r['faq__question'],
                'slug':        r['faq__slug'],
                'total_votes': r['total'],
                'helpful_pct': round(r['helpful'] / r['total'] * 100, 1),
            }
            for r in qs
            if r['helpful'] / r['total'] < 0.5
        ][:limit]
        return Response({'worst_faqs': worst, 'count': len(worst)})


# ─────────────────────────────────────────────────────────────────────────────
# ContentEngagementViewSet  (ContentShare + ContentViewLog + CommentLike)
# ─────────────────────────────────────────────────────────────────────────────

class ContentEngagementViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Combined engagement analytics — views, shares, likes.

    POST /api/cms/engagement/record-view/   public
    POST /api/cms/engagement/record-share/  public
    POST /api/cms/engagement/record-like/   authenticated
    GET  /api/cms/engagement/summary/       admin: per-content summary
    GET  /api/cms/engagement/top-content/   admin: top performing content
    GET  /api/cms/engagement/sharing-platforms/ admin: share platform breakdown
    GET  /api/cms/engagement/avg-duration/  admin: avg view duration by content
    """
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models import ContentViewLog
        return ContentViewLog.objects.all().select_related('content', 'user')

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import ContentViewLogSerializer
        return ContentViewLogSerializer

    @action(detail=False, methods=['post'],
            permission_classes=[AllowAny], url_path='record-view')
    def record_view(self, request):
        """
        POST /api/cms/engagement/record-view/
        Body: { "content_id": 7, "view_duration": 45, "is_completed": false }
        """
        from api.cms.models import ContentViewLog, ContentPage
        content_id = request.data.get('content_id')
        if not content_id:
            return Response({'error': 'content_id required'}, status=400)
        try:
            content = ContentPage.objects.get(pk=content_id, is_active=True)
        except ContentPage.DoesNotExist:
            return Response({'error': 'Content not found'}, status=404)

        ContentViewLog.objects.create(
            content       = content,
            user          = request.user if request.user.is_authenticated else None,
            view_duration = int(request.data.get('view_duration', 0)),
            is_completed  = bool(request.data.get('is_completed', False)),
            ip_address    = request.META.get('REMOTE_ADDR'),
            user_agent    = request.META.get('HTTP_USER_AGENT', ''),
            referrer      = request.META.get('HTTP_REFERER', ''),
            session_id    = request.data.get('session_id', ''),
            device_type   = request.data.get('device_type', ''),
        )
        # Increment view counter on the content object
        ContentPage.objects.filter(pk=content_id).update(
            views_count=ContentPage.objects.filter(pk=content_id).values('views_count')[0]['views_count'] + 1
            if ContentPage.objects.filter(pk=content_id).exists() else 1
        )
        return Response({'success': True})

    @action(detail=False, methods=['post'],
            permission_classes=[AllowAny], url_path='record-share')
    def record_share(self, request):
        """
        POST /api/cms/engagement/record-share/
        Body: { "content_id": 7, "share_platform": "whatsapp" }
        """
        from api.cms.models import ContentShare, ContentPage
        content_id = request.data.get('content_id')
        platform   = request.data.get('share_platform', 'other')
        if not content_id:
            return Response({'error': 'content_id required'}, status=400)
        try:
            content = ContentPage.objects.get(pk=content_id, is_active=True)
        except ContentPage.DoesNotExist:
            return Response({'error': 'Content not found'}, status=404)
        from api.cms.models import ContentShare
        ContentShare.objects.create(
            content          = content,
            user             = request.user if request.user.is_authenticated else None,
            share_platform   = platform,
            ip_address       = request.META.get('REMOTE_ADDR'),
            user_agent       = request.META.get('HTTP_USER_AGENT', ''),
        )
        return Response({'success': True, 'platform': platform})

    @action(detail=False, methods=['post'],
            permission_classes=[IsAuthenticated], url_path='record-like')
    def record_like(self, request):
        """
        POST /api/cms/engagement/record-like/
        Body: { "comment_id": 12 }
        Toggles a CommentLike (like → unlike → like).
        """
        from api.cms.models import CommentLike
        comment_id = request.data.get('comment_id')
        if not comment_id:
            return Response({'error': 'comment_id required'}, status=400)
        try:
            like = CommentLike.objects.get(comment_id=comment_id, user=request.user)
            like.delete()
            return Response({'success': True, 'action': 'unliked'})
        except CommentLike.DoesNotExist:
            CommentLike.objects.create(comment_id=comment_id, user=request.user)
            return Response({'success': True, 'action': 'liked'})

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """GET /api/cms/engagement/summary/?content_id=7&days=30"""
        from api.cms.models import ContentViewLog, ContentShare
        days       = int(request.query_params.get('days', 30))
        content_id = request.query_params.get('content_id')
        since      = timezone.now() - timezone.timedelta(days=days)
        q          = Q(created_at__gte=since)
        if content_id:
            q &= Q(content_id=content_id)
        views_qs   = ContentViewLog.objects.filter(q)
        shares_qs  = ContentShare.objects.filter(q)
        return Response({
            'total_views':        views_qs.count(),
            'completed_views':    views_qs.filter(is_completed=True).count(),
            'avg_duration_secs':  round(views_qs.aggregate(a=Avg('view_duration'))['a'] or 0, 1),
            'total_shares':       shares_qs.count(),
            'unique_viewers':     views_qs.values('user').filter(user__isnull=False).distinct().count(),
            'days':               days,
            'content_id':         content_id,
        })

    @action(detail=False, methods=['get'], url_path='top-content')
    def top_content(self, request):
        """GET /api/cms/engagement/top-content/?metric=views&limit=10"""
        from api.cms.models import ContentViewLog
        metric = request.query_params.get('metric', 'views')
        limit  = int(request.query_params.get('limit', 10))
        days   = int(request.query_params.get('days', 30))
        since  = timezone.now() - timezone.timedelta(days=days)
        qs = (ContentViewLog.objects
              .filter(created_at__gte=since)
              .values('content', 'content__title', 'content__slug')
              .annotate(views=Count('id'), avg_duration=Avg('view_duration'))
              .order_by('-views')[:limit])
        return Response({'top_content': list(qs), 'metric': metric, 'days': days})

    @action(detail=False, methods=['get'], url_path='sharing-platforms')
    def sharing_platforms(self, request):
        """GET /api/cms/engagement/sharing-platforms/?days=30"""
        from api.cms.models import ContentShare
        days  = int(request.query_params.get('days', 30))
        since = timezone.now() - timezone.timedelta(days=days)
        qs = (ContentShare.objects
              .filter(created_at__gte=since)
              .values('share_platform')
              .annotate(shares=Count('id'))
              .order_by('-shares'))
        return Response({'platforms': list(qs), 'days': days})

    @action(detail=False, methods=['get'], url_path='avg-duration')
    def avg_duration(self, request):
        """GET /api/cms/engagement/avg-duration/ — average view duration by content type."""
        from api.cms.models import ContentViewLog
        days  = int(request.query_params.get('days', 30))
        since = timezone.now() - timezone.timedelta(days=days)
        qs = (ContentViewLog.objects
              .filter(created_at__gte=since)
              .values('content', 'content__title', 'content__content_type')
              .annotate(
                  avg_secs=Avg('view_duration'),
                  total_views=Count('id'),
                  completion_rate=Avg('is_completed'),
              )
              .order_by('-avg_secs')[:50])
        data = [
            {**row, 'completion_pct': round(row['completion_rate']*100, 1)}
            for row in qs
        ]
        return Response({'content': data, 'days': days})
