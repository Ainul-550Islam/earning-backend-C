# api/admin_panel/mixins.py
"""
Mixins for admin_panel ViewSets, Serializers, Models.
"এক কাজের জন্য একটাই মালিক" — all reusable logic lives here.
"""
from __future__ import annotations
from typing import Any, Dict, Optional
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


# ==================== VIEWSET MIXINS ====================

class AdminResponseMixin:
    """Standardised response format for all admin viewsets."""

    def success(self, data=None, message='', status_code=200, meta=None) -> Response:
        return Response({
            'success': True,
            'message': message,
            'data': data,
            'meta': meta or {},
            'timestamp': timezone.now().isoformat(),
        }, status=status_code)

    def error(self, message='', errors=None, status_code=400) -> Response:
        return Response({
            'success': False,
            'message': message,
            'errors': errors or [],
            'timestamp': timezone.now().isoformat(),
        }, status=status_code)

    def paginated(self, queryset, serializer_class, request) -> Response:
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = serializer_class(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        serializer = serializer_class(queryset, many=True, context={'request': request})
        return Response(serializer.data)


class CacheableMixin:
    """Cache ViewSet responses automatically."""
    CACHE_TTL = 60
    CACHE_PREFIX = 'admin_panel'

    def _cache_key(self, suffix: str = '') -> str:
        return f"{self.CACHE_PREFIX}:{self.__class__.__name__.lower()}:{suffix}"

    def get_cached(self, key: str, fallback=None):
        return cache.get(self._cache_key(key), fallback)

    def set_cached(self, key: str, data, ttl: int = None):
        cache.set(self._cache_key(key), data, ttl or self.CACHE_TTL)

    def invalidate_cache(self, key: str = ''):
        cache.delete(self._cache_key(key))


class ActivityLogMixin:
    """Auto-log admin actions to AdminActivity."""

    def log_action(self, actor, action: str, model_name: str = '',
                   object_id: str = '', changes: dict = None, status: str = 'success'):
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(
                actor=actor, action=action,
                model_name=model_name, object_id=object_id,
                changes=changes or {}, status=status,
                ip=self._get_ip(),
            )
        except Exception as e:
            logger.debug(f"[ActivityLogMixin] Log failed: {e}")

    def _get_ip(self) -> str:
        try:
            request = getattr(self, 'request', None)
            if request:
                x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
                return x_forwarded.split(',')[0].strip() if x_forwarded else request.META.get('REMOTE_ADDR', '')
        except Exception:
            pass
        return ''


class BulkActionMixin:
    """Bulk create/update/delete for admin viewsets."""

    def bulk_update_field(self, queryset, field: str, value: Any) -> int:
        return queryset.update(**{field: value})

    def bulk_soft_delete(self, queryset) -> int:
        return queryset.update(is_deleted=True, deleted_at=timezone.now())

    def bulk_activate(self, queryset) -> int:
        return queryset.update(is_active=True)

    def bulk_deactivate(self, queryset) -> int:
        return queryset.update(is_active=False)


class FilterMixin:
    """Common filtering helpers for admin querysets."""

    def apply_date_range(self, queryset, field: str, request):
        start = request.query_params.get('start_date')
        end   = request.query_params.get('end_date')
        if start:
            queryset = queryset.filter(**{f'{field}__date__gte': start})
        if end:
            queryset = queryset.filter(**{f'{field}__date__lte': end})
        return queryset

    def apply_search(self, queryset, search_fields: list, request):
        q = request.query_params.get('q', '').strip()
        if not q or len(q) < 2:
            return queryset
        from django.db.models import Q
        query = Q()
        for field in search_fields:
            query |= Q(**{f'{field}__icontains': q})
        return queryset.filter(query)

    def apply_ordering(self, queryset, allowed_fields: list, request, default: str = '-created_at'):
        order = request.query_params.get('order_by', default)
        field = order.lstrip('-')
        if field in allowed_fields:
            return queryset.order_by(order)
        return queryset.order_by(default)


class ExportMixin:
    """Export queryset to CSV/JSON from any admin viewset."""

    def to_csv(self, queryset, fields: list, filename: str = 'export.csv') -> Response:
        import csv, io
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in queryset.values(*fields):
            writer.writerow({k: str(v) for k, v in row.items()})
        from django.http import HttpResponse
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    def to_json(self, queryset, fields: list) -> Response:
        import json
        data = list(queryset.values(*fields))
        return Response({'data': data, 'count': len(data)})


# ==================== MODEL MIXINS ====================

class AdminModelMixin:
    """Helper methods for all admin_panel models."""

    def get_absolute_url(self) -> str:
        return f'/admin/admin_panel/{self.__class__.__name__.lower()}/{self.pk}/'

    @classmethod
    def get_or_none(cls, **kwargs):
        try:
            return cls.objects.get(**kwargs)
        except cls.DoesNotExist:
            return None

    @classmethod
    def count_active(cls) -> int:
        return cls.objects.filter(is_active=True).count()


# ==================== SERIALIZER MIXINS ====================

class ReadOnlyFieldsMixin:
    """Mark specified fields as read-only in serializers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        read_only_fields = getattr(self.Meta, 'read_only_fields', [])
        for field in read_only_fields:
            if field in self.fields:
                self.fields[field].read_only = True


class DynamicFieldsMixin:
    """Allow client to request specific fields via ?fields=id,name,status."""

    def __init__(self, *args, **kwargs):
        fields = kwargs.pop('fields', None)
        super().__init__(*args, **kwargs)
        if fields:
            allowed = set(fields.split(','))
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)


class TimestampMixin:
    """Add formatted timestamps to serializer output."""

    def get_created_at(self, obj):
        return obj.created_at.strftime('%Y-%m-%d %H:%M:%S') if obj.created_at else None

    def get_updated_at(self, obj):
        return obj.updated_at.strftime('%Y-%m-%d %H:%M:%S') if obj.updated_at else None