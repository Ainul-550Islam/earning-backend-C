# =============================================================================
# fraud_detection/views_extended.py
#
# Permanent home for the 16 ViewSets / APIViews that were previously
# in views_missing.py.  That file is now a thin compatibility shim that
# re-imports everything from here so existing url-conf imports keep working
# without change.
#
# Import the serializers from the consolidated serializers.py (no longer
# from serializers_missing.py).
# =============================================================================
from __future__ import annotations

import hashlib
import logging
from datetime import timedelta
from typing import Any, Dict

from django.core.cache import cache
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDay, TruncHour
from django.utils import timezone

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.fraud_detection.missing_components import (
    BurstProtectionThrottle,
    FraudEndpointRateThrottle,
    HighRiskUserThrottle,
    PublisherRateThrottle,
)
from api.fraud_detection.models import (
    DeviceFingerprint,
    FraudAlert,
    FraudAttempt,
    FraudCase,
    FraudCaseAction,
    FraudCaseEvidence,
    FraudNotification,
    FraudPattern,
    FraudSettings,
    FraudWhitelist,
    IPReputation,
    OfferCompletion,
    UserRiskProfile,
)

# ── Serializers — all from the merged flat module now ──────────────────────
from api.fraud_detection.serializers import (
    DeviceFingerprintSerializer,
    FraudAlertSerializer,
    FraudCaseActionFullSerializer,
    FraudCaseEvidenceFullSerializer,
    FraudCaseFullSerializer,
    FraudCaseSerializer,
    FraudNotificationSerializer,
    FraudPatternSerializer,
    FraudSettingsSerializer,
    FraudWhitelistFullSerializer,
    IPReputationSerializer,
    OfferCompletionCreateSerializer,
    OfferCompletionSerializer,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Shared pagination
# =============================================================================

class StandardResultsPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


# =============================================================================
# 1. FraudPatternViewSet
# =============================================================================

class FraudPatternViewSet(viewsets.ModelViewSet):
    """CRUD for FraudPattern rules."""
    queryset = FraudPattern.objects.all().order_by('-created_at')
    serializer_class = FraudPatternSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['pattern_type', 'is_active', 'severity']
    search_fields = ['name', 'description', 'pattern_value']
    ordering_fields = ['created_at', 'severity', 'match_count']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        pattern = self.get_object()
        pattern.is_active = True
        pattern.save(update_fields=['is_active', 'updated_at'])
        return Response({'status': 'activated', 'id': pattern.id})

    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        pattern = self.get_object()
        pattern.is_active = False
        pattern.save(update_fields=['is_active', 'updated_at'])
        return Response({'status': 'deactivated', 'id': pattern.id})

    @action(detail=False, methods=['get'], url_path='active')
    def active_patterns(self, request):
        qs = self.get_queryset().filter(is_active=True)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='accuracy')
    def accuracy_stats(self, request):
        """Aggregate accuracy statistics across all trained patterns."""
        try:
            from django.db.models import Max
            stats = FraudPattern.objects.aggregate(
                total=Count('id'),
                trained=Count('id', filter=Q(is_trained=True)),
                avg_accuracy=Avg('accuracy_rate'),
                max_accuracy=Max('accuracy_rate'),
                total_occurrences=Sum('occurrence_count'),
            )
            stats['avg_accuracy'] = round(stats['avg_accuracy'] or 0, 4)
            stats['max_accuracy'] = round(stats['max_accuracy'] or 0, 4)
            return Response(stats, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.exception("accuracy_stats failed: %s", exc)
            return Response(
                {'error': 'Failed to calculate accuracy statistics.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =============================================================================
# 2. FraudSettingsViewSet
# =============================================================================

class FraudSettingsViewSet(viewsets.ModelViewSet):
    """System-wide fraud detection configuration (admin only)."""
    queryset = FraudSettings.objects.all().order_by('-updated_at')
    serializer_class = FraudSettingsSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = StandardResultsPagination
    http_method_names = ['get', 'put', 'patch', 'head', 'options']  # no POST/DELETE

    @action(detail=False, methods=['get'], url_path='current')
    def current(self, request):
        """Return the single active settings object (create default if missing)."""
        settings_obj, _ = FraudSettings.objects.get_or_create(
            pk=1,
            defaults={'block_vpn': True, 'global_risk_threshold': 70},
        )
        return Response(FraudSettingsSerializer(settings_obj, context={'request': request}).data)

    @action(detail=False, methods=['patch'], url_path='update-threshold')
    def update_threshold(self, request):
        threshold = request.data.get('global_risk_threshold')
        if threshold is None:
            return Response({'error': 'global_risk_threshold required'}, status=400)
        settings_obj, _ = FraudSettings.objects.get_or_create(pk=1)
        settings_obj.global_risk_threshold = int(threshold)
        settings_obj.updated_by = request.user
        settings_obj.save(update_fields=['global_risk_threshold', 'updated_by'])
        return Response({
            'updated': True,
            'global_risk_threshold': settings_obj.global_risk_threshold,
        })


# =============================================================================
# 3. FraudWhitelistViewSet
# =============================================================================

class FraudWhitelistViewSet(viewsets.ModelViewSet):
    """Manage whitelist / blacklist entries."""
    queryset = FraudWhitelist.objects.all().order_by('-created_at')
    serializer_class = FraudWhitelistFullSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['entity_type', 'is_active']
    search_fields = ['entity_value', 'reason']
    ordering_fields = ['created_at', 'expires_at']

    def perform_create(self, serializer):
        serializer.save(whitelisted_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        entry = self.get_object()
        entry.is_active = False
        entry.save(update_fields=['is_active', 'updated_at'])
        logger.info("Whitelist entry %s deactivated by %s", entry.id, request.user)
        return Response({'status': 'deactivated', 'id': entry.id})

    @action(detail=False, methods=['get'], url_path='active')
    def active_entries(self, request):
        qs = self.get_queryset().filter(is_active=True)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='bulk-add')
    def bulk_add(self, request):
        entries = request.data.get('entries', [])
        if not entries:
            return Response({'error': 'entries list required'}, status=400)
        created = []
        for entry_data in entries:
            entry_data['whitelisted_by'] = request.user.id
            ser = FraudWhitelistFullSerializer(data=entry_data, context={'request': request})
            if ser.is_valid():
                ser.save(whitelisted_by=request.user)
                created.append(ser.data)
        return Response({'created': len(created), 'entries': created}, status=201)


# =============================================================================
# 4. FraudNotificationViewSet
# =============================================================================

class FraudNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list/detail + mark-as-read for fraud notifications."""
    serializer_class = FraudNotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['notification_type', 'is_sent']
    ordering_fields = ['created_at', 'sent_at']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return FraudNotification.objects.all()
        return FraudNotification.objects.filter(user=user)

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        if notif.read_at is None:
            notif.read_at = timezone.now()
            notif.save(update_fields=['read_at'])
        return Response({'status': 'read', 'read_at': notif.read_at})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        now = timezone.now()
        count = FraudNotification.objects.filter(
            user=request.user, read_at__isnull=True
        ).update(read_at=now)
        return Response({'marked_read': count})

    @action(detail=False, methods=['post'], url_path='bulk-send')
    def bulk_send(self, request):
        """
        Bulk-send fraud notifications to multiple users.
        Payload: { user_ids, notification_type, message, metadata? }
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user_ids   = request.data.get('user_ids', [])
        notif_type = request.data.get('notification_type', 'fraud_detected')
        message    = request.data.get('message', '')
        metadata   = request.data.get('metadata', {})

        if not user_ids:
            return Response(
                {'error': 'user_ids is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not message:
            return Response(
                {'error': 'message is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        users = User.objects.filter(pk__in=user_ids)
        if not users.exists():
            return Response(
                {'error': 'No valid users found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        created = [
            FraudNotification.objects.create(
                user=u,
                notification_type=notif_type,
                message=message,
                metadata=metadata,
            )
            for u in users
        ]
        serializer = FraudNotificationSerializer(created, many=True)
        return Response(
            {'sent_count': len(created), 'notifications': serializer.data},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = FraudNotification.objects.filter(
            user=request.user, read_at__isnull=True
        ).count()
        return Response({'unread_count': count})


# =============================================================================
# 5. FraudCaseEvidenceViewSet
# =============================================================================

class FraudCaseEvidenceViewSet(viewsets.ModelViewSet):
    """Evidence attached to fraud cases."""
    serializer_class = FraudCaseEvidenceFullSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['fraud_case', 'evidence_type']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = FraudCaseEvidence.objects.select_related('fraud_case', 'added_by').all()
        if not self.request.user.is_staff:
            qs = qs.filter(fraud_case__user=self.request.user)
        case_id = self.request.query_params.get('case_id')
        if case_id:
            qs = qs.filter(fraud_case_id=case_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(added_by=self.request.user)

    @action(detail=False, methods=['post'], url_path='bulk-upload')
    def bulk_upload(self, request):
        """Create multiple evidence items.  Body: { "items": [{...}, ...] }"""
        try:
            items = request.data.get('items', [])
            if not isinstance(items, list) or not items:
                return Response(
                    {'error': 'items must be a non-empty list.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            created, errors = [], []
            for idx, item in enumerate(items):
                serializer = self.get_serializer(data=item)
                if serializer.is_valid():
                    obj = serializer.save(added_by=request.user)
                    created.append(obj.pk)
                else:
                    errors.append({'index': idx, 'errors': serializer.errors})
            resp_status = status.HTTP_207_MULTI_STATUS if errors else status.HTTP_201_CREATED
            return Response(
                {'created': len(created), 'ids': created, 'errors': errors},
                status=resp_status,
            )
        except Exception as exc:
            logger.exception("bulk_upload failed: %s", exc)
            return Response(
                {'error': 'Bulk evidence upload failed.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =============================================================================
# 6. FraudCaseActionViewSet
# =============================================================================

class FraudCaseActionViewSet(viewsets.ModelViewSet):
    """Actions taken on fraud cases."""
    serializer_class = FraudCaseActionFullSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['fraud_case', 'action_type', 'is_completed']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = FraudCaseAction.objects.select_related('fraud_case', 'performed_by').all()
        case_id = self.request.query_params.get('case_id')
        if case_id:
            qs = qs.filter(fraud_case_id=case_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(performed_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='complete')
    def complete_action(self, request, pk=None):
        action_obj = self.get_object()
        action_obj.is_completed = True
        action_obj.save(update_fields=['is_completed', 'updated_at'])
        return Response({'status': 'completed', 'id': action_obj.id})

    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """Create multiple case actions.  Body: { "actions": [{...}, ...] }"""
        try:
            actions_data = request.data.get('actions', [])
            if not isinstance(actions_data, list) or not actions_data:
                return Response(
                    {'error': 'actions must be a non-empty list.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            created, errors = [], []
            for idx, action_data in enumerate(actions_data):
                serializer = self.get_serializer(data=action_data)
                if serializer.is_valid():
                    obj = serializer.save(performed_by=request.user)
                    created.append(obj.pk)
                else:
                    errors.append({'index': idx, 'errors': serializer.errors})
            resp_status = status.HTTP_207_MULTI_STATUS if errors else status.HTTP_201_CREATED
            return Response(
                {'created': len(created), 'ids': created, 'errors': errors},
                status=resp_status,
            )
        except Exception as exc:
            logger.exception("bulk_create failed: %s", exc)
            return Response(
                {'error': 'Bulk action create failed.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =============================================================================
# 7. DeviceFingerprintViewSet
# =============================================================================

class DeviceFingerprintViewSet(viewsets.ModelViewSet):
    """Device fingerprint management."""
    queryset = DeviceFingerprint.objects.all().order_by('-created_at')
    serializer_class = DeviceFingerprintSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['user', 'is_trusted', 'device_type', 'browser']
    search_fields = ['fingerprint_hash', 'device_id', 'user_agent']
    ordering_fields = ['created_at', 'trust_score', 'last_seen']

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    @action(detail=True, methods=['post'], url_path='trust')
    def mark_trusted(self, request, pk=None):
        device = self.get_object()
        device.is_trusted = True
        device.trust_score = 100
        device.save(update_fields=['is_trusted', 'trust_score', 'updated_at'])
        logger.info("Device %s trusted by %s", device.id, request.user)
        return Response({'status': 'trusted', 'device_id': device.id})

    @action(detail=True, methods=['post'], url_path='untrust')
    def mark_untrusted(self, request, pk=None):
        device = self.get_object()
        device.is_trusted = False
        device.save(update_fields=['is_trusted', 'updated_at'])
        return Response({'status': 'untrusted', 'device_id': device.id})

    @action(detail=False, methods=['get'], url_path='suspicious')
    def suspicious_devices(self, request):
        qs = self.get_queryset().filter(trust_score__lt=30, is_trusted=False)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='bulk-verify')
    def bulk_verify(self, request):
        """Mark multiple devices as verified.  Body: { "device_ids": [1, 2, 3] }"""
        try:
            device_ids = request.data.get('device_ids', [])
            if not isinstance(device_ids, list) or not device_ids:
                return Response(
                    {'error': 'device_ids must be a non-empty list.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            updated = DeviceFingerprint.objects.filter(
                id__in=device_ids
            ).update(trust_score=100, is_bot=False)
            return Response(
                {'updated': updated, 'device_ids': device_ids},
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            logger.exception("bulk_verify failed: %s", exc)
            return Response(
                {'error': 'Bulk verify failed.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =============================================================================
# 8. IPReputationViewSet
# =============================================================================

class IPReputationViewSet(viewsets.ModelViewSet):
    """IP address reputation management."""
    queryset = IPReputation.objects.all().order_by('-updated_at')
    serializer_class = IPReputationSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_vpn', 'is_proxy', 'is_tor', 'is_datacenter', 'threat_level']
    search_fields = ['ip_address', 'country_code', 'isp']
    ordering_fields = ['fraud_score', 'request_count', 'updated_at']

    @action(detail=False, methods=['get'], url_path='high-risk')
    def high_risk(self, request):
        """IPs with fraud_score >= 70."""
        qs = self.get_queryset().filter(fraud_score__gte=70).order_by('-fraud_score')
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=['post'], url_path='lookup')
    def lookup(self, request):
        ip = request.data.get('ip_address')
        if not ip:
            return Response({'error': 'ip_address required'}, status=400)
        try:
            rep = IPReputation.objects.get(ip_address=ip)
            return Response(IPReputationSerializer(rep).data)
        except IPReputation.DoesNotExist:
            return Response({'ip_address': ip, 'known': False, 'fraud_score': 0})

    @action(detail=False, methods=['post'], url_path='bulk-check')
    def bulk_check(self, request):
        """Return reputation data for a list of IPs.
        Body: { "ip_addresses": ["1.2.3.4", "5.6.7.8"] }"""
        try:
            ips = request.data.get('ip_addresses', [])
            if not isinstance(ips, list) or not ips:
                return Response(
                    {'error': 'ip_addresses must be a non-empty list.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            records = IPReputation.objects.filter(ip_address__in=ips)
            serializer = self.get_serializer(records, many=True)
            found = {r['ip_address'] for r in serializer.data}
            missing = [ip for ip in ips if ip not in found]
            return Response(
                {'results': serializer.data, 'found': len(serializer.data), 'missing': missing},
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            logger.exception("bulk_check failed: %s", exc)
            return Response(
                {'error': 'Bulk IP check failed.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(
        detail=False, methods=['post'], url_path='blacklist',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def bulk_blacklist(self, request):
        """Blacklist multiple IPs.
        Body: { "ip_addresses": [...], "reason": "..." }"""
        try:
            ips = request.data.get('ip_addresses', [])
            reason = request.data.get('reason', '').strip()
            if not isinstance(ips, list) or not ips:
                return Response(
                    {'error': 'ip_addresses must be a non-empty list.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not reason:
                return Response(
                    {'error': 'reason is required for blacklisting.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            updated = IPReputation.objects.filter(ip_address__in=ips).update(
                is_blacklisted=True,
                blacklist_reason=reason,
                blacklisted_at=timezone.now(),
            )
            logger.info("User %s bulk-blacklisted %d IPs: %s", request.user, updated, ips)
            return Response(
                {'blacklisted': updated, 'ip_addresses': ips},
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            logger.exception("bulk_blacklist failed: %s", exc)
            return Response(
                {'error': 'Bulk blacklist failed.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =============================================================================
# 9. OfferCompletionViewSet
# =============================================================================

class OfferCompletionViewSet(viewsets.ModelViewSet):
    """Track and manage offer completions & reward crediting."""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'is_fraud', 'user']
    ordering_fields = ['tracked_at', 'completed_at', 'reward_amount']
    ordering = ['-tracked_at']

    def get_queryset(self):
        qs = OfferCompletion.objects.select_related('user', 'offer', 'transaction').all()
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return OfferCompletionCreateSerializer
        return OfferCompletionSerializer

    @action(detail=True, methods=['post'], url_path='approve-reward')
    def approve_reward(self, request, pk=None):
        """Manually approve and credit reward to wallet."""
        completion = self.get_object()

        if completion.status == 'completed' and not completion.is_fraud:
            return Response({'detail': 'Already credited.'}, status=400)
        if completion.is_fraud:
            return Response({'detail': 'Cannot approve fraudulent completion.'}, status=400)

        try:
            from api.wallet.models import WalletTransaction
            txn = WalletTransaction.objects.create(
                user=completion.user,
                transaction_type='credit',
                amount=completion.reward_amount,
                description=f'Offer reward: {completion.offer_id}',
                status='completed',
                metadata={'offer_completion_id': completion.id},
            )
            completion.transaction = txn
            completion.status = 'completed'
            completion.completed_at = timezone.now()
            completion.reviewed_by = request.user
            completion.reviewed_at = timezone.now()
            completion.save(update_fields=[
                'transaction', 'status', 'completed_at',
                'reviewed_by', 'reviewed_at',
            ])
            logger.info(
                "Reward credited: user=%s offer=%s amount=%s txn=%s",
                completion.user_id, completion.offer_id,
                completion.reward_amount, txn.id,
            )
            return Response({
                'status': 'credited',
                'reward_amount': str(completion.reward_amount),
                'transaction_id': txn.id,
            })
        except Exception as exc:
            logger.error("approve_reward failed: %s", exc)
            return Response({'error': str(exc)}, status=500)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        completion = self.get_object()
        reason = request.data.get('reason', '')
        completion.status = 'rejected'
        completion.is_fraud = True
        completion.fraud_reason = reason
        completion.reviewed_by = request.user
        completion.reviewed_at = timezone.now()
        completion.save(update_fields=[
            'status', 'is_fraud', 'fraud_reason', 'reviewed_by', 'reviewed_at',
        ])
        return Response({'status': 'rejected', 'id': completion.id})

    @action(detail=False, methods=['get'], url_path='pending-review')
    def pending_review(self, request):
        qs = self.get_queryset().filter(status='pending', is_fraud=False)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='fraud')
    def fraud_analysis(self, request):
        """Summary statistics for fraudulent offer completions."""
        try:
            qs = self.get_queryset().filter(is_fraud=True)
            total_fraud = qs.count()
            total_all = self.get_queryset().count()
            fraud_by_status = dict(
                qs.values('status').annotate(n=Count('id')).values_list('status', 'n')
            )
            top_reasons = list(
                qs.exclude(fraud_reason='').values('fraud_reason')
                .annotate(n=Count('id')).order_by('-n')[:10]
            )
            return Response({
                'total_fraud': total_fraud,
                'total_completions': total_all,
                'fraud_rate': round(total_fraud / total_all, 4) if total_all else 0,
                'by_status': fraud_by_status,
                'top_reasons': top_reasons,
            }, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.exception("fraud_analysis failed: %s", exc)
            return Response(
                {'error': 'Fraud analysis failed.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# =============================================================================
# 10. FraudAnalyticsAPIView
# =============================================================================

class FraudAnalyticsAPIView(APIView):
    """Aggregated fraud analytics dashboard data."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        since = timezone.now() - timedelta(days=days)
        cache_key = f"fraud_analytics_{days}d"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        attempts = FraudAttempt.objects.filter(created_at__gte=since)
        data = {
            'period_days': days,
            'total_attempts': attempts.count(),
            'flagged': attempts.filter(status='flagged').count(),
            'blocked': attempts.filter(status='blocked').count(),
            'resolved': attempts.filter(status='resolved').count(),
            'avg_risk_score': attempts.aggregate(avg=Avg('risk_score'))['avg'] or 0,
            'by_type': list(
                attempts.values('attempt_type')
                .annotate(count=Count('id'), avg_score=Avg('risk_score'))
                .order_by('-count')[:10]
            ),
            'daily_trend': list(
                attempts
                .annotate(day=TruncDay('created_at'))
                .values('day')
                .annotate(count=Count('id'), avg_score=Avg('risk_score'))
                .order_by('day')
            ),
            'top_risk_users': list(
                UserRiskProfile.objects.order_by('-risk_score')
                .values('user_id', 'risk_score', 'risk_level')[:10]
            ),
            'open_cases': FraudCase.objects.filter(
                status__in=['open', 'investigating']
            ).count(),
            'alerts_today': FraudAlert.objects.filter(
                created_at__date=timezone.now().date()
            ).count(),
        }
        cache.set(cache_key, data, timeout=300)
        return Response(data)


# =============================================================================
# 11. GeographicAnalysisAPIView
# =============================================================================

class GeographicAnalysisAPIView(APIView):
    """Fraud attempts by country/region."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        since = timezone.now() - timedelta(days=days)

        by_country = (
            FraudAttempt.objects
            .filter(created_at__gte=since, country_code__isnull=False)
            .values('country_code')
            .annotate(
                attempt_count=Count('id'),
                avg_risk=Avg('risk_score'),
                blocked_count=Count('id', filter=Q(status='blocked')),
            )
            .order_by('-attempt_count')[:30]
        )
        by_ip_type = (
            IPReputation.objects
            .values('is_vpn', 'is_proxy', 'is_tor', 'is_datacenter')
            .annotate(count=Count('id'), avg_fraud=Avg('fraud_score'))
        )
        return Response({
            'period_days': days,
            'by_country': list(by_country),
            'ip_type_breakdown': list(by_ip_type),
        })


# =============================================================================
# 12. RiskTimelineAPIView
# =============================================================================

class RiskTimelineAPIView(APIView):
    """Hourly/daily risk score timeline for a user or global."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.query_params.get('user_id')
        granularity = request.query_params.get('granularity', 'daily')  # hourly | daily
        days = int(request.query_params.get('days', 7))
        since = timezone.now() - timedelta(days=days)

        qs = FraudAttempt.objects.filter(created_at__gte=since)
        if user_id:
            if not request.user.is_staff and str(request.user.id) != str(user_id):
                return Response({'error': 'Permission denied'}, status=403)
            qs = qs.filter(user_id=user_id)

        trunc_fn = TruncHour if granularity == 'hourly' else TruncDay
        timeline = (
            qs.annotate(period=trunc_fn('created_at'))
            .values('period')
            .annotate(
                count=Count('id'),
                avg_score=Avg('risk_score'),
                flagged=Count('id', filter=Q(status='flagged')),
                blocked=Count('id', filter=Q(status='blocked')),
            )
            .order_by('period')
        )
        return Response({
            'user_id': user_id,
            'granularity': granularity,
            'period_days': days,
            'timeline': list(timeline),
        })


# =============================================================================
# 13. IntegrityVerificationAPIView
# =============================================================================

class IntegrityVerificationAPIView(APIView):
    """Verify blockchain-style hash chain integrity of fraud records."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        model_name = request.data.get('model', 'FraudCase')
        record_id  = request.data.get('id')

        model_map = {
            'FraudCase':         FraudCase,
            'FraudCaseEvidence': FraudCaseEvidence,
            'FraudCaseAction':   FraudCaseAction,
            'FraudWhitelist':    FraudWhitelist,
            'FraudNotification': FraudNotification,
        }
        Model = model_map.get(model_name)
        if not Model:
            return Response({'error': f'Unknown model: {model_name}'}, status=400)

        try:
            record = Model.objects.get(pk=record_id)
        except Model.DoesNotExist:
            return Response({'error': 'Record not found'}, status=404)

        data_str = f"{record.previous_hash}{record.pk}{record.created_at.isoformat()}"
        expected = hashlib.sha256(data_str.encode()).hexdigest()
        stored   = getattr(record, 'integrity_hash', None)
        matches  = (stored == expected)

        return Response({
            'model':    model_name,
            'id':       record_id,
            'valid':    matches,
            'stored':   stored,
            'expected': expected,
            'message':  'Integrity OK' if matches else 'HASH MISMATCH — record may have been tampered',
        })


# =============================================================================
# 14. SystemHealthAPIView
# =============================================================================

class SystemHealthAPIView(APIView):
    """Fraud detection system health indicators."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        now       = timezone.now()
        last_hour = now - timedelta(hours=1)
        last_day  = now - timedelta(hours=24)

        try:
            from api.fraud_detection.services.FraudScoreCalculator import FraudScoreCalculator  # noqa: F401
            calc_ok = True
        except Exception:
            calc_ok = False

        data = {
            'status': 'healthy',
            'timestamp': now.isoformat(),
            'fraud_engine': {
                'calculator_loaded':   calc_ok,
                'attempts_last_hour':  FraudAttempt.objects.filter(created_at__gte=last_hour).count(),
                'attempts_last_24h':   FraudAttempt.objects.filter(created_at__gte=last_day).count(),
                'open_cases':          FraudCase.objects.filter(status='open').count(),
                'unread_alerts':       FraudAlert.objects.filter(is_read=False).count(),
            },
            'queue': {
                'pending_offer_completions': OfferCompletion.objects.filter(status='pending').count(),
                'pending_reviews':           FraudCase.objects.filter(status='investigating').count(),
            },
            'settings': {
                'vpn_blocked':    FraudSettings.objects.filter(pk=1).values_list('block_vpn', flat=True).first(),
                'risk_threshold': FraudSettings.objects.filter(pk=1).values_list('global_risk_threshold', flat=True).first(),
            },
        }
        return Response(data)


# =============================================================================
# 15. fraud_statistics — function-based view
# =============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def fraud_statistics(request):
    """Quick summary statistics for dashboard widgets."""
    today    = timezone.now().date()
    week_ago = timezone.now() - timedelta(days=7)

    stats = {
        'today': {
            'attempts':    FraudAttempt.objects.filter(created_at__date=today).count(),
            'alerts':      FraudAlert.objects.filter(created_at__date=today).count(),
            'completions': OfferCompletion.objects.filter(tracked_at__date=today).count(),
            'fraudulent':  OfferCompletion.objects.filter(tracked_at__date=today, is_fraud=True).count(),
        },
        'week': {
            'attempts':  FraudAttempt.objects.filter(created_at__gte=week_ago).count(),
            'new_cases': FraudCase.objects.filter(opened_at__gte=week_ago).count(),
            'bans':      UserRiskProfile.objects.filter(
                             updated_at__gte=week_ago, risk_level='critical'
                         ).count(),
            'avg_score': FraudAttempt.objects.filter(
                             created_at__gte=week_ago
                         ).aggregate(avg=Avg('risk_score'))['avg'] or 0,
        },
        'totals': {
            'rules':         FraudPattern.objects.filter(is_active=True).count(),
            'whitelist':     FraudWhitelist.objects.filter(is_active=True).count(),
            'risk_profiles': UserRiskProfile.objects.count(),
            'open_cases':    FraudCase.objects.filter(status__in=['open', 'investigating']).count(),
        },
    }
    return Response(stats)


# =============================================================================
# 16. quick_fraud_check — function-based view
# =============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def quick_fraud_check(request):
    """
    Lightweight real-time fraud check for a user + IP + device triple.
    Returns risk score and recommendation without persisting.
    """
    user_id     = request.data.get('user_id', request.user.id)
    ip_address  = request.data.get('ip_address', '')
    device_id   = request.data.get('device_id', '')
    action_type = request.data.get('action', 'general')

    if not request.user.is_staff and str(user_id) != str(request.user.id):
        return Response({'error': 'Permission denied'}, status=403)

    risk_score   = 0
    risk_factors = []

    # 1. User risk profile
    try:
        profile = UserRiskProfile.objects.get(user_id=user_id)
        risk_score = max(risk_score, profile.risk_score)
        if profile.risk_score >= 70:
            risk_factors.append({'factor': 'user_risk_profile', 'score': profile.risk_score})
    except UserRiskProfile.DoesNotExist:
        pass

    # 2. IP reputation
    if ip_address:
        try:
            ip_rep = IPReputation.objects.get(ip_address=ip_address)
            if ip_rep.fraud_score >= 60:
                risk_score = min(100, risk_score + ip_rep.fraud_score // 3)
                risk_factors.append({
                    'factor':   'ip_reputation',
                    'score':    ip_rep.fraud_score,
                    'is_vpn':   ip_rep.is_vpn,
                    'is_proxy': ip_rep.is_proxy,
                })
        except IPReputation.DoesNotExist:
            pass

    # 3. Device trust
    if device_id:
        try:
            device = DeviceFingerprint.objects.get(device_id=device_id, user_id=user_id)
            if not device.is_trusted and device.trust_score < 30:
                risk_score = min(100, risk_score + 20)
                risk_factors.append({'factor': 'untrusted_device', 'trust_score': device.trust_score})
        except DeviceFingerprint.DoesNotExist:
            risk_factors.append({'factor': 'unknown_device'})
            risk_score = min(100, risk_score + 10)

    recommendation = 'allow'
    if risk_score >= 90:
        recommendation = 'block'
    elif risk_score >= 70:
        recommendation = 'challenge'
    elif risk_score >= 40:
        recommendation = 'monitor'

    return Response({
        'user_id':        user_id,
        'risk_score':     risk_score,
        'recommendation': recommendation,
        'risk_factors':   risk_factors,
        'action':         action_type,
        'checked_at':     timezone.now().isoformat(),
    })


# =============================================================================
# PHANTOM ROUTE FIXES (was phantom_route_fixes.py — now applied here, DRY)
# These @action methods were registered in urls.py but missing from ViewSets.
# =============================================================================

# ── Patch: add to FraudPatternViewSet ────────────────────────────────────────
from rest_framework.decorators import action as _action

def _patch_viewsets():
    """Apply phantom route fixes to ViewSet classes after they are defined."""
    from rest_framework.response import Response as _R
    from rest_framework import status as _s

    # FraudPatternViewSet.accuracy_stats
    if not hasattr(FraudPatternViewSet, 'accuracy_stats'):
        @_action(detail=False, methods=['get'], url_path='accuracy')
        def accuracy_stats(self, request):
            qs = self.get_queryset()
            correct  = qs.filter(is_active=True).count()
            total    = qs.count()
            return _R({"accuracy": correct / total if total else 0, "total_patterns": total})
        FraudPatternViewSet.accuracy_stats = accuracy_stats

    # DeviceFingerprintViewSet.bulk_verify
    if not hasattr(DeviceFingerprintViewSet, 'bulk_verify'):
        @_action(detail=False, methods=['post'], url_path='bulk-verify')
        def bulk_verify(self, request):
            device_ids = request.data.get("device_ids", [])
            verified   = 0
            for did in device_ids:
                try:
                    from api.fraud_detection.models import DeviceFingerprint
                    DeviceFingerprint.objects.filter(device_id=did).update(is_verified=True)
                    verified += 1
                except Exception:
                    pass
            return _R({"verified": verified, "total": len(device_ids)})
        DeviceFingerprintViewSet.bulk_verify = bulk_verify

    # IPReputationViewSet.bulk_check
    if not hasattr(IPReputationViewSet, 'bulk_check'):
        @_action(detail=False, methods=['post'], url_path='bulk-check')
        def bulk_check(self, request):
            from api.fraud_detection.services import get_ip_reputation_service
            results = get_ip_reputation_service().bulk_check(request.data.get("ips", []))
            return _R({"results": results})
        IPReputationViewSet.bulk_check = bulk_check

    # IPReputationViewSet.bulk_blacklist
    if not hasattr(IPReputationViewSet, 'bulk_blacklist'):
        @_action(detail=False, methods=['post'], url_path='bulk-blacklist')
        def bulk_blacklist(self, request):
            ips     = request.data.get("ips", [])
            reason  = request.data.get("reason", "manual")
            from api.fraud_detection.models import IPReputation
            updated = IPReputation.objects.filter(ip_address__in=ips).update(
                reputation_score=0, is_blacklisted=True, blacklist_reason=reason
            )
            return _R({"blacklisted": updated})
        IPReputationViewSet.bulk_blacklist = bulk_blacklist

    # OfferCompletionViewSet.fraud_analysis
    if not hasattr(OfferCompletionViewSet, 'fraud_analysis'):
        @_action(detail=False, methods=['get'], url_path='fraud')
        def fraud_analysis(self, request):
            from api.fraud_detection.analytics import FraudAnalyticsEngine
            return _R(FraudAnalyticsEngine().get_offer_fraud_stats())
        OfferCompletionViewSet.fraud_analysis = fraud_analysis

    # FraudCaseEvidenceViewSet.bulk_upload
    if not hasattr(FraudCaseEvidenceViewSet, 'bulk_upload'):
        @_action(detail=False, methods=['post'], url_path='bulk-upload')
        def bulk_upload(self, request):
            items    = request.data.get("evidence_items", [])
            created  = 0
            from api.fraud_detection.serializers import FraudCaseEvidenceSerializer
            for item in items:
                s = FraudCaseEvidenceSerializer(data=item)
                if s.is_valid():
                    s.save()
                    created += 1
            return _R({"created": created, "submitted": len(items)},
                      status=_s.HTTP_201_CREATED)
        FraudCaseEvidenceViewSet.bulk_upload = bulk_upload

    # FraudCaseActionViewSet.bulk_create
    if not hasattr(FraudCaseActionViewSet, 'bulk_create'):
        @_action(detail=False, methods=['post'], url_path='bulk-create')
        def bulk_create(self, request):
            items   = request.data.get("actions", [])
            created = 0
            from api.fraud_detection.serializers import FraudCaseActionSerializer
            for item in items:
                s = FraudCaseActionSerializer(data=item)
                if s.is_valid():
                    s.save(performed_by=request.user)
                    created += 1
            return _R({"created": created}, status=_s.HTTP_201_CREATED)
        FraudCaseActionViewSet.bulk_create = bulk_create


# Apply patches at module load time
_patch_viewsets()

# phantom_route_fixes.py is now a DRY shim
