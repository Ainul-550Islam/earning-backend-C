# analytics_warehouse/views.py  (DRY refactored)
"""
Analytics Warehouse ViewSets — DRY refactored।

পুরনো pattern (প্রতিটি 20 ViewSet-এ repeated):
──────────────────────────────────────────────
    class XViewSet(ReadOnlyModelViewSet):
        permission_classes = [IsAuthenticated, IsAdminUser]  ← 20×

        def _publisher_filter(self, qs): ...                  ← 20×
        def _date_filter(self, qs): ...                       ← 20×
        def _processed_filter(self, qs): ...                  ← 20×

        def get_queryset(self):
            qs = X.objects.select_related(...)
            qs = self._publisher_filter(qs)
            qs = self._date_filter(qs)
            qs = self._processed_filter(qs)          ← 3-line chain 20×
            return qs

নতুন pattern (WarehouseViewMixin ব্যবহার):
──────────────────────────────────────────
    class XViewSet(WarehouseViewMixin, ReadOnlyModelViewSet):
        def get_queryset(self):
            return self.apply_filters(X.objects.select_related(...))  ← 1 line
"""
from django.db.models import Count, Sum, Min, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from publisher_tools.mixins import WarehouseViewMixin

from .models import (
    PublisherRecord, SiteRecord, AppRecord, AdUnitRecord,
    ImpressionRecord, ClickRecord, RevenueRecord,
    InvoiceRecord, PaymentRecord, FraudLogRecord,
    AuditLogRecord, AdPlacementRecord, ReportRecord,
    AlertRecord, WebhookLogRecord, NotificationRecord,
    SettingRecord, APIKeyLogRecord, OptimizationLogRecord,
    ABTestRecord,
)
from .serializers import (
    PublisherRecordSerializer, PublisherRecordListSerializer,
    SiteRecordSerializer, SiteRecordListSerializer,
    AppRecordSerializer, AppRecordListSerializer,
    AdUnitRecordSerializer, AdUnitRecordListSerializer,
    ImpressionRecordSerializer, ImpressionRecordListSerializer,
    ClickRecordSerializer, ClickRecordListSerializer,
    RevenueRecordSerializer, RevenueRecordListSerializer,
    InvoiceRecordSerializer, InvoiceRecordListSerializer,
    PaymentRecordSerializer, PaymentRecordListSerializer,
    FraudLogRecordSerializer, FraudLogRecordListSerializer,
    AuditLogRecordSerializer, AuditLogRecordListSerializer,
    AdPlacementRecordSerializer, AdPlacementRecordListSerializer,
    ReportRecordSerializer, ReportRecordListSerializer,
    AlertRecordSerializer, AlertRecordListSerializer,
    WebhookLogRecordSerializer, WebhookLogRecordListSerializer,
    NotificationRecordSerializer, NotificationRecordListSerializer,
    SettingRecordSerializer, SettingRecordListSerializer,
    APIKeyLogRecordSerializer, APIKeyLogRecordListSerializer,
    OptimizationLogRecordSerializer, OptimizationLogRecordListSerializer,
    ABTestRecordSerializer, ABTestRecordListSerializer,
    WarehouseIngestSerializer, WarehouseMarkProcessedSerializer,
)


# ── Shared base (single definition instead of 20 identical classes) ───────────

class _WarehouseBase(WarehouseViewMixin, ReadOnlyModelViewSet):
    """
    All warehouse ViewSets inherit from here.
    WarehouseViewMixin provides:
      - permission_classes = [IsAuthenticated, IsAdminUser]
      - apply_filters(qs)   ← replaces 3-method chain
    """
    list_serializer_class = None

    def get_serializer_class(self):
        if self.action == 'list' and self.list_serializer_class:
            return self.list_serializer_class
        return self.serializer_class

    def _str_filter(self, qs, param: str, field: str):
        """Generic string equality filter from query param."""
        val = self.request.query_params.get(param)
        if val:
            qs = qs.filter(**{field: val})
        return qs

    def _bool_filter(self, qs, param: str, field: str):
        """Generic boolean filter from query param."""
        val = self.request.query_params.get(param)
        if val is not None:
            qs = qs.filter(**{field: val.lower() == 'true'})
        return qs


