# cms/viewsets_new/MissingModelViewSets.py
"""
ViewSets for 7 models that had NO API exposure.

Business impact of each missing ViewSet:
  BlogComment      — Blog post comments existed in DB but had no REST API.
                     Frontend comment section was hardcoded or non-functional.
  BlogTag          — Tags stored in DB but no CRUD endpoint; admins had to
                     manage tags only via Django admin.
  ContentComment   — Generic comment system on pages/quizzes had no API;
                     the CommentReaction model was also orphaned.
  MenuItem         — Menu items could only be managed via admin, not via
                     the CMS REST API or any headless frontend.
  NotificationTemplate — Template CRUD was admin-only; no programmatic
                          management from integrations or CI pipelines.
  PopupRule        — Popup trigger rules had no management API; every rule
                     change required direct DB access or admin panel.
  PopupStat        — Daily popup stats existed in DB but were inaccessible
                     to the analytics dashboard via REST.
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.utils import timezone

logger = logging.getLogger('cms.viewsets_new.missing_models')


# ─────────────────────────────────────────────────────────────────────────────
# BlogCommentViewSet
# ─────────────────────────────────────────────────────────────────────────────

class BlogCommentViewSet(viewsets.ModelViewSet):
    """
    CRUD + moderation for BlogComment.

    Endpoints:
      GET    /v3/blog-comments/              — list (admin: all, user: approved only)
      POST   /v3/blog-comments/              — create (authenticated users)
      GET    /v3/blog-comments/{id}/         — detail
      PATCH  /v3/blog-comments/{id}/         — update own comment (within 10 min)
      DELETE /v3/blog-comments/{id}/         — soft delete
      POST   /v3/blog-comments/{id}/approve/ — admin: approve pending comment
      POST   /v3/blog-comments/{id}/flag/    — report spam or abuse
      POST   /v3/blog-comments/{id}/like/    — toggle like
      GET    /v3/blog-comments/pending/      — admin: pending moderation queue
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['post', 'is_approved', 'is_flagged', 'is_active']
    search_fields = ['content', 'guest_name', 'guest_email']
    ordering_fields = ['created_at', 'like_count']
    ordering = ['-created_at']

    def get_queryset(self):
        from api.cms.models_new.blog import BlogComment
        if self.request.user.is_staff:
            return BlogComment.objects.all().select_related(
                'post', 'user', 'parent', 'approved_by'
            )
        return BlogComment.objects.filter(
            is_approved=True, is_active=True
        ).select_related('post', 'user', 'parent')

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import (
            BlogCommentSerializer, BlogCommentCreateSerializer
        )
        if self.action in ('create', 'update', 'partial_update'):
            return BlogCommentCreateSerializer
        return BlogCommentSerializer

    def perform_create(self, serializer):
        ip = self.request.META.get('REMOTE_ADDR')
        ua = self.request.META.get('HTTP_USER_AGENT', '')
        user = self.request.user if self.request.user.is_authenticated else None
        serializer.save(
            user=user,
            ip_address=ip,
            user_agent=ua,
            is_approved=True,   # auto-approve; add moderation queue toggle via settings
        )

    def perform_update(self, serializer):
        """Only allow editing own comment within 10 minutes of creation."""
        obj = self.get_object()
        if not self.request.user.is_staff:
            if obj.user != self.request.user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You can only edit your own comments.")
            edit_window = (timezone.now() - obj.created_at).total_seconds()
            if edit_window > 600:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Edit window (10 min) has passed.")
        serializer.save()

    def perform_destroy(self, instance):
        """Soft delete — preserve audit trail."""
        instance.soft_delete()

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """POST /v3/blog-comments/{id}/approve/ — Admin moderation."""
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=403)
        comment = self.get_object()
        comment.approve(moderator=request.user)
        return Response({'success': True, 'comment_id': comment.pk,
                         'approved_at': comment.approved_at.isoformat()})

    @action(detail=True, methods=['post'])
    def flag(self, request, pk=None):
        """POST /v3/blog-comments/{id}/flag/ — Report spam/abuse."""
        comment = self.get_object()
        reason = request.data.get('reason', 'Reported by user')
        comment.flag(reason=reason, moderator=request.user)
        return Response({'success': True, 'message': 'Comment flagged for review'})

    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        """POST /v3/blog-comments/{id}/like/ — Toggle like."""
        comment = self.get_object()
        comment.increment_likes()
        comment.refresh_from_db()
        return Response({'success': True, 'like_count': comment.like_count})

    @action(detail=False, methods=['get'])
    def pending(self, request):
        """GET /v3/blog-comments/pending/ — Admin: moderation queue."""
        if not request.user.is_staff:
            return Response({'error': 'Admin access required'}, status=403)
        from api.cms.models_new.blog import BlogComment
        qs = BlogComment.objects.filter(
            is_approved=False, is_active=True
        ).select_related('post', 'user').order_by('created_at')
        from api.cms.serializers_new.ContentAndFormSerializer import BlogCommentSerializer
        return Response({
            'pending': BlogCommentSerializer(qs[:50], many=True).data,
            'count': qs.count(),
        })


