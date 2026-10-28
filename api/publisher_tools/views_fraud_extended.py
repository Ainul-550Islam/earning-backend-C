# publisher_tools/views_fraud_extended.py
"""
FILE 6 of 10 — Fraud Prevention Extended API
=============================================
fraud_prevention/ subfolder-এর 10টি floating item expose করা হয়েছে।

Previously floating (now wired):
  analyze_user_agent, calculate_composite_fraud_score,
  check_device_fingerprint, BOT_USER_AGENTS, DATACENTER_IP_RANGES,
  SUSPICIOUS_CLICK_THRESHOLD, create_fraud_alert, detect_invalid_traffic,
  get_ip_reputation, resolve_fraud_alert

Register in urls.py:
  router.register(r'fraud-tools', FraudExtendedViewSet, basename='fraud-ext')
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher, IsAdminOrPublisher


class FraudExtendedViewSet(BaseViewSet):
    """
    Fraud Prevention Extended API।

    Publisher endpoints:
      POST /fraud-tools/analyze-ua/           — analyze user agent string
      POST /fraud-tools/check-device/         — device fingerprint check
      POST /fraud-tools/check-impression/     — real-time impression fraud check
      GET  /fraud-tools/ip-reputation/        — IP reputation lookup
      GET  /fraud-tools/config/               — fraud detection thresholds

    Admin endpoints:
      POST /fraud-tools/composite-score/      — full composite fraud scoring
      GET  /fraud-tools/invalid-traffic/      — IVT detection report
      POST /fraud-tools/create-alert/         — create fraud alert
      POST /fraud-tools/resolve-alert/        — resolve fraud alert
      GET  /fraud-tools/bot-list/             — known bot user agents list
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    # ── USER AGENT ANALYSIS ────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='analyze-ua')
    def analyze_ua(self, request):
        """
        User agent string analyze করে bot কিনা বলে।
        POST body: { "user_agent": "Mozilla/5.0 ...", "headers": {} }
        """
        ua      = request.data.get('user_agent', '')
        headers = request.data.get('headers', {})
        if not ua:
            return self.error_response('user_agent required.', status_code=400)
        try:
            from .fraud_prevention.bot_detector import (
                detect_bot_from_ua, detect_headless_browser
            )
            bot_result      = detect_bot_from_ua(ua)
            headless_result = detect_headless_browser(ua, headers)
            return self.success_response(data={
                'user_agent':       ua,
                'is_bot':           bot_result.get('is_bot', False),
                'bot_type':         bot_result.get('bot_type'),
                'confidence':       bot_result.get('confidence', 0),
                'is_headless':      headless_result.get('is_headless', False),
                'headless_signals': headless_result.get('signals', []),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── DEVICE FINGERPRINT ─────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='check-device')
    def check_device(self, request):
        """
        Device fingerprint fraud check করে।
        POST body: {
          "device_data": { "screen": "1920x1080", "platform": "Win32", ... }
        }
        """
        device_data = request.data.get('device_data', {})
        if not device_data:
            return self.error_response('device_data required.', status_code=400)
        try:
            from .fraud_prevention.device_fingerprint import (
                generate_device_fingerprint, detect_emulator,
                get_device_trust_score
            )
            fingerprint   = generate_device_fingerprint(device_data)
            emulator_data = detect_emulator(device_data)
            trust_score   = get_device_trust_score(device_data)
            return self.success_response(data={
                'fingerprint':    fingerprint,
                'trust_score':    trust_score,
                'is_emulator':    emulator_data.get('is_emulator', False),
                'emulator_signals': emulator_data.get('signals', []),
                'risk_level':     'high' if trust_score < 30 else
                                  'medium' if trust_score < 60 else 'low',
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── IMPRESSION FRAUD CHECK ─────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='check-impression')
    def check_impression(self, request):
        """
        Real-time impression fraud check।
        POST body: {
          "ip_address": "1.2.3.4",
          "user_agent": "...",
          "unit_id":    "UNIT-001",
          "session_id": "sess_abc123"
        }
        """
        ip_address = request.data.get('ip_address', '')
        user_agent = request.data.get('user_agent', '')
        if not ip_address:
            return self.error_response('ip_address required.', status_code=400)
        try:
            from .fraud_prevention.bot_detector import detect_bot_from_ua, is_datacenter_ip
            is_datacenter = is_datacenter_ip(ip_address)
            bot_result    = detect_bot_from_ua(user_agent) if user_agent else {}
            is_fraud      = is_datacenter or bot_result.get('is_bot', False)
            fraud_score   = 0
            if is_datacenter:
                fraud_score += 60
            if bot_result.get('is_bot'):
                fraud_score += bot_result.get('confidence', 30)
            return self.success_response(data={
                'ip_address':      ip_address,
                'is_fraud':        is_fraud,
                'fraud_score':     min(100, fraud_score),
                'is_datacenter':   is_datacenter,
                'is_bot':          bot_result.get('is_bot', False),
                'action':          'block' if is_fraud else 'allow',
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── IP REPUTATION ──────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='ip-reputation')
    def ip_reputation(self, request):
        """
        IP address-এর fraud reputation।
        GET ?ip=1.2.3.4
        """
        ip = request.query_params.get('ip', '').strip()
        if not ip:
            return self.error_response('ip query param required.', status_code=400)
        try:
            from .fraud_prevention.bot_detector import is_datacenter_ip
            from .models import BlockedIP
            is_datacenter = is_datacenter_ip(ip)
            is_blocked    = BlockedIP.objects.filter(
                ip_address=ip
            ).filter(
                unblocked_at__isnull=True
            ).exists()
            return self.success_response(data={
                'ip_address':    ip,
                'is_datacenter': is_datacenter,
                'is_blocked':    is_blocked,
                'risk_level':    'high' if (is_datacenter or is_blocked) else 'low',
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── FRAUD CONFIG (thresholds + known bots) ─────────────────────────────────

    @action(detail=False, methods=['get'], url_path='config')
    def fraud_config(self, request):
        """
        Fraud detection thresholds ও configuration।
        """
        try:
            from .fraud_prevention import (
                SUSPICIOUS_CLICK_THRESHOLD,
            )
            return self.success_response(data={
                'suspicious_click_threshold': SUSPICIOUS_CLICK_THRESHOLD,
                'auto_block_score':           80,
                'review_score':               50,
                'safe_score':                 30,
            })
        except ImportError:
            return self.success_response(data={
                'suspicious_click_threshold': 10,
                'auto_block_score': 80,
                'review_score': 50,
                'safe_score': 30,
            })

    @action(
        detail=False, methods=['get'], url_path='bot-list',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def bot_list(self, request):
        """[Admin] Known bot user agent patterns।"""
        try:
            from .fraud_prevention import BOT_USER_AGENTS, DATACENTER_IP_RANGES
            return self.success_response(data={
                'bot_user_agents':     list(BOT_USER_AGENTS),
                'datacenter_ranges':   list(DATACENTER_IP_RANGES),
                'bot_count':           len(BOT_USER_AGENTS),
                'datacenter_count':    len(DATACENTER_IP_RANGES),
            })
        except ImportError:
            return self.error_response('Bot list not available.', status_code=503)

    # ── ADMIN: COMPOSITE SCORE + IVT + ALERTS ─────────────────────────────────

    @action(
        detail=False, methods=['post'], url_path='composite-score',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def composite_score(self, request):
        """
        [Admin] Full composite fraud score calculation。
        POST body: { "ip": "1.2.3.4", "ua": "...", "device_data": {} }
        """
        ip          = request.data.get('ip', '')
        ua          = request.data.get('ua', '')
        device_data = request.data.get('device_data', {})
        try:
            from .fraud_prevention import calculate_composite_fraud_score
            score = calculate_composite_fraud_score(
                ip_address=ip,
                user_agent=ua,
                device_data=device_data,
            )
            return self.success_response(data={
                'composite_score': score,
                'risk_level': 'critical' if score >= 80 else
                              'high'     if score >= 60 else
                              'medium'   if score >= 40 else 'low',
                'recommended_action': 'block'  if score >= 80 else
                                      'review' if score >= 50 else 'allow',
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(
        detail=False, methods=['get'], url_path='invalid-traffic',
        permission_classes=[IsAuthenticated, IsAdminOrPublisher],
    )
    def invalid_traffic(self, request):
        """
        Invalid traffic (IVT) detection summary।
        GET ?publisher_id=PUB-001&days=7
        """
        publisher = self._get_publisher()
        days      = int(request.query_params.get('days', 7))
        try:
            from .fraud_prevention import detect_invalid_traffic
            result = detect_invalid_traffic(publisher, days=days)
            return self.success_response(data=result)
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(
        detail=False, methods=['post'], url_path='create-alert',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def create_alert(self, request):
        """[Admin] Manual fraud alert তৈরি করে।"""
        publisher_id = request.data.get('publisher_id')
        alert_type   = request.data.get('alert_type', 'manual')
        severity     = request.data.get('severity', 'high')
        message      = request.data.get('message', '')
        if not publisher_id:
            return self.error_response('publisher_id required.', status_code=400)
        try:
            from .models import Publisher
            from .fraud_prevention import create_fraud_alert
            publisher = Publisher.objects.get(publisher_id=publisher_id)
            alert     = create_fraud_alert(publisher, alert_type, severity, message)
            return self.success_response(
                data={'alert_id': getattr(alert, 'pk', None), 'created': True},
                message='Fraud alert created.',
                status_code=201,
            )
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(
        detail=False, methods=['post'], url_path='resolve-alert',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def resolve_alert(self, request):
        """[Admin] Fraud alert resolve করে।"""
        alert_id   = request.data.get('alert_id')
        resolution = request.data.get('resolution', 'resolved')
        if not alert_id:
            return self.error_response('alert_id required.', status_code=400)
        try:
            from .fraud_prevention.fraud_alert import resolve_fraud_alert
            resolve_fraud_alert(alert_id, resolution, resolved_by=request.user)
            return self.success_response(data={'alert_id': alert_id, 'resolved': True})
        except Exception as e:
            return self.error_response(str(e), status_code=503)
