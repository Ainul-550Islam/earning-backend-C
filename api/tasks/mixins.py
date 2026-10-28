"""
api/tasks/mixins.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Reusable DRF view mixins, serializer mixins, and
model mixins for the task system.
"""

import logging
from django.db import models
from decimal import Decimal
from django.utils import timezone
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW MIXINS
# ══════════════════════════════════════════════════════════════════════════════

class StaffOnlyMixin:
    """
    Mixin that restricts viewset access to staff users only.
    Apply to any ViewSet that should only be accessible to admins.
    """
    def get_permissions(self):
        from rest_framework.permissions import IsAdminUser
        return [IsAdminUser()]

    def permission_denied(self, request, message=None, code=None):
        return Response(
            {'error': 'Staff access required.', 'code': 'staff_only'},
            status=status.HTTP_403_FORBIDDEN,
        )


class TaskOwnershipMixin:
    """
    Mixin that filters queryset to only include objects belonging
    to the authenticated user. Use with UserTaskCompletion viewsets.
    """
    user_field = 'user'

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff:
            return qs
        return qs.filter(**{self.user_field: self.request.user})


class BulkActionMixin:
    """
    Mixin that adds bulk_activate and bulk_deactivate actions
    to a ViewSet. Expects the model to have an is_active field.
    """

    @action(detail=False, methods=['post'], url_path='bulk-activate')
    def bulk_activate(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided.'}, status=400)
        count = self.get_queryset().filter(pk__in=ids).update(is_active=True)
        return Response({'activated': count, 'ids': ids})

    @action(detail=False, methods=['post'], url_path='bulk-deactivate')
    def bulk_deactivate(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided.'}, status=400)
        count = self.get_queryset().filter(pk__in=ids).update(is_active=False)
        return Response({'deactivated': count, 'ids': ids})

    @action(detail=False, methods=['post'], url_path='bulk-delete')
    def bulk_delete(self, request):
        if not request.user.is_staff:
            return Response({'error': 'Staff only.'}, status=403)
        ids   = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'No IDs provided.'}, status=400)
        deleted, _ = self.get_queryset().filter(pk__in=ids).delete()
        return Response({'deleted': deleted})


class CachedRetrieveMixin:
    """
    Mixin that caches the retrieve() response in Redis.
    Override cache_ttl to customize TTL.
    """
    cache_ttl    = 300   # 5 minutes
    cache_prefix = 'view_cache'

    def retrieve(self, request, *args, **kwargs):
        pk  = kwargs.get('pk', '')
        key = f'{self.cache_prefix}_{self.__class__.__name__}_{pk}'
        cached = cache.get(key)
        if cached is not None:
            return Response(cached)
        response = super().retrieve(request, *args, **kwargs)
        if response.status_code == 200:
            cache.set(key, response.data, timeout=self.cache_ttl)
        return response

    def _invalidate_cache(self, pk):
        key = f'{self.cache_prefix}_{self.__class__.__name__}_{pk}'
        cache.delete(key)


class PlatformStatsActionMixin:
    """
    Adds a /stats/ action endpoint to any ViewSet that exposes
    platform-wide stats from the DataBridge.
    """

    @action(detail=False, methods=['get'])
    def stats(self, request):
        try:
            from api.tasks.integration.data_bridge import DataBridge
            data = DataBridge.get_platform_snapshot()
            return Response(data)
        except Exception as e:
            logger.error(f"[STATS] {e}")
            return Response({'error': str(e)}, status=500)


class ExportMixin:
    """
    Adds CSV/JSON export actions to a ViewSet.
    Delegates to export_tasks for async large exports.
    """

    @action(detail=False, methods=['post'], url_path='export')
    def export(self, request):
        export_format = request.data.get('format', 'csv')
        date_from     = request.data.get('date_from')
        date_to       = request.data.get('date_to')
        email         = request.data.get('email', request.user.email)

        from celery import current_app
        current_app.send_task(
            'tasks.export_tasks.export_task_history',
            kwargs={
                'user_id':       request.user.pk,
                'format':        export_format,
                'date_from':     date_from,
                'date_to':       date_to,
                'email':         email,
            },
            queue='reports',
        )
        return Response({
            'status':  'queued',
            'message': f'Export queued. You will receive an email at {email}.',
        })


class HealthCheckMixin:
    """
    Adds a /health/ endpoint to a ViewSet for service health monitoring.
    """

    @action(detail=False, methods=['get'])
    def health(self, request):
        from django.db import connection
        import time

        start = time.monotonic()
        try:
            with connection.cursor() as c:
                c.execute('SELECT 1')
            db_ok = True
        except Exception:
            db_ok = False

        try:
            cache.set('_health', 1, 5)
            cache_ok = cache.get('_health') == 1
        except Exception:
            cache_ok = False

        elapsed = time.monotonic() - start

        return Response({
            'status':      'healthy' if (db_ok and cache_ok) else 'degraded',
            'database':    'ok' if db_ok else 'error',
            'cache':       'ok' if cache_ok else 'error',
            'latency_ms':  round(elapsed * 1000, 2),
            'timestamp':   timezone.now().isoformat(),
        }, status=200 if (db_ok and cache_ok) else 503)


