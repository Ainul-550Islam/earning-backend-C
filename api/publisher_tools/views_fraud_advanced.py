# publisher_tools/views_fraud_advanced.py
"""
FILE 5 of 10 — Fraud Prevention Advanced API
=============================================
fraud_prevention/ remaining 15 floating functions exposed.

Previously floating (now wired):
  check_impression_velocity, check_conversion_velocity,
  check_multi_window, validate_geo, detect_geo_impossible_travel,
  get_country_risk_score, detect_click_fraud, detect_click_injection,
  check_viewability_fraud, get_risk_level, mark_read (fraud_alert)

Register in urls.py:
  router.register(r'fraud-advanced', FraudAdvancedViewSet, basename='fraud-adv')
"""
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PublisherViewMixin, AdminScriptViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from core.views import BaseViewSet
from .permissions import IsPublisher, IsAdminOrPublisher


class FraudAdvancedViewSet(BaseViewSet):
    """
    Fraud Prevention Advanced API.

    Velocity checking:
      POST /fraud-advanced/check-impression-velocity/  — impression velocity check
      POST /fraud-advanced/check-conversion-velocity/  — conversion velocity check
      POST /fraud-advanced/check-multi-window/         — multi-window velocity

    Geo validation:
      POST /fraud-advanced/validate-geo/               — geographic validation
      POST /fraud-advanced/impossible-travel/          — impossible travel detection
      GET  /fraud-advanced/country-risk/               — country risk score

    Click fraud:
      POST /fraud-advanced/detect-click-fraud/         — click fraud detection
      POST /fraud-advanced/detect-click-injection/     — click injection detection

    Viewability:
      POST /fraud-advanced/check-viewability-fraud/    — viewability fraud check

    Risk scoring:
      POST /fraud-advanced/risk-level/                 — get risk level from score

    Alerts:
      GET  /fraud-advanced/alerts/                     — fraud alerts list
      POST /fraud-advanced/mark-alert-read/            — mark alert as read
    """
    permission_classes = [IsAuthenticated, IsPublisher]

    # ── VELOCITY CHECKING ──────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='check-impression-velocity')
    def check_impression_velocity(self, request):
        """
        Impression velocity check — too many impressions from same source।
        POST body: {
          "ip":         "1.2.3.4",
          "unit_id":    "UNIT-001",
          "window_sec": 3600
        }
        """
        ip       = request.data.get('ip', '')
        unit_id  = request.data.get('unit_id', '')
        window   = int(request.data.get('window_sec', 3600))
        if not ip:
            return self.error_response('ip required.', status_code=400)
        try:
            from .fraud_prevention.velocity_checker import check_impression_velocity
            result = check_impression_velocity(ip, unit_id, window_seconds=window)
            return self.success_response(data=result if isinstance(result, dict) else {
                'suspicious': bool(result), 'ip': ip, 'unit_id': unit_id
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='check-conversion-velocity')
    def check_conversion_velocity(self, request):
        """
        Conversion velocity check।
        POST body: { "ip": "1.2.3.4", "unit_id": "UNIT-001", "window_sec": 86400 }
        """
        ip      = request.data.get('ip', '')
        unit_id = request.data.get('unit_id', '')
        window  = int(request.data.get('window_sec', 86400))
        if not ip:
            return self.error_response('ip required.', status_code=400)
        try:
            from .fraud_prevention.velocity_checker import check_conversion_velocity
            result = check_conversion_velocity(ip, unit_id, window_seconds=window)
            return self.success_response(data=result if isinstance(result, dict) else {
                'suspicious': bool(result)
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='check-multi-window')
    def check_multi_window(self, request):
        """
        Multi-window velocity check (1min, 5min, 1hr, 24hr simultaneously)।
        POST body: { "ip": "1.2.3.4", "event_type": "impression", "unit_id": "UNIT-001" }
        """
        ip         = request.data.get('ip', '')
        event_type = request.data.get('event_type', 'impression')
        unit_id    = request.data.get('unit_id', '')
        if not ip:
            return self.error_response('ip required.', status_code=400)
        try:
            from .fraud_prevention.velocity_checker import check_multi_window
            result = check_multi_window(ip, event_type, unit_id=unit_id)
            return self.success_response(data=result if isinstance(result, dict) else {
                'suspicious': bool(result)
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── GEO VALIDATION ─────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='validate-geo')
    def validate_geo(self, request):
        """
        Geographic data validation — country/timezone mismatch detection।
        POST body: {
          "ip":          "1.2.3.4",
          "browser_tz":  "America/New_York",
          "browser_lang":"en-US"
        }
        """
        ip          = request.data.get('ip', '')
        browser_tz  = request.data.get('browser_tz', '')
        browser_lang= request.data.get('browser_lang', '')
        if not ip:
            return self.error_response('ip required.', status_code=400)
        try:
            from .fraud_prevention.geo_validation import validate_geo
            result = validate_geo(ip, browser_tz=browser_tz, browser_lang=browser_lang)
            return self.success_response(data=result if isinstance(result, dict) else {
                'valid': bool(result), 'ip': ip
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='impossible-travel')
    def impossible_travel(self, request):
        """
        Impossible travel detection — same user from two distant locations।
        POST body: {
          "user_id":         "user_123",
          "current_ip":      "1.2.3.4",
          "previous_ip":     "5.6.7.8",
          "time_diff_sec":   3600
        }
        """
        user_id     = request.data.get('user_id', '')
        current_ip  = request.data.get('current_ip', '')
        previous_ip = request.data.get('previous_ip', '')
        time_diff   = int(request.data.get('time_diff_sec', 3600))
        if not current_ip or not previous_ip:
            return self.error_response('current_ip and previous_ip required.', status_code=400)
        try:
            from .fraud_prevention.geo_validation import detect_geo_impossible_travel
            result = detect_geo_impossible_travel(
                user_id, current_ip, previous_ip, time_diff_seconds=time_diff
            )
            return self.success_response(data=result if isinstance(result, dict) else {
                'impossible_travel': bool(result),
                'current_ip':        current_ip,
                'previous_ip':       previous_ip,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['get'], url_path='country-risk')
    def country_risk(self, request):
        """
        Country risk score for ad fraud।
        GET ?country=US | BD | IN | ...
        Multiple: GET ?country=US,BD,IN
        """
        country_param = request.query_params.get('country', 'US')
        countries     = [c.strip().upper() for c in country_param.split(',')]
        try:
            from .fraud_prevention.geo_validation import get_country_risk_score
            result = {c: get_country_risk_score(c) for c in countries}
            return self.success_response(data={
                'risk_scores': result,
                'scale':       '0 (safe) – 100 (high risk)',
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── CLICK FRAUD ────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='detect-click-fraud')
    def detect_click_fraud(self, request):
        """
        Click fraud detection।
        POST body: {
          "ip":         "1.2.3.4",
          "unit_id":    "UNIT-001",
          "user_agent": "...",
          "referrer":   "https://example.com",
          "session_id": "sess_abc"
        }
        """
        ip         = request.data.get('ip', '')
        unit_id    = request.data.get('unit_id', '')
        user_agent = request.data.get('user_agent', '')
        referrer   = request.data.get('referrer', '')
        session_id = request.data.get('session_id', '')
        if not ip:
            return self.error_response('ip required.', status_code=400)
        try:
            from .fraud_prevention.click_fraud_detector import detect_click_fraud
            result = detect_click_fraud(
                ip=ip, unit_id=unit_id, user_agent=user_agent,
                referrer=referrer, session_id=session_id,
            )
            return self.success_response(data=result if isinstance(result, dict) else {
                'is_fraud': bool(result), 'ip': ip
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='detect-click-injection')
    def detect_click_injection(self, request):
        """
        Click injection detection (mobile app fraud)।
        POST body: {
          "click_timestamp_ms": 1704067200000,
          "install_timestamp_ms": 1704067500000,
          "attribution_window_sec": 604800
        }
        """
        click_ts   = request.data.get('click_timestamp_ms')
        install_ts = request.data.get('install_timestamp_ms')
        window     = int(request.data.get('attribution_window_sec', 604800))
        if not click_ts or not install_ts:
            return self.error_response(
                'click_timestamp_ms and install_timestamp_ms required.', status_code=400
            )
        try:
            from .fraud_prevention.click_fraud_detector import detect_click_injection
            result = detect_click_injection(
                click_timestamp_ms=int(click_ts),
                install_timestamp_ms=int(install_ts),
                attribution_window_sec=window,
            )
            return self.success_response(data=result if isinstance(result, dict) else {
                'is_injection': bool(result)
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── VIEWABILITY FRAUD ──────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='check-viewability-fraud')
    def check_viewability_fraud(self, request):
        """
        Viewability fraud check — artificially inflated viewability।
        POST body: {
          "impression_id":   "imp_abc",
          "viewability_pct": 98,
          "duration_ms":     100,
          "unit_id":         "UNIT-001"
        }
        """
        viewability_pct = float(request.data.get('viewability_pct', 0))
        duration_ms     = int(request.data.get('duration_ms', 0))
        unit_id         = request.data.get('unit_id', '')
        impression_id   = request.data.get('impression_id', '')
        try:
            from .fraud_prevention.impression_fraud_detector import check_viewability_fraud
            result = check_viewability_fraud(
                viewability_pct=viewability_pct,
                duration_ms=duration_ms,
                unit_id=unit_id,
            )
            return self.success_response(data=result if isinstance(result, dict) else {
                'is_fraud':       bool(result),
                'impression_id':  impression_id,
                'viewability_pct': viewability_pct,
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    # ── RISK SCORING ───────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='risk-level')
    def risk_level(self, request):
        """
        Fraud score থেকে risk level বের করে।
        POST body: { "fraud_score": 75 }
        """
        score = int(request.data.get('fraud_score', 0))
        if not 0 <= score <= 100:
            return self.error_response('fraud_score must be 0–100.', status_code=400)
        try:
            from .fraud_prevention.quality_score import get_risk_level
            level = get_risk_level(score)
            return self.success_response(data={
                'fraud_score': score,
                'risk_level':  level,
                'action':      'block'  if score >= 80 else
                               'review' if score >= 50 else 'allow',
            })
        except Exception as e:
            # Fallback
            level = 'critical' if score >= 80 else 'high' if score >= 60 else \
                    'medium'   if score >= 40 else 'low'
            return self.success_response(data={
                'fraud_score': score, 'risk_level': level
            })

    # ── FRAUD ALERTS ───────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='alerts')
    def alerts(self, request):
        """Publisher-এর unread fraud alerts।"""
        publisher = self._get_publisher()
        try:
            from .fraud_prevention.fraud_alert import FraudAlert
            alerts = FraudAlert.objects.filter(
                publisher=publisher
            ).order_by('-created_at')[:50]
            return self.success_response(data={
                'alerts': [
                    {
                        'pk':         a.pk,
                        'alert_type': getattr(a, 'alert_type', ''),
                        'severity':   getattr(a, 'severity', ''),
                        'is_read':    getattr(a, 'is_read', False),
                        'message':    getattr(a, 'message', ''),
                        'created_at': str(a.created_at),
                    }
                    for a in alerts
                ],
                'count': alerts.count(),
                'unread': alerts.filter(is_read=False).count(),
            })
        except Exception as e:
            return self.error_response(str(e), status_code=503)

    @action(detail=False, methods=['post'], url_path='mark-alert-read')
    def mark_alert_read(self, request):
        """
        Fraud alert mark as read।
        POST body: { "alert_id": 5 } or { "mark_all": true }
        """
        publisher = self._get_publisher()
        alert_id  = request.data.get('alert_id')
        mark_all  = bool(request.data.get('mark_all', False))
        try:
            from .fraud_prevention.fraud_alert import FraudAlert
            if mark_all:
                updated = FraudAlert.objects.filter(
                    publisher=publisher, is_read=False
                ).update(is_read=True)
                return self.success_response(data={'marked_read': updated})
            if not alert_id:
                return self.error_response('alert_id or mark_all required.', status_code=400)
            alert = FraudAlert.objects.get(pk=alert_id, publisher=publisher)
            if hasattr(alert, 'mark_read'):
                alert.mark_read()
            else:
                alert.is_read = True
                alert.save(update_fields=['is_read', 'updated_at'])
            return self.success_response(data={'alert_id': alert_id, 'is_read': True})
        except Exception as e:
            return self.error_response(str(e), status_code=503)
