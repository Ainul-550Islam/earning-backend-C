# =============================================================================
# fraud_detection/views_business.py
# =============================================================================
"""
Business-layer API views wiring all previously floating modules:

  1.  Data Export         — CSV / Excel / JSON / PDF / XML downloads
  2.  Compliance (AML)    — SAR, CTR, monthly audit reports
  3.  Webhook Push        — fraud event → external webhook delivery
  4.  Referral Fraud      — detect / report referral abuse
  5.  Chargeback          — dispute CRUD + stats
  6.  Conversion Cap      — per-offer / per-user cap enforcement
  7.  Advertiser Portal   — publisher + advertiser fraud dashboards
  8.  Pre-payout Screen   — screen payouts before release
  9.  KYC Integration     — full KYC status + fraud correlation
  10. Real-time Dashboard — live fraud metrics stream
"""
from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any, Dict

from django.core.cache import cache
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.fraud_detection.missing_components import (
    BurstProtectionThrottle,
    FraudEndpointRateThrottle,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data, status_code=status.HTTP_200_OK):
    return Response(data, status=status_code)


def _err(msg, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': msg}, status=status_code)


# =============================================================================
# 1. DATA EXPORT
# =============================================================================

class ExportCreateAPIView(APIView):
    """
    POST /fraud/export/create/
    Body: { export_type, format, filters?, fields?, max_records?, compress? }
    export_type: cases | alerts | rules
    format:      csv | excel | json | pdf | xml
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        export_type = request.data.get('export_type', '').strip()
        fmt         = request.data.get('format', 'csv').strip()
        filters     = request.data.get('filters', {})
        fields      = request.data.get('fields', [])
        max_records = request.data.get('max_records')
        compress    = bool(request.data.get('compress', False))

        if not export_type:
            return _err('export_type required. Choices: cases, alerts, rules')
        if fmt not in ('csv', 'excel', 'json', 'pdf', 'xml'):
            return _err('format must be one of: csv, excel, json, pdf, xml')

        try:
            from api.fraud_detection.data_export import export_manager
            result = export_manager.create_export(
                export_type=export_type,
                format_type=fmt,
                filters=filters,
                fields=fields or None,
                max_records=int(max_records) if max_records else None,
                compress=compress,
                created_by=request.user.id,
            )
            return _ok({
                'export_id':    result.export_id,
                'filename':     result.filename,
                'format':       result.format.value,
                'record_count': result.record_count,
                'file_size':    result.file_size,
                'download_url': result.download_url,
                'success':      result.success,
                'error':        result.error_message,
            }, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('ExportCreateAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExportDownloadAPIView(APIView):
    """
    GET /fraud/export/download/<export_id>/
    Returns the generated file as an attachment.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, export_id):
        try:
            from api.fraud_detection.data_export import export_manager
            content = export_manager.download_export(export_id)
            if not content:
                return _err('Export not found or expired.', status.HTTP_404_NOT_FOUND)

            result = export_manager.get_export_status(export_id)
            fmt      = result.format.value if result else 'csv'
            filename = result.filename if result else f'export_{export_id}.{fmt}'

            content_types = {
                'csv':   'text/csv',
                'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'json':  'application/json',
                'pdf':   'application/pdf',
                'xml':   'application/xml',
            }
            response = HttpResponse(
                content,
                content_type=content_types.get(fmt, 'application/octet-stream'),
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except Exception as exc:
            logger.exception('ExportDownloadAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExportStatusAPIView(APIView):
    """GET /fraud/export/status/<export_id>/"""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, export_id):
        try:
            from api.fraud_detection.data_export import export_manager
            result = export_manager.get_export_status(export_id)
            if not result:
                return _err('Export not found.', status.HTTP_404_NOT_FOUND)
            return _ok({
                'export_id':    result.export_id,
                'success':      result.success,
                'record_count': result.record_count,
                'file_size':    result.file_size,
                'download_url': result.download_url,
                'filename':     result.filename,
            })
        except Exception as exc:
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExportHistoryAPIView(APIView):
    """GET /fraud/export/history/"""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            from api.fraud_detection.data_export import export_manager
            history = export_manager.get_export_history(
                user_id=None if request.user.is_superuser else request.user.id
            )
            return _ok({'count': len(history), 'exports': history})
        except Exception as exc:
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 2. COMPLIANCE (AML / SAR / CTR / AUDIT)
# =============================================================================

class ComplianceTransactionMonitorAPIView(APIView):
    """
    POST /fraud/compliance/monitor-transaction/
    Run AML limits check on a transaction before it is processed.
    Body: { user_id, amount, currency, transaction_type, ... }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.compliance import monitor_aml_compliance
            result = monitor_aml_compliance(request.data)
            return _ok(result)
        except Exception as exc:
            logger.exception('ComplianceTransactionMonitorAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ComplianceSARReportAPIView(APIView):
    """
    POST /fraud/compliance/sar/
    Generate a Suspicious Activity Report (SAR) for a fraud case.
    Body: { case_id, ... }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        case_id = request.data.get('case_id')
        if not case_id:
            return _err('case_id required.')
        try:
            from api.fraud_detection.models import FraudCase
            from api.fraud_detection.compliance import AMLComplianceManager
            case = FraudCase.objects.get(pk=case_id)
            mgr  = AMLComplianceManager()
            report = mgr.generate_sar_report({
                'case_id':      case.pk,
                'user_id':      case.user_id,
                'case_type':    case.case_type if hasattr(case, 'case_type') else '',
                'risk_score':   case.risk_score,
                'description':  case.description,
                'opened_at':    case.opened_at.isoformat() if case.opened_at else None,
                **request.data,
            })
            return _ok(report, status.HTTP_201_CREATED)
        except FraudCase.DoesNotExist:
            return _err('FraudCase not found.', status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            logger.exception('ComplianceSARReportAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ComplianceCTRReportAPIView(APIView):
    """
    POST /fraud/compliance/ctr/
    Generate a Currency Transaction Report (CTR) for large-value transactions.
    Body: { user_id, amount, currency, transaction_id, ... }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        try:
            from api.fraud_detection.compliance import AMLComplianceManager
            mgr    = AMLComplianceManager()
            report = mgr.generate_ctr_report(request.data)
            return _ok(report, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('ComplianceCTRReportAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ComplianceMonthlyAuditAPIView(APIView):
    """
    GET /fraud/compliance/monthly-audit/?year=2025&month=5
    Generate or retrieve the monthly compliance audit report.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            from api.fraud_detection.compliance import generate_monthly_compliance_report
            year  = int(request.query_params.get('year',  timezone.now().year))
            month = int(request.query_params.get('month', timezone.now().month))

            cache_key = f'compliance_audit_{year}_{month}'
            cached = cache.get(cache_key)
            if cached:
                return _ok(cached)

            report = generate_monthly_compliance_report()
            cache.set(cache_key, report, timeout=3600)
            return _ok(report)
        except Exception as exc:
            logger.exception('ComplianceMonthlyAuditAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ComplianceFraudIncidentReportAPIView(APIView):
    """
    POST /fraud/compliance/incident-report/
    Generate and send a fraud incident report to regulatory channels.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        try:
            from api.fraud_detection.compliance import create_fraud_incident_report
            report = create_fraud_incident_report(request.data)
            return _ok(report, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('ComplianceFraudIncidentReportAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 3. WEBHOOK FRAUD EVENT PUSH
# =============================================================================

class WebhookRegisterAPIView(APIView):
    """
    POST /fraud/webhooks/register/
    Register an external endpoint to receive fraud events.
    Body: { url, secret, events, is_active }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        url    = request.data.get('url', '').strip()
        secret = request.data.get('secret', '').strip()
        events = request.data.get('events', [])
        if not url:
            return _err('url required.')
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.webhooks_integration import (
                WebhookConfig, WebhookProcessor
            )
            config = WebhookConfig(
                webhook_id=str(__import__('uuid').uuid4()),
                url=url,
                secret=secret,
                events=events or [],
                is_active=bool(request.data.get('is_active', True)),
                metadata={'registered_by': request.user.id},
            )
            processor = WebhookProcessor()
            processor.register_webhook(config)
            logger.info('Webhook registered: %s by user %s', url, request.user.id)
            return _ok({'registered': True, 'webhook_id': config.webhook_id},
                       status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('WebhookRegisterAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class WebhookPushFraudEventAPIView(APIView):
    """
    POST /fraud/webhooks/push/
    Manually push a fraud event to all registered webhooks.
    Body: { event_type, fraud_attempt_id?, case_id?, payload? }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        event_type = request.data.get('event_type', 'fraud_detected')
        payload    = request.data.get('payload', {})
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.webhooks_integration import (
                WebhookEvent, WebhookEventType, WebhookProcessor
            )
            event = WebhookEvent(
                event_id=str(__import__('uuid').uuid4()),
                event_type=WebhookEventType(event_type) if hasattr(WebhookEventType, event_type.upper())
                           else WebhookEventType.FRAUD_DETECTED,
                payload={
                    **payload,
                    'triggered_by': request.user.id,
                    'timestamp':    timezone.now().isoformat(),
                },
                source='api',
            )
            processor = WebhookProcessor()
            from api.fraud_detection.views_services import _run
            _run(processor._deliver_all(event))
            return _ok({'pushed': True, 'event_id': event.event_id})
        except Exception as exc:
            logger.exception('WebhookPushFraudEventAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class WebhookListAPIView(APIView):
    """GET /fraud/webhooks/list/"""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.webhooks_integration import WebhookProcessor
            processor = WebhookProcessor()
            webhooks = [
                {'webhook_id': wid, **vars(cfg)}
                for wid, cfg in processor.webhooks.items()
            ]
            return _ok({'count': len(webhooks), 'webhooks': webhooks})
        except Exception as exc:
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 4. REFERRAL FRAUD
# =============================================================================

class ReferralFraudDetectAPIView(APIView):
    """
    POST /fraud/referral/detect/
    Check a single referral event for fraud.
    Body: { referrer_user_id, referred_user_id?, referral_code, ip_address?, device_id? }
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        referrer_id = request.data.get('referrer_user_id')
        if not referrer_id:
            return _err('referrer_user_id required.')
        if not request.user.is_staff and int(referrer_id) != request.user.id:
            return _err('Permission denied.', status.HTTP_403_FORBIDDEN)
        try:
            from api.fraud_detection.detectors.ReferralFraudDetector import ReferralFraudDetector
            detector = ReferralFraudDetector()
            result   = detector.detect(request.data)
            if result['is_fraud']:
                from api.fraud_detection.models import FraudAttempt
                FraudAttempt.objects.create(
                    user_id=referrer_id,
                    attempt_type='referral_fraud',
                    description='Referral fraud detected by ReferralFraudDetector',
                    detected_by='ReferralFraudDetector',
                    fraud_score=result['risk_score'],
                    confidence_score=80,
                    evidence_data={
                        'signals':       result.get('signals', {}),
                        'reasons':       result.get('reasons', []),
                        'referral_code': request.data.get('referral_code', ''),
                    },
                    metadata={'referral_result': result},
                )
            return _ok(result)
        except Exception as exc:
            logger.exception('ReferralFraudDetectAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReferralFraudBatchAPIView(APIView):
    """
    POST /fraud/referral/batch/
    Batch-check multiple referral events.
    Body: { referrals: [{referrer_user_id, ...}, ...] }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        referrals = request.data.get('referrals', [])
        if not isinstance(referrals, list) or not referrals:
            return _err('referrals must be a non-empty list.')
        try:
            from api.fraud_detection.detectors.ReferralFraudDetector import ReferralFraudDetector
            detector = ReferralFraudDetector()
            results  = detector.batch_detect(referrals)
            flagged  = [r for r in results if r['is_suspicious']]
            blocked  = [r for r in results if r['is_fraud']]
            return _ok({
                'total':   len(results),
                'flagged': len(flagged),
                'blocked': len(blocked),
                'results': results,
            })
        except Exception as exc:
            logger.exception('ReferralFraudBatchAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReferralFraudStatsAPIView(APIView):
    """GET /fraud/referral/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            from api.fraud_detection.models import FraudAttempt
            from django.db.models import Count, Avg
            days   = int(request.query_params.get('days', 30))
            cutoff = timezone.now() - timedelta(days=days)
            qs     = FraudAttempt.objects.filter(
                attempt_type='referral_fraud',
                created_at__gte=cutoff,
            )
            return _ok({
                'period_days':     days,
                'total_flagged':   qs.count(),
                'avg_fraud_score': qs.aggregate(avg=Avg('fraud_score'))['avg'] or 0,
                'confirmed_fraud': qs.filter(status='confirmed').count(),
                'by_status':       dict(
                    qs.values('status').annotate(n=Count('id')).values_list('status', 'n')
                ),
            })
        except Exception as exc:
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 5. CHARGEBACK / DISPUTE
# =============================================================================

class ChargebackListCreateAPIView(APIView):
    """
    GET  /fraud/chargebacks/          — list all disputes
    POST /fraud/chargebacks/          — record a new dispute
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            from api.fraud_detection.models_chargeback import ChargebackDispute
            qs = ChargebackDispute.objects.select_related('user').order_by('-received_at')
            status_filter = request.query_params.get('status')
            if status_filter:
                qs = qs.filter(status=status_filter)
            user_id = request.query_params.get('user_id')
            if user_id:
                qs = qs.filter(user_id=user_id)
            data = list(qs.values(
                'id', 'dispute_id', 'user_id', 'transaction_id', 'reason',
                'status', 'original_amount', 'disputed_amount', 'currency',
                'received_at', 'response_deadline', 'resolved_at', 'is_fraudulent',
            )[:200])
            return _ok({'count': len(data), 'disputes': data})
        except Exception as exc:
            logger.exception('ChargebackListCreateAPIView.get failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        required = ['transaction_id', 'reason', 'disputed_amount']
        missing  = [f for f in required if not request.data.get(f)]
        if missing:
            return _err(f'Missing required fields: {", ".join(missing)}')
        try:
            from api.fraud_detection.models_chargeback import ChargebackDispute
            dispute = ChargebackDispute.objects.create(
                user_id=request.data.get('user_id'),
                transaction_id=request.data['transaction_id'],
                payment_processor=request.data.get('payment_processor', 'unknown'),
                original_amount=request.data.get('original_amount', request.data['disputed_amount']),
                disputed_amount=request.data['disputed_amount'],
                currency=request.data.get('currency', 'USD'),
                reason=request.data['reason'],
                bank_reference=request.data.get('bank_reference', ''),
                description=request.data.get('description', ''),
                is_fraudulent=bool(request.data.get('is_fraudulent', False)),
                metadata=request.data.get('metadata', {}),
            )
            logger.info('Chargeback recorded: %s by user %s', dispute.dispute_id, request.user)
            return _ok({'id': dispute.pk, 'dispute_id': str(dispute.dispute_id)},
                       status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('ChargebackListCreateAPIView.post failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChargebackDetailAPIView(APIView):
    """
    GET   /fraud/chargebacks/<pk>/          — detail
    PATCH /fraud/chargebacks/<pk>/          — update status / resolution
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, pk):
        try:
            from api.fraud_detection.models_chargeback import ChargebackDispute
            dispute = ChargebackDispute.objects.get(pk=pk)
            from django.forms.models import model_to_dict
            return _ok(model_to_dict(dispute))
        except ChargebackDispute.DoesNotExist:
            return _err('Not found.', status.HTTP_404_NOT_FOUND)

    def patch(self, request, pk):
        try:
            from api.fraud_detection.models_chargeback import ChargebackDispute
            dispute = ChargebackDispute.objects.get(pk=pk)
            allowed = ['status', 'resolution_notes', 'evidence_submitted',
                       'bank_reference', 'is_fraudulent', 'fraud_confirmed']
            for field in allowed:
                if field in request.data:
                    setattr(dispute, field, request.data[field])
            if request.data.get('status') in (
                ChargebackDispute.Status.WON, ChargebackDispute.Status.LOST,
                ChargebackDispute.Status.REVERSED, ChargebackDispute.Status.WITHDRAWN,
            ):
                dispute.resolved_at  = timezone.now()
                dispute.resolved_by  = request.user
            dispute.save()
            return _ok({'updated': True, 'status': dispute.status})
        except ChargebackDispute.DoesNotExist:
            return _err('Not found.', status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChargebackStatsAPIView(APIView):
    """GET /fraud/chargebacks/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            from api.fraud_detection.models_chargeback import ChargebackDispute
            from django.db.models import Count, Sum
            days   = int(request.query_params.get('days', 30))
            cutoff = timezone.now() - timedelta(days=days)
            qs     = ChargebackDispute.objects.filter(received_at__gte=cutoff)
            return _ok({
                'period_days':      days,
                'total_disputes':   qs.count(),
                'total_amount':     float(qs.aggregate(t=Sum('disputed_amount'))['t'] or 0),
                'won':              qs.filter(status='won').count(),
                'lost':             qs.filter(status='lost').count(),
                'open':             qs.filter(status__in=['received','investigating','represented']).count(),
                'fraud_confirmed':  qs.filter(fraud_confirmed=True).count(),
                'by_reason':        dict(
                    qs.values('reason').annotate(n=Count('id')).values_list('reason', 'n')
                ),
                'by_processor':     dict(
                    qs.values('payment_processor').annotate(n=Count('id')).values_list('payment_processor', 'n')
                ),
            })
        except Exception as exc:
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 6. CONVERSION CAP ENFORCEMENT
# =============================================================================

class ConversionCapListAPIView(APIView):
    """GET /fraud/conversion-caps/"""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            from api.fraud_detection.models_chargeback import ConversionCap
            qs   = ConversionCap.objects.filter(is_active=True).order_by('-created_at')
            data = list(qs.values(
                'id', 'offer_id', 'advertiser_id', 'advertiser_name',
                'cap_type', 'cap_limit', 'current_count', 'window_hours',
                'action_on_exceed', 'reset_at', 'is_active',
            ))
            return _ok({'count': len(data), 'caps': data})
        except Exception as exc:
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        required = ['cap_type', 'cap_limit']
        missing  = [f for f in required if request.data.get(f) is None]
        if missing:
            return _err(f'Missing: {", ".join(missing)}')
        try:
            from api.fraud_detection.models_chargeback import ConversionCap
            cap = ConversionCap.objects.create(
                offer_id=request.data.get('offer_id'),
                advertiser_id=request.data.get('advertiser_id'),
                advertiser_name=request.data.get('advertiser_name', ''),
                cap_type=request.data['cap_type'],
                cap_limit=int(request.data['cap_limit']),
                window_hours=int(request.data.get('window_hours', 0)),
                action_on_exceed=request.data.get('action_on_exceed', 'block'),
                metadata=request.data.get('metadata', {}),
            )
            return _ok({'id': cap.pk, 'cap_type': cap.cap_type}, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('ConversionCapListAPIView.post failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConversionCapCheckAPIView(APIView):
    """
    POST /fraud/conversion-caps/check/
    Check if a conversion is allowed under all applicable caps.
    Body: { offer_id?, user_id?, ip_address?, device_id? }
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        offer_id   = request.data.get('offer_id')
        user_id    = request.data.get('user_id', request.user.id)
        ip_address = request.data.get('ip_address', '')
        device_id  = request.data.get('device_id', '')

        try:
            from api.fraud_detection.models_chargeback import ConversionCap
            from django.db.models import Q

            caps = ConversionCap.objects.filter(
                is_active=True
            ).filter(
                Q(offer_id=offer_id) | Q(offer_id__isnull=True)
            )

            blocked_by = []
            can_convert = True

            for cap in caps:
                if cap.is_exceeded:
                    can_convert = False
                    blocked_by.append({
                        'cap_id':   cap.pk,
                        'cap_type': cap.cap_type,
                        'limit':    cap.cap_limit,
                        'current':  cap.current_count,
                        'action':   cap.action_on_exceed,
                    })

            return _ok({
                'can_convert': can_convert,
                'offer_id':    offer_id,
                'user_id':     user_id,
                'blocked_by':  blocked_by,
                'caps_checked': caps.count(),
            })
        except Exception as exc:
            logger.exception('ConversionCapCheckAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConversionCapResetAPIView(APIView):
    """POST /fraud/conversion-caps/<pk>/reset/"""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, pk):
        try:
            from api.fraud_detection.models_chargeback import ConversionCap
            cap = ConversionCap.objects.get(pk=pk)
            old_count = cap.current_count
            cap.reset()
            logger.info('Cap %d reset by %s (was %d)', pk, request.user, old_count)
            return _ok({'reset': True, 'cap_id': pk, 'previous_count': old_count})
        except ConversionCap.DoesNotExist:
            return _err('Not found.', status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 7. ADVERTISER / PUBLISHER DASHBOARD
# =============================================================================

class PublisherFraudDashboardAPIView(APIView):
    """
    GET /fraud/publisher/dashboard/?publisher_id=X
    Publisher-specific fraud stats: click fraud, conversion fraud, IP abuse.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        days         = int(request.query_params.get('days', 30))
        publisher_id = request.query_params.get('publisher_id')
        cutoff       = timezone.now() - timedelta(days=days)

        try:
            from api.fraud_detection.models import FraudAttempt, OfferCompletion
            from django.db.models import Count, Avg, Sum

            attempt_qs = FraudAttempt.objects.filter(
                created_at__gte=cutoff,
                attempt_type__in=['click_fraud', 'conversion_fraud', 'offer_abuse'],
            )
            completion_qs = OfferCompletion.objects.filter(
                tracked_at__gte=cutoff,
                is_fraud=True,
            )

            return _ok({
                'period_days':          days,
                'publisher_id':         publisher_id,
                'click_fraud_attempts': attempt_qs.filter(attempt_type='click_fraud').count(),
                'fraud_completions':    completion_qs.count(),
                'fraud_amount_lost':    float(
                    completion_qs.aggregate(t=Sum('reward_amount'))['t'] or 0
                ),
                'avg_fraud_score':      float(
                    attempt_qs.aggregate(avg=Avg('fraud_score'))['avg'] or 0
                ),
                'top_fraud_ips':        list(
                    attempt_qs.values('evidence_data__ip')
                              .annotate(n=Count('id'))
                              .order_by('-n')[:10]
                ),
                'daily_trend':          list(
                    attempt_qs
                    .extra(select={'day': "DATE(created_at)"})
                    .values('day')
                    .annotate(count=Count('id'))
                    .order_by('day')
                ),
            })
        except Exception as exc:
            logger.exception('PublisherFraudDashboardAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdvertiserFraudReportAPIView(APIView):
    """
    GET /fraud/advertiser/report/?advertiser_id=X&days=30
    Advertiser-facing fraud report: fraudulent conversions, cap violations.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        days          = int(request.query_params.get('days', 30))
        advertiser_id = request.query_params.get('advertiser_id')
        cutoff        = timezone.now() - timedelta(days=days)

        try:
            from api.fraud_detection.models import OfferCompletion, FraudAttempt
            from django.db.models import Count, Sum, Avg

            qs = OfferCompletion.objects.filter(tracked_at__gte=cutoff)
            fraud_qs = qs.filter(is_fraud=True)

            return _ok({
                'period_days':            days,
                'advertiser_id':          advertiser_id,
                'total_completions':      qs.count(),
                'fraudulent_completions': fraud_qs.count(),
                'fraud_rate':             round(
                    fraud_qs.count() / max(qs.count(), 1) * 100, 2
                ),
                'fraud_amount':           float(
                    fraud_qs.aggregate(t=Sum('reward_amount'))['t'] or 0
                ),
                'saved_by_detection':     float(
                    fraud_qs.aggregate(t=Sum('reward_amount'))['t'] or 0
                ),
                'by_fraud_reason':        dict(
                    fraud_qs.exclude(fraud_reason='')
                            .values('fraud_reason')
                            .annotate(n=Count('id'))
                            .values_list('fraud_reason', 'n')
                ),
                'top_fraud_users':        list(
                    fraud_qs.values('user_id')
                            .annotate(n=Count('id'), lost=Sum('reward_amount'))
                            .order_by('-n')[:10]
                ),
            })
        except Exception as exc:
            logger.exception('AdvertiserFraudReportAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 8. PRE-PAYOUT FRAUD SCREEN
# =============================================================================

class PrePayoutScreenAPIView(APIView):
    """
    POST /fraud/payout/screen/
    Screen a payout before releasing funds.
    Body: { user_id, amount, payout_method, currency? }
    Returns: { approved, risk_score, reason, recommendation }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        user_id       = request.data.get('user_id')
        amount        = request.data.get('amount')
        payout_method = request.data.get('payout_method', 'wallet')

        if not user_id or amount is None:
            return _err('user_id and amount required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fraud_adapter import FraudDetectionAdapter
            adapter = FraudDetectionAdapter()
            result  = adapter.pre_payout_screen(
                user_id=int(user_id),
                amount=float(amount),
                payout_method=payout_method,
            )
        except Exception:
            result = {}

        # Supplement with local risk profile check
        try:
            from api.fraud_detection.models import UserRiskProfile
            profile = UserRiskProfile.objects.get(user_id=user_id)
            risk_score = profile.overall_risk_score
            is_restricted = profile.is_restricted
        except Exception:
            risk_score    = result.get('risk_score', 0)
            is_restricted = False

        final_score = max(int(risk_score), int(result.get('risk_score', 0)))

        if is_restricted or final_score >= 90:
            approved        = False
            recommendation  = 'block'
        elif final_score >= 70:
            approved        = False
            recommendation  = 'manual_review'
        elif final_score >= 40:
            approved        = True
            recommendation  = 'approve_with_monitoring'
        else:
            approved        = True
            recommendation  = 'approve'

        return _ok({
            'user_id':        user_id,
            'amount':         amount,
            'payout_method':  payout_method,
            'approved':       approved,
            'risk_score':     final_score,
            'recommendation': recommendation,
            'is_restricted':  is_restricted,
            'details':        result,
            'screened_at':    timezone.now().isoformat(),
        })


class PrePayoutBulkScreenAPIView(APIView):
    """
    POST /fraud/payout/bulk-screen/
    Screen multiple payouts at once.
    Body: { payouts: [{user_id, amount, payout_method}, ...] }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        payouts = request.data.get('payouts', [])
        if not isinstance(payouts, list) or not payouts:
            return _err('payouts must be a non-empty list.')

        results = []
        blocked = 0
        for payout in payouts:
            user_id       = payout.get('user_id')
            amount        = payout.get('amount', 0)
            payout_method = payout.get('payout_method', 'wallet')
            try:
                from api.fraud_detection.models import UserRiskProfile
                profile = UserRiskProfile.objects.get(user_id=user_id)
                score = profile.overall_risk_score
                approved = score < 70 and not profile.is_restricted
            except Exception:
                score    = 0
                approved = True

            if not approved:
                blocked += 1
            results.append({
                'user_id':    user_id,
                'amount':     amount,
                'approved':   approved,
                'risk_score': score,
            })

        return _ok({
            'total':   len(results),
            'blocked': blocked,
            'approved': len(results) - blocked,
            'results': results,
        })


# =============================================================================
# 9. KYC INTEGRATION
# =============================================================================

class KYCStatusAPIView(APIView):
    """GET /fraud/kyc/status/<user_id>/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        if not request.user.is_staff and request.user.id != int(user_id):
            return _err('Permission denied.', status.HTTP_403_FORBIDDEN)
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fraud_adapter import FraudDetectionAdapter
            adapter = FraudDetectionAdapter()
            kyc     = adapter.get_kyc_status(user_id=int(user_id))

            # Cross-reference with fraud risk profile
            try:
                from api.fraud_detection.models import UserRiskProfile
                profile     = UserRiskProfile.objects.get(user_id=user_id)
                kyc['fraud_risk_score']    = profile.overall_risk_score
                kyc['is_flagged']          = profile.is_flagged
                kyc['monitoring_level']    = profile.monitoring_level
            except Exception:
                pass

            return _ok(kyc)
        except Exception as exc:
            logger.exception('KYCStatusAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class KYCFraudCorrelationAPIView(APIView):
    """
    GET /fraud/kyc/correlation/
    Find users with KYC issues that also have high fraud scores.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            from api.fraud_detection.models import UserRiskProfile
            min_risk = int(request.query_params.get('min_risk', 60))

            high_risk_users = list(
                UserRiskProfile.objects.filter(
                    overall_risk_score__gte=min_risk,
                    is_flagged=True,
                ).values('user_id', 'overall_risk_score', 'monitoring_level', 'is_restricted')[:100]
            )
            return _ok({
                'min_risk':         min_risk,
                'high_risk_users':  high_risk_users,
                'count':            len(high_risk_users),
            })
        except Exception as exc:
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 10. REAL-TIME DASHBOARD
# =============================================================================

class RealTimeFraudDashboardAPIView(APIView):
    """
    GET /fraud/dashboard/realtime/
    Live fraud metrics — cached 60s. Suitable for dashboard polling.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        cache_key = 'fraud_realtime_dashboard'
        cached = cache.get(cache_key)
        if cached:
            cached['from_cache'] = True
            return _ok(cached)

        try:
            from api.fraud_detection.models import (
                FraudAttempt, FraudAlert, FraudCase,
                UserRiskProfile, OfferCompletion,
            )
            from django.db.models import Count, Avg

            now       = timezone.now()
            last_hour = now - timedelta(hours=1)
            last_day  = now - timedelta(hours=24)

            data = {
                'timestamp':        now.isoformat(),
                'from_cache':       False,
                'last_hour': {
                    'fraud_attempts': FraudAttempt.objects.filter(created_at__gte=last_hour).count(),
                    'new_alerts':     FraudAlert.objects.filter(created_at__gte=last_hour).count(),
                    'blocked_users':  FraudAttempt.objects.filter(
                        created_at__gte=last_hour, status='blocked'
                    ).values('user_id').distinct().count(),
                    'avg_score':      FraudAttempt.objects.filter(
                        created_at__gte=last_hour
                    ).aggregate(avg=Avg('fraud_score'))['avg'] or 0,
                },
                'last_24h': {
                    'fraud_attempts':   FraudAttempt.objects.filter(created_at__gte=last_day).count(),
                    'fraud_completions': OfferCompletion.objects.filter(
                        tracked_at__gte=last_day, is_fraud=True
                    ).count(),
                    'new_cases':        FraudCase.objects.filter(opened_at__gte=last_day).count(),
                    'high_risk_users':  UserRiskProfile.objects.filter(
                        overall_risk_score__gte=80
                    ).count(),
                },
                'totals': {
                    'open_cases':     FraudCase.objects.filter(
                        status__in=['open', 'investigating']
                    ).count(),
                    'unread_alerts':  FraudAlert.objects.filter(
                        acknowledged=False
                    ).count(),
                    'flagged_users':  UserRiskProfile.objects.filter(is_flagged=True).count(),
                    'restricted_users': UserRiskProfile.objects.filter(is_restricted=True).count(),
                },
                'by_type': dict(
                    FraudAttempt.objects.filter(created_at__gte=last_day)
                    .values('attempt_type')
                    .annotate(n=Count('id'))
                    .values_list('attempt_type', 'n')
                ),
            }
            cache.set(cache_key, data, timeout=60)
            return _ok(data)
        except Exception as exc:
            logger.exception('RealTimeFraudDashboardAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FraudMetricsStreamAPIView(APIView):
    """
    GET /fraud/dashboard/metrics-stream/
    Server-sent-events style endpoint — returns latest metrics as newline-delimited JSON.
    Use with EventSource on the frontend.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        def generate():
            from api.fraud_detection.models import FraudAttempt, FraudAlert
            from django.db.models import Count
            now       = timezone.now()
            last_hour = now - timedelta(hours=1)
            payload   = {
                'ts':           now.isoformat(),
                'attempts_1h':  FraudAttempt.objects.filter(created_at__gte=last_hour).count(),
                'alerts_open':  FraudAlert.objects.filter(acknowledged=False).count(),
            }
            yield f"data: {json.dumps(payload)}\n\n"

        return StreamingHttpResponse(generate(), content_type='text/event-stream')


# ── MISSING: Business Rule views expected by urls.py ─────────────────────────
from rest_framework.views import APIView as _APIView
from rest_framework.response import Response as _R
from rest_framework.permissions import IsAdminUser as _Admin
from rest_framework import status as _s


class BusinessRuleListAPIView(_APIView):
    """GET /business-rules/ — list all fraud business rules."""
    permission_classes = [_Admin]
    def get(self, request):
        from api.fraud_detection.models import FraudRule
        from api.fraud_detection.serializers import FraudRuleSerializer
        qs = FraudRule.objects.filter(is_active=True).order_by("-created_at")
        return _R({"rules": FraudRuleSerializer(qs, many=True).data, "total": qs.count()})


class BusinessRuleEvaluateAPIView(_APIView):
    """POST /business-rules/evaluate/ — evaluate rules against a payload."""
    permission_classes = [_Admin]
    def post(self, request):
        try:
            from api.fraud_detection.models import FraudRule
            rules   = FraudRule.objects.filter(is_active=True)
            payload = request.data
            triggered = []
            for rule in rules:
                try:
                    threshold = getattr(rule, 'threshold', 0)
                    score     = float(payload.get('risk_score', 0))
                    if score >= float(threshold):
                        triggered.append({"rule_id": rule.pk, "name": rule.name,
                                          "threshold": threshold, "score": score})
                except Exception:
                    pass
            return _R({"triggered_rules": triggered, "total_evaluated": rules.count()})
        except Exception as exc:
            return _R({"error": str(exc)}, status=_s.HTTP_500_INTERNAL_SERVER_ERROR)


class BusinessRuleCreateAPIView(_APIView):
    """POST /business-rules/create/ — create a new fraud rule."""
    permission_classes = [_Admin]
    def post(self, request):
        from api.fraud_detection.serializers import FraudRuleSerializer
        s = FraudRuleSerializer(data=request.data)
        if s.is_valid():
            rule = s.save()
            return _R({"success": True, "rule_id": rule.pk, "rule": s.data},
                      status=_s.HTTP_201_CREATED)
        return _R({"success": False, "errors": s.errors}, status=_s.HTTP_400_BAD_REQUEST)


class BusinessRuleToggleAPIView(_APIView):
    """POST /business-rules/<rule_id>/toggle/ — enable / disable a rule."""
    permission_classes = [_Admin]
    def post(self, request, rule_id: str):
        try:
            from api.fraud_detection.models import FraudRule
            rule           = FraudRule.objects.get(pk=rule_id)
            rule.is_active = not rule.is_active
            rule.save(update_fields=["is_active"])
            return _R({"rule_id": rule_id, "is_active": rule.is_active})
        except FraudRule.DoesNotExist:
            return _R({"error": "Rule not found"}, status=_s.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return _R({"error": str(exc)}, status=_s.HTTP_500_INTERNAL_SERVER_ERROR)