class RateLimitedActionMixin:
    """
    Applies rate limiting to specific ViewSet actions.
    Override rate_limit_config to customize per-action limits.
    """
    rate_limit_config = {
        # action_name: (limit, window_seconds)
        'create':  (100,  3600),
        'update':  (50,   3600),
        'destroy': (20,   3600),
    }

    def _check_rate_limit(self, action_name: str) -> bool:
        """Returns True if rate limit is OK, False if exceeded."""
        config = self.rate_limit_config.get(action_name)
        if not config:
            return True
        limit, window = config
        user_id = self.request.user.pk
        key     = f'rl_{self.__class__.__name__}_{action_name}_{user_id}'
        count   = cache.get(key, 0)
        if count >= limit:
            return False
        cache.set(key, count + 1, timeout=window)
        return True

    def create(self, request, *args, **kwargs):
        if not self._check_rate_limit('create'):
            return Response(
                {'error': 'Rate limit exceeded.', 'code': 'rate_limited'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return super().create(request, *args, **kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# SERIALIZER MIXINS
# ══════════════════════════════════════════════════════════════════════════════

class ReadOnlyFieldsMixin:
    """
    Serializer mixin that makes all fields read-only after creation.
    Useful for immutable records like AdminLedger.
    """
    def get_fields(self):
        fields = super().get_fields()
        if self.context.get('request') and self.context['request'].method != 'POST':
            for field in fields.values():
                field.read_only = True
        return fields


class DynamicFieldsMixin:
    """
    Serializer mixin that allows the caller to specify which fields
    to include/exclude via query params: ?fields=id,name or ?exclude=created_at

    Usage:
        class TaskSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
            ...
    """
    def __init__(self, *args, **kwargs):
        fields  = kwargs.pop('fields',  None)
        exclude = kwargs.pop('exclude', None)
        super().__init__(*args, **kwargs)

        if fields is not None:
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)

        if exclude is not None:
            for field_name in exclude:
                self.fields.pop(field_name, None)


class DecimalAsStringMixin:
    """
    Serializer mixin that serializes all Decimal fields as strings
    to prevent floating-point precision issues in JSON.
    """
    def to_representation(self, instance):
        rep = super().to_representation(instance)
        for key, value in rep.items():
            if isinstance(value, Decimal):
                rep[key] = str(value)
        return rep


class UserContextMixin:
    """
    Serializer mixin that injects the current user into context
    and provides helper methods.
    """
    @property
    def current_user(self):
        request = self.context.get('request')
        return getattr(request, 'user', None)

    @property
    def is_staff(self) -> bool:
        user = self.current_user
        return user and user.is_staff

    def get_user_id(self):
        user = self.current_user
        return getattr(user, 'pk', None)


# ══════════════════════════════════════════════════════════════════════════════
# MODEL MIXINS
# ══════════════════════════════════════════════════════════════════════════════

class CacheClearMixin:
    """
    Model mixin that clears related cache keys on save/delete.
    Override cache_keys_to_clear() to specify which keys.
    """
    def cache_keys_to_clear(self) -> list:
        return []

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        for key in self.cache_keys_to_clear():
            cache.delete(key)

    def delete(self, *args, **kwargs):
        for key in self.cache_keys_to_clear():
            cache.delete(key)
        super().delete(*args, **kwargs)


class SlugMixin(models.Model):
    """
    Model mixin that auto-generates a URL slug from the name field.
    """
    slug = models.SlugField(max_length=200, unique=True, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug and hasattr(self, 'name'):
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            slug      = base_slug
            counter   = 1
            while self.__class__.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug    = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class NotifiableMixin:
    """
    Model mixin for objects that can trigger notifications.
    Provides a convenience method to dispatch notifications.
    """
    def notify_user(self, user_id: int, title: str, message: str,
                    notification_type: str = 'info', **kwargs):
        try:
            from api.tasks.notification_tasks import dispatch_in_app_notification
            dispatch_in_app_notification.apply_async(kwargs={
                'user_id':           user_id,
                'title':             title,
                'message':           message,
                'notification_type': notification_type,
                **kwargs,
            })
        except Exception as e:
            logger.debug(f"[NOTIFY] {e}")


class FraudCheckMixin:
    """
    Mixin for models/services that need fraud score checking.
    """
    @staticmethod
    def get_fraud_score(user_id: int) -> int:
        return int(cache.get(f'fraud_score_{user_id}', 0))

    @staticmethod
    def is_high_risk(user_id: int, threshold: int = 60) -> bool:
        return FraudCheckMixin.get_fraud_score(user_id) >= threshold

    @staticmethod
    def increment_fraud_score(user_id: int, increment: int = 10,
                              reason: str = '') -> int:
        key   = f'fraud_score_{user_id}'
        score = min(cache.get(key, 0) + increment, 100)
        cache.set(key, score, timeout=86400)
        return score


__all__ = [
    # View mixins
    'StaffOnlyMixin', 'TaskOwnershipMixin', 'BulkActionMixin',
    'CachedRetrieveMixin', 'PlatformStatsActionMixin', 'ExportMixin',
    'HealthCheckMixin', 'RateLimitedActionMixin',
    # Serializer mixins
    'ReadOnlyFieldsMixin', 'DynamicFieldsMixin', 'DecimalAsStringMixin',
    'UserContextMixin',
    # Model mixins
    'CacheClearMixin', 'SlugMixin', 'NotifiableMixin', 'FraudCheckMixin',
]