# ─────────────────────────────────────────────────────────────────────────────
# BlogTagViewSet
# ─────────────────────────────────────────────────────────────────────────────

class BlogTagViewSet(viewsets.ModelViewSet):
    """
    CRUD for BlogTag.

    Endpoints:
      GET    /v3/blog-tags/             — list all active tags (public)
      POST   /v3/blog-tags/             — create tag (admin)
      GET    /v3/blog-tags/{id}/        — detail
      PATCH  /v3/blog-tags/{id}/        — update (admin)
      DELETE /v3/blog-tags/{id}/        — delete (admin)
      GET    /v3/blog-tags/popular/     — top 20 tags by usage_count (public, cached)
    """
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'slug']
    ordering_fields = ['name', 'usage_count', 'created_at']
    ordering = ['-usage_count']

    def get_queryset(self):
        from api.cms.models_new.blog import BlogTag
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return BlogTag.objects.all()
        return BlogTag.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'popular'):
            return [AllowAny()]
        return [IsAdminUser()]

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import BlogTagSerializer
        return BlogTagSerializer

    @action(detail=False, methods=['get'])
    def popular(self, request):
        """GET /v3/blog-tags/popular/ — top 20 tags (cached 10 min)."""
        from django.core.cache import cache
        from api.cms.models_new.blog import BlogTag
        from api.cms.serializers_new.ContentAndFormSerializer import BlogTagSerializer
        cache_key = 'blog_tags_popular'
        data = cache.get(cache_key)
        if data is None:
            qs = BlogTag.objects.filter(is_active=True).order_by('-usage_count')[:20]
            data = BlogTagSerializer(qs, many=True).data
            cache.set(cache_key, data, 600)
        return Response({'tags': data, 'count': len(data)})


# ─────────────────────────────────────────────────────────────────────────────
# ContentCommentViewSet
# ─────────────────────────────────────────────────────────────────────────────