# ══════════════════════════════════════════════════════════════════════════════
# 1. PublisherRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

class PublisherRecordViewSet(_WarehouseBase):
    serializer_class      = PublisherRecordSerializer
    list_serializer_class = PublisherRecordListSerializer

    def get_queryset(self):
        return self.apply_filters(
            PublisherRecord.objects.select_related('publisher', 'tenant')
        ).order_by('-record_date', '-created_at')

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        qs   = self.get_queryset()
        data = qs.aggregate(
            total=Count('id'),
            processed=Count('id', filter=Q(is_processed=True)),
            oldest_unprocessed=Min('record_date', filter=Q(is_processed=False)),
        )
        data['unprocessed']     = data['total'] - data['processed']
        data['processing_rate'] = round(data['processed'] / max(data['total'], 1) * 100, 2)
        return Response(data)


# ══════════════════════════════════════════════════════════════════════════════
# 2. SiteRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

class SiteRecordViewSet(_WarehouseBase):
    serializer_class      = SiteRecordSerializer
    list_serializer_class = SiteRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            SiteRecord.objects.select_related('publisher', 'site', 'tenant')
        )
        return self._str_filter(qs, 'site_id', 'site__site_id').order_by('-record_date', '-created_at')


# ══════════════════════════════════════════════════════════════════════════════
# 3. AppRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

class AppRecordViewSet(_WarehouseBase):
    serializer_class      = AppRecordSerializer
    list_serializer_class = AppRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            AppRecord.objects.select_related('publisher', 'app', 'tenant')
        )
        return self._str_filter(qs, 'app_id', 'app__app_id').order_by('-record_date', '-created_at')


# ══════════════════════════════════════════════════════════════════════════════
# 4. AdUnitRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

class AdUnitRecordViewSet(_WarehouseBase):
    serializer_class      = AdUnitRecordSerializer
    list_serializer_class = AdUnitRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            AdUnitRecord.objects.select_related('publisher', 'ad_unit', 'tenant')
        )
        return self._str_filter(qs, 'unit_id', 'ad_unit__unit_id').order_by('-record_date', '-created_at')


# ══════════════════════════════════════════════════════════════════════════════
# 5. ImpressionRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

class ImpressionRecordViewSet(_WarehouseBase):
    serializer_class      = ImpressionRecordSerializer
    list_serializer_class = ImpressionRecordListSerializer

    def get_queryset(self):
        return self.apply_filters(
            ImpressionRecord.objects.select_related('publisher', 'ad_unit', 'tenant')
        ).order_by('-record_date', '-created_at')

    @action(detail=False, methods=['get'], url_path='totals')
    def totals(self, request):
        qs   = self.get_queryset()
        data = qs.aggregate(
            total_impressions=Sum('impressions'),
            avg_fill_rate=Sum('fill_rate'),
            avg_viewability=Sum('viewability'),
        )
        return Response(data)


# ══════════════════════════════════════════════════════════════════════════════
# 6. ClickRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

class ClickRecordViewSet(_WarehouseBase):
    serializer_class      = ClickRecordSerializer
    list_serializer_class = ClickRecordListSerializer

    def get_queryset(self):
        return self.apply_filters(
            ClickRecord.objects.select_related('publisher', 'ad_unit', 'tenant')
        ).order_by('-record_date', '-created_at')


# ══════════════════════════════════════════════════════════════════════════════
# 7. RevenueRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

class RevenueRecordViewSet(_WarehouseBase):
    serializer_class      = RevenueRecordSerializer
    list_serializer_class = RevenueRecordListSerializer

    def get_queryset(self):
        return self.apply_filters(
            RevenueRecord.objects.select_related('publisher', 'tenant')
        ).order_by('-record_date', '-created_at')

    @action(detail=False, methods=['get'], url_path='totals')
    def totals(self, request):
        qs    = self.get_queryset()
        data  = qs.aggregate(
            total_gross=Sum('gross_revenue'),
            total_net=Sum('net_revenue'),
            record_count=Count('id'),
        )
        data['avg_ecpm'] = float(
            qs.aggregate(avg=Sum('ecpm'))['avg'] or 0
        ) / max(data['record_count'], 1)
        return Response(data)


