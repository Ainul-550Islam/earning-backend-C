# api/referral/mixins.py
# DRF View mixins for referral viewsets
# Shared behaviour across multiple viewsets without code duplication
# ============================================================

import logging
from decimal import Decimal
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django.utils import timezone

logger = logging.getLogger(__name__)


class ReferralOwnerMixin:
    """
    Mixin: restricts queryset to records owned by request.user.
    Add to any ViewSet where users should only see their own data.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return qs
        return qs.filter(user=user)


class TenantFilterMixin:
    """
    Mixin: filters queryset by request.user.tenant if set.
    Ensures multi-tenant data isolation.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request.user, 'tenant', None)
        if tenant:
            return qs.filter(tenant=tenant)
        return qs


class ReferralPaginationMixin:
    """
    Mixin: provides standard pagination for referral list endpoints.
    All list endpoints use the same page_size=20 default.
    """
    from api.referral.pagination import ReferralPagination
    pagination_class = ReferralPagination


class ExportMixin:
    """
    Mixin: adds CSV/JSON export action to any ViewSet.
    Usage: inherit in AdminReferralViewSet or any list ViewSet.
    """

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request, *args, **kwargs):
        fmt = request.query_params.get('format', 'csv')
        try:
            from api.referral.services.ReferralExportService import ReferralExportService
            qs = self.get_queryset()
            if fmt == 'csv':
                csv_data = ReferralExportService.export_queryset_to_csv(qs)
                from django.http import HttpResponse
                response = HttpResponse(csv_data, content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename="referral_export.csv"'
                return response
            else:
                data = list(qs.values())
                return Response({'count': len(data), 'results': data})
        except Exception as e:
            return Response({'error': str(e)}, status=500)


class StatsActionMixin:
    """
    Mixin: adds /stats/ action to ViewSets.
    Returns aggregated stats for the queryset.
    """

    @action(detail=False, methods=['get'])
    def stats(self, request, *args, **kwargs):
        from django.db.models import Count, Sum, Avg
        qs = self.get_queryset()
        try:
            stats = qs.aggregate(
                total=Count('id'),
                total_amount=Sum('amount'),
                avg_amount=Avg('amount'),
            )
            stats = {k: (float(v) if isinstance(v, Decimal) else v)
                     for k, v in stats.items() if v is not None}
            return Response(stats)
        except Exception as e:
            return Response({'total': qs.count(), 'error': str(e)})


class SoftDeleteMixin:
    """
    Mixin: overrides destroy() to perform soft-delete.
    Sets is_deleted=True instead of hard DELETE.
    """

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if hasattr(instance, 'soft_delete'):
            instance.soft_delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        return super().destroy(request, *args, **kwargs)


class AdminOnlyMixin:
    """
    Mixin: restricts entire ViewSet to is_staff users only.
    Returns 403 for non-staff requests.
    """

    def get_permissions(self):
        from api.referral.permissions import IsReferralAdmin
        return [IsReferralAdmin()]


class CacheResponseMixin:
    """
    Mixin: caches list/retrieve responses in Django cache.
    Useful for public endpoints like leaderboard.
    """
    cache_timeout = 60  # seconds

    def list(self, request, *args, **kwargs):
        from django.core.cache import cache
        cache_key = f'referral_view:{self.__class__.__name__}:list:{request.path}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            cache.set(cache_key, response.data, timeout=self.cache_timeout)
        return response


class BulkCreateMixin:
    """
    Mixin: adds bulk_create endpoint to ViewSets.
    POST /endpoint/bulk/ with a list of objects.
    """

    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk_create(self, request, *args, **kwargs):
        many_serializer = self.get_serializer(
            data=request.data, many=True
        )
        if many_serializer.is_valid():
            instances = many_serializer.save()
            return Response(
                self.get_serializer(instances, many=True).data,
                status=status.HTTP_201_CREATED
            )
        return Response(many_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DateRangeFilterMixin:
    """
    Mixin: adds from_date / to_date query param filtering on created_at.
    """

    def filter_queryset(self, queryset):
        qs = super().filter_queryset(queryset)
        from_date = self.request.query_params.get('from_date')
        to_date   = self.request.query_params.get('to_date')
        if from_date:
            qs = qs.filter(created_at__date__gte=from_date)
        if to_date:
            qs = qs.filter(created_at__date__lte=to_date)
        return qs


class AuditLogMixin:
    """
    Mixin: writes to audit log on create/update/destroy actions.
    """

    def perform_create(self, serializer):
        instance = serializer.save()
        self._audit('CREATE', instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self._audit('UPDATE', instance)

    def perform_destroy(self, instance):
        self._audit('DELETE', instance)
        instance.delete()

    def _audit(self, action: str, instance) -> None:
        try:
            from api.referral.INTEGRATION_SYSTEM.integ_audit_logs import ReferralAuditLogger
            ReferralAuditLogger.log(
                action=f'REFERRAL_{action}_{instance.__class__.__name__.upper()}',
                user=self.request.user,
                data={'id': instance.pk, 'repr': str(instance)},
            )
        except Exception:
            pass