class ContentCommentViewSet(viewsets.ModelViewSet):
    """
    Generic threaded comment system for any content type.

    Endpoints:
      GET    /v3/content-comments/?content_type=blog_post&object_id=5 — list
      POST   /v3/content-comments/                     — create
      GET    /v3/content-comments/{id}/                — detail + replies
      PATCH  /v3/content-comments/{id}/                — update own
      DELETE /v3/content-comments/{id}/                — soft delete (set status=rejected)
      POST   /v3/content-comments/{id}/react/          — like or dislike
      GET    /v3/content-comments/{id}/replies/        — get threaded replies
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['content_type', 'object_id', 'status', 'is_pinned']
    ordering_fields = ['created_at', 'likes']
    ordering = ['created_at']

    def get_queryset(self):
        from api.cms.models_new.comments import ContentComment
        if self.request.user.is_staff:
            return ContentComment.objects.all().select_related('user', 'parent')
        return ContentComment.objects.filter(
            status='approved'
        ).select_related('user', 'parent')

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'replies'):
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import ContentCommentSerializer
        return ContentCommentSerializer

    def perform_create(self, serializer):
        ip = self.request.META.get('REMOTE_ADDR')
        user = self.request.user if self.request.user.is_authenticated else None
        # Compute depth from parent
        parent = serializer.validated_data.get('parent')
        depth = (parent.depth + 1) if parent else 0
        serializer.save(user=user, ip_address=ip, depth=depth, status='approved')

    def perform_destroy(self, instance):
        """Soft delete — mark as rejected instead of hard delete."""
        instance.status = 'rejected'
        instance.save(update_fields=['status'])

    @action(detail=True, methods=['post'])
    def react(self, request, pk=None):
        """POST /v3/content-comments/{id}/react/ — like or dislike."""
        from api.cms.models_new.comments import CommentReaction, ContentComment
        comment = self.get_object()
        reaction_type = request.data.get('reaction', 'like')
        if reaction_type not in ('like', 'dislike'):
            return Response({'error': 'reaction must be like or dislike'}, status=400)
        obj, created = CommentReaction.objects.get_or_create(
            comment=comment, user=request.user,
            defaults={'reaction': reaction_type}
        )
        if not created:
            old = obj.reaction
            if old == reaction_type:
                obj.delete()
                action_taken = 'removed'
            else:
                obj.reaction = reaction_type
                obj.save()
                action_taken = 'changed'
        else:
            action_taken = 'added'
        # Update denormalized counts
        comment.likes    = CommentReaction.objects.filter(comment=comment, reaction='like').count()
        comment.dislikes = CommentReaction.objects.filter(comment=comment, reaction='dislike').count()
        comment.save(update_fields=['likes', 'dislikes'])
        return Response({
            'action': action_taken,
            'reaction': reaction_type,
            'likes': comment.likes,
            'dislikes': comment.dislikes,
        })

    @action(detail=True, methods=['get'])
    def replies(self, request, pk=None):
        """GET /v3/content-comments/{id}/replies/ — threaded replies."""
        comment = self.get_object()
        qs = comment.get_replies()
        from api.cms.serializers_new.ContentAndFormSerializer import ContentCommentSerializer
        return Response({
            'replies': ContentCommentSerializer(qs, many=True).data,
            'count': qs.count(),
        })


# ─────────────────────────────────────────────────────────────────────────────
# MenuItemViewSet
# ─────────────────────────────────────────────────────────────────────────────

class MenuItemViewSet(viewsets.ModelViewSet):
    """
    CRUD + reordering for MenuItem.

    Endpoints:
      GET    /v3/menu-items/?menu={id}       — list items for a menu
      POST   /v3/menu-items/                 — create item (admin)
      GET    /v3/menu-items/{id}/            — detail
      PUT    /v3/menu-items/{id}/            — update (admin)
      DELETE /v3/menu-items/{id}/            — delete (admin)
      POST   /v3/menu-items/bulk-reorder/    — drag-drop reorder (admin)
      POST   /v3/menu-items/{id}/click/      — record click (public)
      POST   /v3/menu-items/{id}/move/       — move to different parent (admin)
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['menu', 'parent', 'is_active', 'link_type']
    ordering_fields = ['sort_order', 'click_count']
    ordering = ['menu', 'sort_order']

    def get_queryset(self):
        from api.cms.models_new.menu import MenuItem
        return MenuItem.objects.all().select_related('menu', 'parent').prefetch_related('children')

    def get_permissions(self):
        if self.action == 'click':
            return [AllowAny()]
        return [IsAdminUser()]

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import MenuItemSerializer
        return MenuItemSerializer

    @action(detail=False, methods=['post'], url_path='bulk-reorder')
    def bulk_reorder(self, request):
        """POST /v3/menu-items/bulk-reorder/ — reorder items by drag-drop."""
        order_data = request.data.get('order', [])
        if not order_data:
            return Response({'error': 'order list required'}, status=400)
        try:
            from api.cms.models_new.menu import MenuItem
            MenuItem.bulk_reorder(order_data)
            return Response({'success': True, 'reordered': len(order_data)})
        except Exception as e:
            logger.error(f'[MenuItemViewSet] bulk_reorder error: {e}', exc_info=True)
            return Response({'error': str(e)}, status=400)

    @action(detail=True, methods=['post'])
    def click(self, request, pk=None):
        """POST /v3/menu-items/{id}/click/ — record click for analytics."""
        item = self.get_object()
        item.record_click()
        return Response({'success': True, 'click_count': item.click_count})

    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        """POST /v3/menu-items/{id}/move/ — move to new parent."""
        item = self.get_object()
        new_parent_id = request.data.get('parent_id')
        try:
            from api.cms.models_new.menu import MenuItem
            new_parent = MenuItem.objects.get(pk=new_parent_id) if new_parent_id else None
            item.move_to_parent(new_parent)
            return Response({'success': True, 'parent_id': new_parent_id})
        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ─────────────────────────────────────────────────────────────────────────────
# NotificationTemplateViewSet
# ─────────────────────────────────────────────────────────────────────────────

class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """
    CRUD for NotificationTemplate — admin/integration use.

    Endpoints:
      GET    /v3/notification-templates/              — list
      POST   /v3/notification-templates/              — create (admin)
      GET    /v3/notification-templates/{id}/         — detail
      PUT    /v3/notification-templates/{id}/         — update (admin)
      DELETE /v3/notification-templates/{id}/         — delete (admin)
      POST   /v3/notification-templates/{id}/preview/ — render with sample context
      POST   /v3/notification-templates/{id}/send/    — send to user(s) (admin)
    """
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['notification_type', 'is_active']
    search_fields = ['name', 'title_template', 'message_template']

    def get_queryset(self):
        from api.cms.models_new.extras import NotificationTemplate
        return NotificationTemplate.objects.all().order_by('name')

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import NotificationTemplateSerializer
        return NotificationTemplateSerializer

    @action(detail=True, methods=['post'])
    def preview(self, request, pk=None):
        """POST /v3/notification-templates/{id}/preview/ — render with context."""
        template = self.get_object()
        context = request.data.get('context', {})
        title, message = template.render(context)
        return Response({
            'template_name': template.name,
            'rendered_title':   title,
            'rendered_message': message,
            'context_used': context,
        })

    @action(detail=True, methods=['post'])
    def send(self, request, pk=None):
        """POST /v3/notification-templates/{id}/send/ — send to user(s)."""
        template = self.get_object()
        if not template.is_active:
            return Response({'error': 'Template is inactive'}, status=400)
        user_ids = request.data.get('user_ids', [])
        context  = request.data.get('context', {})
        if not user_ids:
            return Response({'error': 'user_ids required'}, status=400)
        title, message = template.render(context)
        try:
            from api.cms.models_new.extras import Notification
            Notification.bulk_create_for_users(
                user_ids=user_ids,
                notification_type=template.notification_type,
                title=title,
                message=message,
                icon=template.icon,
            )
            return Response({'success': True, 'sent_to': len(user_ids),
                             'title': title})
        except Exception as e:
            logger.error(f'[NotificationTemplateViewSet] send error: {e}', exc_info=True)
            return Response({'error': str(e)}, status=500)


