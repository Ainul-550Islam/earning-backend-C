# api/cms/viewsets_new/CMSOperationsViewSet.py
"""
Exposes four services that had zero API surface:
  • CMSPublishService   → publish / unpublish / bulk-publish / scheduled sweep
  • CMSCacheService     → cache invalidation and warm-up controls
  • ContentCalendarService → editorial calendar queries
  • MiscModelService    → misc helpers (rewards, blocks, comments, forms, landing pages, audit log)
"""
import logging
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

logger = logging.getLogger('api.cms.viewsets')


# ══════════════════════════════════════════════════════════════════════════════
# CMSPublishViewSet
# ══════════════════════════════════════════════════════════════════════════════

class CMSPublishViewSet(viewsets.ViewSet):
    """
    Publication workflow actions.

    POST /v3/cms-publish/publish/          — publish one object
    POST /v3/cms-publish/unpublish/        — unpublish one object
    POST /v3/cms-publish/bulk_publish/     — publish a list of IDs
    POST /v3/cms-publish/run_scheduled/    — admin: process all due scheduled items (admin only)
    """
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['post'])
    def publish(self, request):
        """
        Publish a single CMS object.
        Body: { "content_type": "page|blog|banner|popup", "object_id": 42,
                "publish_date": "2026-06-01T09:00:00Z" }   ← publish_date optional
        """
        from ..services_new.CMSPublishService import CMSPublishService
        from ..models import ContentPage, BlogPost, Banner, Popup
        content_type = request.data.get('content_type')
        object_id = request.data.get('object_id')
        publish_date_str = request.data.get('publish_date')

        MODEL_MAP = {
            'page': ContentPage, 'blog': BlogPost,
            'banner': Banner,    'popup': Popup,
        }
        model = MODEL_MAP.get(content_type)
        if not model:
            return Response({'detail': f'Unknown content_type: {content_type}'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            obj = model.objects.get(pk=object_id)
        except model.DoesNotExist:
            return Response({'detail': 'Object not found.'}, status=status.HTTP_404_NOT_FOUND)

        publish_date = None
        if publish_date_str:
            from django.utils.dateparse import parse_datetime
            publish_date = parse_datetime(publish_date_str)

        ok = CMSPublishService.publish(obj, content_type, publish_date=publish_date, user=request.user)
        return Response({'published': ok, 'object_id': object_id, 'content_type': content_type})

    @action(detail=False, methods=['post'])
    def unpublish(self, request):
        """
        Unpublish a single CMS object.
        Body: { "content_type": "page|blog|banner|popup", "object_id": 42 }
        """
        from ..services_new.CMSPublishService import CMSPublishService
        from ..models import ContentPage, BlogPost, Banner, Popup
        content_type = request.data.get('content_type')
        object_id = request.data.get('object_id')
        MODEL_MAP = {
            'page': ContentPage, 'blog': BlogPost,
            'banner': Banner,    'popup': Popup,
        }
        model = MODEL_MAP.get(content_type)
        if not model:
            return Response({'detail': f'Unknown content_type: {content_type}'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            obj = model.objects.get(pk=object_id)
        except model.DoesNotExist:
            return Response({'detail': 'Object not found.'}, status=status.HTTP_404_NOT_FOUND)
        ok = CMSPublishService.unpublish(obj, content_type, user=request.user)
        return Response({'unpublished': ok, 'object_id': object_id, 'content_type': content_type})

    @action(detail=False, methods=['post'])
    def bulk_publish(self, request):
        """
        Publish multiple objects of the same type.
        Body: { "content_type": "page", "object_ids": [1, 2, 3] }
        """
        from ..services_new.CMSPublishService import CMSPublishService
        content_type = request.data.get('content_type')
        object_ids = request.data.get('object_ids', [])
        if not object_ids:
            return Response({'detail': 'object_ids is required.'}, status=status.HTTP_400_BAD_REQUEST)
        count = CMSPublishService.bulk_publish(object_ids, content_type, user=request.user)
        return Response({'published_count': count, 'content_type': content_type})

    @action(detail=False, methods=['post'])
    def run_scheduled(self, request):
        """
        Trigger an immediate sweep of all scheduled-publish items.
        Normally handled by Celery beat; this endpoint allows manual triggering.
        """
        from ..services_new.CMSPublishService import CMSPublishService
        result = CMSPublishService.publish_scheduled_all()
        return Response(result)


# ══════════════════════════════════════════════════════════════════════════════
# CMSCacheViewSet
# ══════════════════════════════════════════════════════════════════════════════

class CMSCacheViewSet(viewsets.ViewSet):
    """
    Cache management for CMS content.

    POST /v3/cms-cache/clear_all/   — admin: wipe all CMS caches
    POST /v3/cms-cache/warm/        — admin: pre-warm blog cache
    POST /v3/cms-cache/invalidate/  — invalidate by content_type + id
    """
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['post'])
    def clear_all(self, request):
        """Wipe every CMS-managed cache key. Use with caution in production."""
        from ..services_new.CMSCacheService import CMSCacheService
        CMSCacheService.clear_all_cms_caches()
        return Response({'detail': 'All CMS caches cleared.'})

    @action(detail=False, methods=['post'])
    def warm(self, request):
        """Pre-warm the blog list cache (typically called after a deployment)."""
        from ..services_new.CMSCacheService import CMSCacheService
        CMSCacheService.warm_blog_cache()
        return Response({'detail': 'Blog cache warmed.'})

    @action(detail=False, methods=['post'])
    def invalidate(self, request):
        """
        Invalidate caches for a specific content object.
        Body: { "content_type": "blog_post|media_file|popup|menu|seo|page",
                "object_id": 42 }   ← object_id used where applicable
        """
        from ..services_new.CMSCacheService import CMSCacheService
        content_type = request.data.get('content_type', '')
        object_id = request.data.get('object_id')

        handler_map = {
            'blog_post':  lambda: CMSCacheService.invalidate_blog_post(
                type('_', (), {'pk': object_id, 'id': object_id})()
            ),
            'media_file': lambda: CMSCacheService.invalidate_media_file(
                type('_', (), {'pk': object_id, 'id': object_id})()
            ),
            'popup':  lambda: CMSCacheService.invalidate_popup(
                type('_', (), {'pk': object_id, 'id': object_id})()
            ),
            'menu':   lambda: CMSCacheService.invalidate_menu(
                type('_', (), {'pk': object_id, 'id': object_id})()
            ),
            'seo':    CMSCacheService.invalidate_seo,
            'page':   lambda: CMSCacheService.invalidate_content_page(
                type('_', (), {'pk': object_id, 'id': object_id})()
            ),
        }
        fn = handler_map.get(content_type)
        if not fn:
            return Response({'detail': f'Unknown content_type: {content_type}'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            fn()
            return Response({'detail': f'Cache invalidated for {content_type} id={object_id}.'})
        except Exception as exc:
            logger.error(f"CMSCache.invalidate failed: {exc}")
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ══════════════════════════════════════════════════════════════════════════════
# ContentCalendarViewSet
# ══════════════════════════════════════════════════════════════════════════════

class ContentCalendarViewSet(viewsets.ViewSet):
    """
    Editorial calendar API.

    GET  /v3/content-calendar/upcoming/?days=30&content_type=blog
    GET  /v3/content-calendar/month/?year=2026&month=6
    POST /v3/content-calendar/schedule/
    POST /v3/content-calendar/cancel/
    POST /v3/content-calendar/process_due/   — admin: run due schedules now
    """
    permission_classes = [permissions.IsAuthenticated]

    def _require_admin(self, request):
        if not request.user.is_staff:
            return Response({'detail': 'Admin required.'}, status=status.HTTP_403_FORBIDDEN)
        return None

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Scheduled content items due in the next N days."""
        from ..services_new.ContentCalendarService import ContentCalendarService
        days = int(request.query_params.get('days', 30))
        content_type = request.query_params.get('content_type') or None
        try:
            data = ContentCalendarService.get_upcoming(days=days, content_type=content_type)
            return Response(data)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def month(self, request):
        """
        GET /v3/content-calendar/month/?year=2026&month=6
        Returns a dict keyed by day-of-month with lists of scheduled items.
        """
        from ..services_new.ContentCalendarService import ContentCalendarService
        from django.utils import timezone
        now = timezone.now()
        year = int(request.query_params.get('year', now.year))
        month = int(request.query_params.get('month', now.month))
        try:
            data = ContentCalendarService.get_calendar(year=year, month=month)
            return Response(data)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def schedule(self, request):
        """
        Schedule content for future publication.
        Body: { "content_type": "blog", "content_id": 5, "title": "...",
                "scheduled_at": "2026-06-10T09:00:00Z" }
        """
        from ..services_new.ContentCalendarService import ContentCalendarService
        required = ['content_type', 'content_id', 'title', 'scheduled_at']
        for field in required:
            if field not in request.data:
                return Response({'detail': f'{field} is required.'},
                                status=status.HTTP_400_BAD_REQUEST)
        try:
            from django.utils.dateparse import parse_datetime
            obj = ContentCalendarService.schedule(
                content_type=request.data['content_type'],
                content_id=int(request.data['content_id']),
                title=request.data['title'],
                scheduled_at=parse_datetime(request.data['scheduled_at']),
            )
            return Response({'id': obj.id if hasattr(obj, 'id') else None,
                             'detail': 'Scheduled.'}, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def cancel(self, request):
        """
        Cancel a scheduled item.
        Body: { "schedule_id": 12 }
        """
        from ..services_new.ContentCalendarService import ContentCalendarService
        schedule_id = request.data.get('schedule_id')
        if not schedule_id:
            return Response({'detail': 'schedule_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        ok = ContentCalendarService.cancel_schedule(int(schedule_id))
        return Response({'cancelled': ok, 'schedule_id': schedule_id})

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def process_due(self, request):
        """Synchronously process all due schedules (normally done by Celery beat)."""
        from ..services_new.ContentCalendarService import ContentCalendarService
        count = ContentCalendarService.process_due_schedules()
        return Response({'processed': count})


# ══════════════════════════════════════════════════════════════════════════════
# MiscModelViewSet — BannerReward process, BlockDefinition reorder,
#                   CommentReaction, ContentPermission, FormField reorder,
#                   LandingPage publish, PermissionAuditLog
# ══════════════════════════════════════════════════════════════════════════════

class MiscModelViewSet(viewsets.ViewSet):
    """
    Misc service actions with no existing route.

    POST /v3/misc/process_reward/           — process a BannerReward
    POST /v3/misc/retry_failed_rewards/     — retry failed BannerRewards (admin)
    GET  /v3/misc/my_rewards/               — own BannerReward list
    POST /v3/misc/reorder_blocks/           — reorder BlockDefinitions (admin)
    POST /v3/misc/comment_reaction/         — toggle reaction on a comment
    GET  /v3/misc/comment_reaction_counts/  — get reaction counts
    GET  /v3/misc/check_permission/         — check content permission
    POST /v3/misc/grant_permission/         — grant permission (admin)
    POST /v3/misc/revoke_permission/        — revoke permission (admin)
    POST /v3/misc/publish_landing_page/     — publish a landing page (admin)
    GET  /v3/misc/audit_log/               — recent audit log (admin)
    """
    permission_classes = [permissions.IsAuthenticated]

    def _svc(self):
        from ..services_new.MiscModelService import (
            BannerRewardService,
            BlockDefinitionService as BlockService,
            CommentReactionService,
            ContentPermissionService, FormFieldService, LandingPageService,
            PermissionAuditService,
        )
        return (BannerRewardService, BlockService, CommentReactionService,
                ContentPermissionService, FormFieldService, LandingPageService,
                PermissionAuditService)

    @action(detail=False, methods=['post'])
    def process_reward(self, request):
        """Process a specific BannerReward. Body: { "reward_id": "<uuid>" }"""
        BannerRewardService, *_ = self._svc()
        reward_id = request.data.get('reward_id')
        if not reward_id:
            return Response({'detail': 'reward_id required.'}, status=status.HTTP_400_BAD_REQUEST)
        ok = BannerRewardService.process(str(reward_id))
        return Response({'processed': ok})

    @action(detail=False, methods=['get'])
    def my_rewards(self, request):
        """List own BannerRewards, optionally filtered by processed status."""
        BannerRewardService, *_ = self._svc()
        processed = request.query_params.get('processed')
        if processed is not None:
            processed = processed.lower() == 'true'
        items = BannerRewardService.get_user_rewards(request.user, processed=processed)
        return Response(items)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def retry_failed_rewards(self, request):
        """Retry all failed BannerRewards up to max_retries attempts."""
        BannerRewardService, *_ = self._svc()
        max_retries = int(request.data.get('max_retries', 3))
        retried = BannerRewardService.retry_failed(max_retries=max_retries)
        return Response({'retried': retried})

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def reorder_blocks(self, request):
        """
        Reorder block definitions.
        Body: { "block_type_order": ["hero", "text", "cta"] }
        """
        _, BlockService, *_ = self._svc()
        order = request.data.get('block_type_order', [])
        if not order:
            return Response({'detail': 'block_type_order required.'}, status=status.HTTP_400_BAD_REQUEST)
        ok = BlockService.reorder(order)
        return Response({'reordered': ok})

    @action(detail=False, methods=['post'])
    def comment_reaction(self, request):
        """
        Toggle a reaction on a comment.
        Body: { "comment_id": 5, "reaction": "like" }
        """
        _, _, CommentReactionService, *_ = self._svc()
        comment_id = request.data.get('comment_id')
        reaction = request.data.get('reaction', 'like')
        result = CommentReactionService.toggle(request.user, comment_id, reaction)
        return Response(result)

    @action(detail=False, methods=['get'])
    def comment_reaction_counts(self, request):
        """
        GET /v3/misc/comment_reaction_counts/?comment_id=5
        """
        _, _, CommentReactionService, *_ = self._svc()
        comment_id = request.query_params.get('comment_id')
        if not comment_id:
            return Response({'detail': 'comment_id required.'}, status=status.HTTP_400_BAD_REQUEST)
        data = CommentReactionService.get_counts(int(comment_id))
        return Response(data)

    @action(detail=False, methods=['get'])
    def check_permission(self, request):
        """
        GET /v3/misc/check_permission/?content_id=abc&permission=edit
        """
        _, _, _, ContentPermissionService, *_ = self._svc()
        content_id = request.query_params.get('content_id', '')
        permission = request.query_params.get('permission', 'view')
        has_perm = ContentPermissionService.has_permission(request.user, content_id, permission)
        return Response({'has_permission': has_perm, 'content_id': content_id, 'permission': permission})

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def grant_permission(self, request):
        """
        Body: { "content_id": "abc", "target_id": "user:5", "permissions": ["edit","publish"] }
        """
        _, _, _, ContentPermissionService, *_ = self._svc()
        ok = ContentPermissionService.grant(
            request.data.get('content_id', ''),
            request.data.get('target_id', ''),
            request.data.get('permissions', []),
        )
        return Response({'granted': ok})

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def revoke_permission(self, request):
        """Body: { "content_id": "abc", "target_id": "user:5" }"""
        _, _, _, ContentPermissionService, *_ = self._svc()
        ok = ContentPermissionService.revoke(
            request.data.get('content_id', ''),
            request.data.get('target_id', ''),
        )
        return Response({'revoked': ok})

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def publish_landing_page(self, request):
        """Body: { "landing_page_id": 3 }"""
        _, _, _, _, _, LandingPageService, _ = self._svc()
        lp_id = request.data.get('landing_page_id')
        if not lp_id:
            return Response({'detail': 'landing_page_id required.'}, status=status.HTTP_400_BAD_REQUEST)
        ok = LandingPageService.publish(int(lp_id), user=request.user)
        return Response({'published': ok})

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAdminUser])
    def audit_log(self, request):
        """
        GET /v3/misc/audit_log/?content_id=abc&limit=50
        """
        _, _, _, _, _, _, PermissionAuditService = self._svc()
        content_id = request.query_params.get('content_id', '')
        limit = int(request.query_params.get('limit', 50))
        data = PermissionAuditService.get_recent(content_id=content_id, limit=limit)
        return Response(data)