# ══════════════════════════════════════════════════════════════════════════════
# 8-9. InvoiceRecord & PaymentRecord
# ══════════════════════════════════════════════════════════════════════════════

class InvoiceRecordViewSet(_WarehouseBase):
    serializer_class      = InvoiceRecordSerializer
    list_serializer_class = InvoiceRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            InvoiceRecord.objects.select_related('publisher', 'invoice', 'tenant')
        )
        return self._str_filter(qs, 'status', 'status').order_by('-record_date', '-created_at')


class PaymentRecordViewSet(_WarehouseBase):
    serializer_class      = PaymentRecordSerializer
    list_serializer_class = PaymentRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            PaymentRecord.objects.select_related('publisher', 'tenant')
        )
        return self._str_filter(qs, 'status', 'status').order_by('-record_date', '-created_at')


# ══════════════════════════════════════════════════════════════════════════════
# 10. FraudLogRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

class FraudLogRecordViewSet(_WarehouseBase):
    serializer_class      = FraudLogRecordSerializer
    list_serializer_class = FraudLogRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            FraudLogRecord.objects.select_related('publisher', 'tenant')
        )
        qs = self._str_filter(qs, 'fraud_type', 'fraud_type')
        return self._bool_filter(qs, 'resolved', 'resolved').order_by('-record_date', '-created_at')

    @action(detail=False, methods=['get'], url_path='unresolved')
    def unresolved(self, request):
        qs = self.get_queryset().filter(resolved=False).order_by('-fraud_score', '-record_date')
        return Response({'count': qs.count(), 'results': self.get_serializer(qs[:100], many=True).data})


# ══════════════════════════════════════════════════════════════════════════════
# 11. AuditLogRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

class AuditLogRecordViewSet(_WarehouseBase):
    serializer_class      = AuditLogRecordSerializer
    list_serializer_class = AuditLogRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            AuditLogRecord.objects.select_related('publisher', 'tenant')
        )
        action_f = self.request.query_params.get('action')
        if action_f:
            qs = qs.filter(action__icontains=action_f)
        return self._str_filter(qs, 'actor_id', 'actor_id').order_by('-record_date', '-created_at')


# ══════════════════════════════════════════════════════════════════════════════
# 12-17. Simpler ViewSets (no special actions)
# ══════════════════════════════════════════════════════════════════════════════

class AdPlacementRecordViewSet(_WarehouseBase):
    serializer_class      = AdPlacementRecordSerializer
    list_serializer_class = AdPlacementRecordListSerializer

    def get_queryset(self):
        return self.apply_filters(
            AdPlacementRecord.objects.select_related('publisher', 'placement', 'tenant')
        ).order_by('-record_date', '-created_at')


class ReportRecordViewSet(_WarehouseBase):
    serializer_class      = ReportRecordSerializer
    list_serializer_class = ReportRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            ReportRecord.objects.select_related('publisher', 'tenant')
        )
        qs = self._str_filter(qs, 'report_type', 'report_type')
        return self._str_filter(qs, 'status', 'status').order_by('-record_date', '-created_at')


class AlertRecordViewSet(_WarehouseBase):
    serializer_class      = AlertRecordSerializer
    list_serializer_class = AlertRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            AlertRecord.objects.select_related('publisher', 'tenant')
        )
        qs = self._str_filter(qs, 'severity', 'severity')
        return self._bool_filter(qs, 'resolved', 'resolved').order_by('-record_date', '-created_at')

    @action(detail=False, methods=['get'], url_path='active')
    def active(self, request):
        qs = self.get_queryset().filter(
            resolved=False, severity__in=['critical', 'error', 'warning']
        ).order_by('severity', '-record_date')
        return Response({'count': qs.count(), 'results': self.get_serializer(qs[:200], many=True).data})


