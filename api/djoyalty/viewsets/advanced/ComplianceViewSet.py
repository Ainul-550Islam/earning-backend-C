# djoyalty/viewsets/advanced/ComplianceViewSet.py
"""
Compliance ViewSet -- exposes compliance.py GDPRComplianceManager,
DataRetentionPolicy। Previously: zero API routes।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ...permissions import IsLoyaltyAdmin
from ...mixins import DjoyaltyBaseViewSet
from ...serializers.AnalyticsSerializer import (
    GDPRDataExportSerializer, GDPRDeleteSerializer,
    RetentionPolicySerializer, RetentionCleanupInputSerializer,
)


class ComplianceViewSet(DjoyaltyBaseViewSet, viewsets.ViewSet):
    """
    GET  /compliance/customer/{id}/data/          -- GDPR data access export
    POST /compliance/customer/{id}/delete/        -- GDPR deletion request
    GET  /compliance/customer/{id}/consent-history/ -- full consent trail
    GET  /compliance/retention/policy/            -- retention schedule
    POST /compliance/retention/cleanup/           -- dry-run or live cleanup
    """
    permission_classes = [IsLoyaltyAdmin]

    @action(detail=False, methods=['get'],
            url_path='customer/(?P<customer_id>[0-9]+)/data')
    def data_access(self, request, customer_id=None):
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        from ...compliance import GDPRComplianceManager
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            return Response(GDPRComplianceManager.handle_data_access_request(customer))
        except Exception as e:
            return self.err(str(e), http_status=500)

    @action(detail=False, methods=['post'],
            url_path='customer/(?P<customer_id>[0-9]+)/delete')
    def data_delete(self, request, customer_id=None):
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        from ...compliance import GDPRComplianceManager
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            result = GDPRComplianceManager.handle_deletion_request(customer)
            return Response(result)
        except Exception as e:
            return self.err(str(e), http_status=500)

    @action(detail=False, methods=['get'],
            url_path='customer/(?P<customer_id>[0-9]+)/consent-history')
    def consent_history(self, request, customer_id=None):
        from django.shortcuts import get_object_or_404
        from ...models.core import Customer
        from ...compliance import GDPRComplianceManager
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            return Response({'history': GDPRComplianceManager.get_consent_history(customer)})
        except Exception as e:
            return self.err(str(e), http_status=500)

    @action(detail=False, methods=['get'], url_path='retention/policy')
    def retention_policy(self, request):
        from ...compliance import DataRetentionPolicy
        record_types = [
            'txn', 'event', 'points_ledger', 'fraud_log',
            'audit_log', 'notification', 'receipt_scan',
        ]
        policy = {}
        for rt in record_types:
            days = DataRetentionPolicy.get_retention_days(rt)
            policy[rt] = {'retain_days': days}
        return Response({'retention_policy': policy})

    @action(detail=False, methods=['post'], url_path='retention/cleanup')
    def retention_cleanup(self, request):
        from ...compliance import DataRetentionPolicy
        dry_run = request.data.get('dry_run', True)
        try:
            result = DataRetentionPolicy.run_retention_cleanup(dry_run=dry_run)
            return Response({'dry_run': dry_run, 'result': result})
        except Exception as e:
            return self.err(str(e), http_status=500)
    @action(detail=False, methods=['get', 'post'], url_path='fraud-rules', permission_classes=[IsLoyaltyAdmin])
    def fraud_rules(self, request):
        """
        FIXED: LoyaltyFraudRule had NO API endpoint -- fraud rules only configurable via admin.
        GET: list rules. POST: create new rule.
        """
        from ...models.advanced import LoyaltyFraudRule
        if request.method == 'GET':
            qs = LoyaltyFraudRule.objects.all().order_by('-created_at')
            return Response({'results': [{
                'id': r.id, 'rule_type': r.rule_type, 'threshold': str(r.threshold),
                'action': r.action, 'is_active': r.is_active, 'description': getattr(r, 'description', ''),
            } for r in qs]})
        rule = LoyaltyFraudRule.objects.create(
            rule_type=request.data.get('rule_type'),
            threshold=request.data.get('threshold', 0),
            action=request.data.get('action', 'flag'),
            is_active=request.data.get('is_active', True),
        )
        return Response({'id': rule.id, 'rule_type': rule.rule_type, 'action': rule.action},
                        status=status.HTTP_201_CREATED)
