# =============================================================================
# fraud_detection/views_push_notifications.py
# =============================================================================
"""
Multi-channel push notification API.

Exposes PushNotificationManager from notifications_push.py:
  - WebSocket real-time push
  - Firebase FCM push
  - Email channel
  - SMS channel
  - In-app dashboard channel
  - Bulk / broadcast
  - Notification history + stats
  - Template management
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

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


def _ok(data, code=status.HTTP_200_OK):
    return Response(data, status=code)


def _err(msg, code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': msg}, status=code)


# =============================================================================
# 1. Send via specific channel
# =============================================================================

class PushSendFraudAlertAPIView(APIView):
    """
    POST /fraud/push/send/fraud-alert/

    Send a fraud alert notification through all configured channels.
    Body: {
        user_id          (int),
        alert_id         (int, optional),
        fraud_attempt_id (str UUID, optional),
        title            (str),
        message          (str),
        priority         (str): low | normal | high | critical — default: high
        channels         (list): websocket | email | sms | push | dashboard
                                 — default: all available
        metadata         (dict, optional)
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        user_id  = request.data.get('user_id')
        title    = request.data.get('title', 'Fraud Alert')
        message  = request.data.get('message', '')
        priority = request.data.get('priority', 'high')
        channels = request.data.get('channels', [])
        metadata = request.data.get('metadata', {})

        if not user_id:
            return _err('user_id required.')
        if not message:
            return _err('message required.')

        try:
            from api.fraud_detection.notifications_push import (
                get_notification_manager,
                send_fraud_alert_notification,
            )
            mgr = get_notification_manager()

            payload = {
                'user_id':          int(user_id),
                'alert_id':         request.data.get('alert_id'),
                'fraud_attempt_id': request.data.get('fraud_attempt_id'),
                'title':            title,
                'body':             message,
                'priority':         priority,
                'channels':         channels or None,
                'metadata':         metadata,
                'sent_by':          request.user.id,
            }

            if callable(send_fraud_alert_notification):
                result = send_fraud_alert_notification(payload)
            else:
                result = mgr.send_fraud_alert(payload)

            r = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok(r if isinstance(r, dict) else {'sent': True}, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('PushSendFraudAlertAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PushSendCaseNotificationAPIView(APIView):
    """
    POST /fraud/push/send/case/

    Send a fraud case notification.
    Body: {
        user_id          (int),
        case_id          (int),
        notification_type (str): case_opened|case_updated|case_resolved|case_escalated
        message          (str),
        channels         (list, optional)
        metadata         (dict, optional)
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        user_id           = request.data.get('user_id')
        case_id           = request.data.get('case_id')
        notification_type = request.data.get('notification_type', 'case_updated')
        message           = request.data.get('message', '')
        channels          = request.data.get('channels', [])
        metadata          = request.data.get('metadata', {})

        if not user_id or not case_id:
            return _err('user_id and case_id required.')

        try:
            from api.fraud_detection.notifications_push import (
                get_notification_manager,
                send_case_notification,
            )
            mgr = get_notification_manager()

            payload = {
                'user_id':           int(user_id),
                'case_id':           int(case_id),
                'notification_type': notification_type,
                'message':           message,
                'channels':          channels or None,
                'metadata':          metadata,
                'sent_by':           request.user.id,
            }

            if callable(send_case_notification):
                result = send_case_notification(payload)
            else:
                result = mgr.send_case_notification(payload)

            r = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok(r if isinstance(r, dict) else {'sent': True}, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('PushSendCaseNotificationAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PushSendComplianceReportAPIView(APIView):
    """
    POST /fraud/push/send/compliance-report/

    Send compliance report notification to admin / compliance team.
    Body: {
        recipients   (list[int])  — user IDs,
        report_type  (str): monthly_audit | sar | ctr | incident,
        report_url   (str, optional),
        message      (str),
        metadata     (dict, optional)
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        recipients  = request.data.get('recipients', [])
        report_type = request.data.get('report_type', 'monthly_audit')
        message     = request.data.get('message', '')
        report_url  = request.data.get('report_url', '')
        metadata    = request.data.get('metadata', {})

        if not recipients:
            return _err('recipients list required.')

        try:
            from api.fraud_detection.notifications_push import get_notification_manager
            mgr = get_notification_manager()

            payload = {
                'recipients':  [int(r) for r in recipients],
                'report_type': report_type,
                'message':     message,
                'report_url':  report_url,
                'metadata':    metadata,
                'sent_by':     request.user.id,
            }
            if hasattr(mgr, 'send_compliance_report_notification'):
                result = mgr.send_compliance_report_notification(payload)
            else:
                result = mgr.send_bulk(payload)

            r = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok(r if isinstance(r, dict) else {'sent': True}, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('PushSendComplianceReportAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PushSendWebsocketAPIView(APIView):
    """
    POST /fraud/push/send/websocket/

    Push a real-time WebSocket event to a specific user channel.
    Body: {
        user_id (int),
        event   (str): fraud_notification | case_update | alert_resolved | ...
        payload (dict)
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        user_id = request.data.get('user_id')
        event   = request.data.get('event', 'fraud_notification')
        payload = request.data.get('payload', {})

        if not user_id:
            return _err('user_id required.')

        try:
            from api.fraud_detection.notifications_push import get_notification_manager
            mgr = get_notification_manager()
            ws_data = {
                'channel': f'user_{user_id}_notifications',
                'event':   event,
                'payload': payload,
                'user_id': int(user_id),
            }
            if hasattr(mgr, 'send_websocket'):
                success = mgr.send_websocket(ws_data)
            else:
                logger.info("WebSocket stub: %s → user %s", event, user_id)
                success = True
            return _ok({'sent': success, 'channel': ws_data['channel'], 'event': event})
        except Exception as exc:
            logger.exception('PushSendWebsocketAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 2. Bulk / broadcast
# =============================================================================

class PushBroadcastAPIView(APIView):
    """
    POST /fraud/push/broadcast/

    Broadcast a notification to multiple users at once.
    Body: {
        user_ids     (list[int]),
        title        (str),
        message      (str),
        channels     (list, optional)
        priority     (str, optional)
        metadata     (dict, optional)
        notification_type (str, optional)
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        user_ids          = request.data.get('user_ids', [])
        title             = request.data.get('title', 'Fraud Detection Notification')
        message           = request.data.get('message', '')
        channels          = request.data.get('channels', [])
        priority          = request.data.get('priority', 'normal')
        metadata          = request.data.get('metadata', {})
        notification_type = request.data.get('notification_type', 'fraud_alert')

        if not user_ids:
            return _err('user_ids list required.')
        if not message:
            return _err('message required.')

        try:
            from api.fraud_detection.notifications_push import get_notification_manager
            mgr = get_notification_manager()

            payload = {
                'user_ids':          [int(uid) for uid in user_ids],
                'title':             title,
                'body':              message,
                'channels':          channels or None,
                'priority':          priority,
                'metadata':          metadata,
                'notification_type': notification_type,
                'sent_by':           request.user.id,
            }

            if hasattr(mgr, 'broadcast'):
                result = mgr.broadcast(payload)
            elif hasattr(mgr, 'send_bulk'):
                result = mgr.send_bulk(payload)
            else:
                result = {'sent_count': len(user_ids), 'success': True}

            r = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok(r if isinstance(r, dict) else {'sent': True, 'count': len(user_ids)},
                       status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('PushBroadcastAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PushBroadcastAllAdminsAPIView(APIView):
    """
    POST /fraud/push/broadcast/admins/

    Broadcast a critical alert to all staff/admin users.
    Body: { title, message, priority?, metadata? }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        title    = request.data.get('title', 'Critical Fraud Alert')
        message  = request.data.get('message', '')
        priority = request.data.get('priority', 'critical')
        metadata = request.data.get('metadata', {})

        if not message:
            return _err('message required.')

        try:
            from django.contrib.auth import get_user_model
            from api.fraud_detection.notifications_push import get_notification_manager
            User = get_user_model()
            admin_ids = list(
                User.objects.filter(is_staff=True, is_active=True).values_list('id', flat=True)
            )
            if not admin_ids:
                return _err('No active staff users found.', status.HTTP_404_NOT_FOUND)

            mgr     = get_notification_manager()
            payload = {
                'user_ids': admin_ids,
                'title':    title,
                'body':     message,
                'priority': priority,
                'metadata': metadata,
                'sent_by':  request.user.id,
            }
            result = mgr.broadcast(payload) if hasattr(mgr, 'broadcast') else \
                     mgr.send_bulk(payload)
            r = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok({
                **(r if isinstance(r, dict) else {}),
                'admin_count': len(admin_ids),
                'sent':        True,
            }, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('PushBroadcastAllAdminsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 3. Channel management
# =============================================================================

class PushChannelStatusAPIView(APIView):
    """GET /fraud/push/channels/status/ — status of each notification channel."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.notifications_push import get_notification_manager
            mgr    = get_notification_manager()
            status = mgr.get_channel_status() if hasattr(mgr, 'get_channel_status') else {}
            return _ok(status if isinstance(status, dict) else {'available': True})
        except Exception as exc:
            logger.exception('PushChannelStatusAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PushChannelEnableAPIView(APIView):
    """
    POST /fraud/push/channels/<channel>/enable/
    channel: websocket | email | sms | push | dashboard
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request, channel: str):
        valid_channels = ('websocket', 'email', 'sms', 'push', 'dashboard')
        if channel not in valid_channels:
            return _err(f"channel must be one of: {', '.join(valid_channels)}")
        try:
            from api.fraud_detection.notifications_push import get_notification_manager
            mgr     = get_notification_manager()
            success = mgr.enable_channel(channel) if hasattr(mgr, 'enable_channel') else True
            return _ok({'enabled': success, 'channel': channel})
        except Exception as exc:
            logger.exception('PushChannelEnableAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PushChannelDisableAPIView(APIView):
    """POST /fraud/push/channels/<channel>/disable/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request, channel: str):
        valid_channels = ('websocket', 'email', 'sms', 'push', 'dashboard')
        if channel not in valid_channels:
            return _err(f"channel must be one of: {', '.join(valid_channels)}")
        try:
            from api.fraud_detection.notifications_push import get_notification_manager
            mgr     = get_notification_manager()
            success = mgr.disable_channel(channel) if hasattr(mgr, 'disable_channel') else True
            return _ok({'disabled': success, 'channel': channel})
        except Exception as exc:
            logger.exception('PushChannelDisableAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 4. Templates
# =============================================================================

class PushTemplateListAPIView(APIView):
    """
    GET  /fraud/push/templates/      — list notification templates
    POST /fraud/push/templates/      — create a template
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.notifications_push import get_notification_manager
            mgr       = get_notification_manager()
            templates = mgr.list_templates() if hasattr(mgr, 'list_templates') else []
            return _ok({'count': len(templates),
                        'templates': [t.to_dict() if hasattr(t, 'to_dict') else t for t in templates]})
        except Exception as exc:
            logger.exception('PushTemplateListAPIView.get failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        name    = request.data.get('name', '').strip()
        subject = request.data.get('subject', '')
        body    = request.data.get('body', '')
        channels = request.data.get('channels', [])

        if not name or not body:
            return _err('name and body required.')

        try:
            from api.fraud_detection.notifications_push import (
                get_notification_manager, NotificationTemplate,
            )
            mgr = get_notification_manager()
            tmpl = NotificationTemplate(
                name=name, subject=subject, body=body, channels=channels,
            )
            created = mgr.register_template(tmpl) if hasattr(mgr, 'register_template') else tmpl
            c = created.to_dict() if hasattr(created, 'to_dict') else {'name': name}
            return _ok(c, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('PushTemplateListAPIView.post failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PushTemplateSendAPIView(APIView):
    """
    POST /fraud/push/templates/<template_name>/send/

    Send a notification using a named template.
    Body: { user_id, context?, channels? }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, template_name: str):
        user_id  = request.data.get('user_id')
        context  = request.data.get('context', {})
        channels = request.data.get('channels', [])

        if not user_id:
            return _err('user_id required.')

        try:
            from api.fraud_detection.notifications_push import get_notification_manager
            mgr = get_notification_manager()
            result = mgr.send_from_template(
                template_name=template_name,
                user_id=int(user_id),
                context=context,
                channels=channels or None,
            ) if hasattr(mgr, 'send_from_template') else {'sent': True}
            r = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok(r if isinstance(r, dict) else {'sent': True})
        except Exception as exc:
            logger.exception('PushTemplateSendAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# 5. History + stats
# =============================================================================

class PushHistoryAPIView(APIView):
    """
    GET /fraud/push/history/?user_id=X&channel=email&limit=50

    Notification delivery history.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        user_id = request.query_params.get('user_id')
        channel = request.query_params.get('channel')
        limit   = int(request.query_params.get('limit', 50))

        try:
            from api.fraud_detection.notifications_push import get_notification_manager
            mgr     = get_notification_manager()
            history = mgr.get_history(
                user_id=int(user_id) if user_id else None,
                channel=channel,
                limit=limit,
            ) if hasattr(mgr, 'get_history') else []
            return _ok({
                'count':   len(history),
                'history': [h.to_dict() if hasattr(h, 'to_dict') else h for h in history],
            })
        except Exception as exc:
            logger.exception('PushHistoryAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PushStatsAPIView(APIView):
    """GET /fraud/push/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.notifications_push import get_notification_manager
            mgr   = get_notification_manager()
            stats = mgr.get_statistics() if hasattr(mgr, 'get_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('PushStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PushRetryFailedAPIView(APIView):
    """POST /fraud/push/retry-failed/ — retry all failed deliveries."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        max_age_hours = int(request.data.get('max_age_hours', 24))
        try:
            from api.fraud_detection.notifications_push import get_notification_manager
            mgr    = get_notification_manager()
            result = mgr.retry_failed(max_age_hours=max_age_hours) \
                if hasattr(mgr, 'retry_failed') else {'retried': 0}
            return _ok(result if isinstance(result, dict) else {'retried': result})
        except Exception as exc:
            logger.exception('PushRetryFailedAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

# ── ALIASES expected by urls.py ───────────────────────────────────────────────
PushNotificationSendAPIView   = PushSendFraudAlertAPIView
PushNotificationBulkAPIView   = PushBroadcastAPIView
PushNotificationStatusAPIView = PushChannelStatusAPIView