class WebhookLogRecordViewSet(_WarehouseBase):
    serializer_class      = WebhookLogRecordSerializer
    list_serializer_class = WebhookLogRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            WebhookLogRecord.objects.select_related('publisher', 'tenant')
        )
        qs = self._str_filter(qs, 'event_type', 'event_type')
        return self._str_filter(qs, 'status', 'status').order_by('-record_date', '-created_at')


class NotificationRecordViewSet(_WarehouseBase):
    serializer_class      = NotificationRecordSerializer
    list_serializer_class = NotificationRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            NotificationRecord.objects.select_related('publisher', 'tenant')
        )
        return self._bool_filter(qs, 'is_read', 'is_read').order_by('-record_date', '-created_at')


class SettingRecordViewSet(_WarehouseBase):
    serializer_class      = SettingRecordSerializer
    list_serializer_class = SettingRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            SettingRecord.objects.select_related('publisher', 'tenant')
        )
        key = self.request.query_params.get('setting_key')
        if key:
            qs = qs.filter(setting_key__icontains=key)
        return qs.order_by('-record_date', '-created_at')


# ══════════════════════════════════════════════════════════════════════════════
# 18. APIKeyLogRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

class APIKeyLogRecordViewSet(_WarehouseBase):
    serializer_class      = APIKeyLogRecordSerializer
    list_serializer_class = APIKeyLogRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            APIKeyLogRecord.objects.select_related('publisher', 'tenant')
        )
        return self._str_filter(qs, 'api_key_prefix', 'api_key_prefix').order_by('-record_date', '-created_at')

    @action(detail=False, methods=['get'], url_path='top-endpoints')
    def top_endpoints(self, request):
        top = (
            self.get_queryset()
            .values('endpoint', 'method')
            .annotate(total_requests=Sum('requests_count'))
            .order_by('-total_requests')[:10]
        )
        return Response({'results': list(top)})


# ══════════════════════════════════════════════════════════════════════════════
# 19. OptimizationLogRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

class OptimizationLogRecordViewSet(_WarehouseBase):
    serializer_class      = OptimizationLogRecordSerializer
    list_serializer_class = OptimizationLogRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            OptimizationLogRecord.objects.select_related('publisher', 'tenant')
        )
        qs = self._str_filter(qs, 'optimization_type', 'optimization_type')
        return self._bool_filter(qs, 'applied', 'applied').order_by('-record_date', '-created_at')


# ══════════════════════════════════════════════════════════════════════════════
# 20. ABTestRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

class ABTestRecordViewSet(_WarehouseBase):
    serializer_class      = ABTestRecordSerializer
    list_serializer_class = ABTestRecordListSerializer

    def get_queryset(self):
        qs = self.apply_filters(
            ABTestRecord.objects.select_related('publisher', 'ab_test', 'tenant')
        )
        qs = self._str_filter(qs, 'test_type', 'test_type')
        return self._str_filter(qs, 'ab_test_id', 'ab_test__id').order_by('-record_date', '-created_at')

    @action(detail=False, methods=['get'], url_path='by-test/(?P<test_id>[^/.]+)')
    def by_test(self, request, test_id=None):
        qs = ABTestRecord.objects.filter(ab_test__id=test_id).order_by('-record_date')
        return Response({'count': qs.count(), 'results': self.get_serializer(qs, many=True).data})


# ══════════════════════════════════════════════════════════════════════════════
# 21. WarehouseHealthViewSet
# ══════════════════════════════════════════════════════════════════════════════