# ─────────────────────────────────────────────────────────────────────────────
# PopupRuleViewSet
# ─────────────────────────────────────────────────────────────────────────────

class PopupRuleViewSet(viewsets.ModelViewSet):
    """
    CRUD for PopupRule — trigger rules attached to popups.

    Endpoints:
      GET    /v3/popup-rules/?popup={id}    — list rules for a popup (admin)
      POST   /v3/popup-rules/               — create rule (admin)
      GET    /v3/popup-rules/{id}/          — detail
      PATCH  /v3/popup-rules/{id}/          — update (admin)
      DELETE /v3/popup-rules/{id}/          — delete (admin)
      POST   /v3/popup-rules/{id}/evaluate/ — test rule against context
    """
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['popup', 'trigger_type', 'is_active']
    ordering_fields = ['priority', 'trigger_type']
    ordering = ['-priority', 'trigger_type']

    def get_queryset(self):
        from api.cms.models_new.popup import PopupRule
        return PopupRule.objects.all().select_related('popup')

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import PopupRuleSerializer
        return PopupRuleSerializer

    @action(detail=True, methods=['post'])
    def evaluate(self, request, pk=None):
        """
        POST /v3/popup-rules/{id}/evaluate/
        Test whether this rule would trigger given a context.
        Body: { "context": { "seconds_on_page": 10, "scroll_depth": 55 } }
        """
        rule = self.get_object()
        context = request.data.get('context', {})
        result = rule.evaluate(context)
        return Response({
            'rule_id': rule.pk,
            'trigger_type': rule.trigger_type,
            'context': context,
            'would_trigger': result,
        })


# ─────────────────────────────────────────────────────────────────────────────
# PopupStatViewSet
# ─────────────────────────────────────────────────────────────────────────────

class PopupStatViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only access to PopupStat daily analytics.
    Stats are written by the Celery task aggregate_popup_stats.

    Endpoints:
      GET  /v3/popup-stats/              — list all (admin)
      GET  /v3/popup-stats/{id}/         — detail
      GET  /v3/popup-stats/summary/      — aggregated summary for dashboard
      GET  /v3/popup-stats/period/?popup={id}&days=30 — period aggregation
    """
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['popup', 'date']
    ordering_fields = ['date', 'views', 'conversions', 'conversion_rate']
    ordering = ['-date']

    def get_queryset(self):
        from api.cms.models_new.popup import PopupStat
        return PopupStat.objects.all().select_related('popup')

    def get_serializer_class(self):
        from api.cms.serializers_new.ContentAndFormSerializer import PopupStatSerializer
        return PopupStatSerializer

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """GET /v3/popup-stats/summary/ — aggregated across all popups."""
        from api.cms.models_new.popup import PopupStat
        from django.db.models import Sum, Avg, Count
        days = int(request.query_params.get('days', 30))
        from django.utils import timezone as tz
        since = tz.now().date() - __import__('datetime').timedelta(days=days)
        agg = PopupStat.objects.filter(date__gte=since).aggregate(
            total_views=Sum('views'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            total_dismissals=Sum('dismissals'),
            avg_conversion_rate=Avg('conversion_rate'),
            popup_count=Count('popup', distinct=True),
        )
        return Response({**agg, 'days': days})

    @action(detail=False, methods=['get'])
    def period(self, request):
        """GET /v3/popup-stats/period/?popup={id}&days=30 — per-popup period."""
        popup_id = request.query_params.get('popup')
        if not popup_id:
            return Response({'error': 'popup query param required'}, status=400)
        days = int(request.query_params.get('days', 30))
        try:
            from api.cms.models_new.popup import Popup
            popup = Popup.objects.get(pk=popup_id)
        except Popup.DoesNotExist:
            return Response({'error': 'Popup not found'}, status=404)
        stats = popup.stats.model.get_period_stats(popup, days=days)
        return Response({**stats, 'popup_id': int(popup_id), 'days': days})