MODEL_MAP = {
    'publisher':        PublisherRecord,
    'site':             SiteRecord,
    'app':              AppRecord,
    'ad_unit':          AdUnitRecord,
    'impression':       ImpressionRecord,
    'click':            ClickRecord,
    'revenue':          RevenueRecord,
    'invoice':          InvoiceRecord,
    'payment':          PaymentRecord,
    'fraud_log':        FraudLogRecord,
    'audit_log':        AuditLogRecord,
    'ad_placement':     AdPlacementRecord,
    'report':           ReportRecord,
    'alert':            AlertRecord,
    'webhook_log':      WebhookLogRecord,
    'notification':     NotificationRecord,
    'setting':          SettingRecord,
    'api_key_log':      APIKeyLogRecord,
    'optimization_log': OptimizationLogRecord,
    'ab_test':          ABTestRecord,
}


class WarehouseHealthViewSet(_WarehouseBase):
    queryset = PublisherRecord.objects.none()
    serializer_class = PublisherRecordSerializer  # fallback

    def list(self, request, *args, **kwargs):
        counts_by_type, total, processed = {}, 0, 0
        for key, Model in MODEL_MAP.items():
            try:
                agg = Model.objects.aggregate(
                    total=Count('id'),
                    done=Count('id', filter=Q(is_processed=True)),
                )
                counts_by_type[key] = agg['total']
                total     += agg['total']
                processed += agg['done']
            except Exception:
                counts_by_type[key] = -1

        oldest = None
        for Model in MODEL_MAP.values():
            try:
                rec = Model.objects.filter(is_processed=False).order_by('record_date').first()
                if rec and (oldest is None or rec.record_date < oldest):
                    oldest = rec.record_date
            except Exception:
                pass

        return Response({
            'total_records':         total,
            'processed_records':     processed,
            'unprocessed_records':   total - processed,
            'processing_rate_pct':   round(processed / max(total, 1) * 100, 2),
            'oldest_unprocessed':    str(oldest) if oldest else None,
            'record_counts_by_type': counts_by_type,
            'last_updated':          timezone.now().isoformat(),
        })

    @action(detail=False, methods=['get'], url_path='counts')
    def counts(self, request):
        result = {}
        for key, Model in MODEL_MAP.items():
            try:
                result[key] = {
                    'total':       Model.objects.count(),
                    'processed':   Model.objects.filter(is_processed=True).count(),
                    'unprocessed': Model.objects.filter(is_processed=False).count(),
                }
            except Exception as e:
                result[key] = {'error': str(e)}
        return Response(result)

    @action(detail=False, methods=['post'], url_path='ingest')
    def ingest(self, request):
        s = WarehouseIngestSerializer(data=request.data)
        if not s.is_valid():
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)
        vd = s.validated_data
        if vd['record_type'] not in MODEL_MAP:
            return Response({'error': f'Unknown record_type: {vd["record_type"]}'}, status=400)
        if vd['dry_run']:
            return Response({'dry_run': True, 'would_insert': len(vd['records']), **vd})
        try:
            from publisher_tools.models import Publisher
            publisher = Publisher.objects.get(publisher_id=vd['publisher_id'])
        except Exception:
            return Response({'error': f'Publisher {vd["publisher_id"]} not found.'}, status=404)
        Model   = MODEL_MAP[vd['record_type']]
        created, errors = 0, []
        for i, rec in enumerate(vd['records']):
            try:
                obj = Model(publisher=publisher, **rec)
                obj.full_clean()
                obj.save()
                created += 1
            except Exception as e:
                errors.append({'index': i, 'error': str(e)})
        return Response({
            'record_type': vd['record_type'], 'created': created,
            'failed': len(errors), 'errors': errors[:20],
        }, status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='mark-processed')
    def mark_processed(self, request):
        s = WarehouseMarkProcessedSerializer(data=request.data)
        if not s.is_valid():
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)
        vd = s.validated_data
        if vd['record_type'] not in MODEL_MAP:
            return Response({'error': f'Unknown record_type: {vd["record_type"]}'}, status=400)
        now     = timezone.now()
        updated = MODEL_MAP[vd['record_type']].objects.filter(id__in=vd['ids']).update(
            is_processed=True, processed_at=now,
        )
        return Response({'record_type': vd['record_type'], 'requested': len(vd['ids']),
                         'updated': updated, 'processed_at': now.isoformat()})
