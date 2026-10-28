# publisher_tools/views_fraud_report.py
"""
FraudReportViewSet — fraud_prevention/ subfolder-এর সব floating
report/geo/velocity functions এখানে API-তে wire করা হয়েছে।

Previously floating (এখন wired):
  fraud_prevention/fraud_report.py    → generate_fraud_report,
                                         generate_platform_fraud_report
  fraud_prevention/geo_validation.py  → validate_geo, detect_geo_impossible_travel,
                                         get_country_risk_score, is_country_allowed
  fraud_prevention/velocity_checker.py → VelocityChecker, check_click_velocity,
                                          check_impression_velocity,
                                          check_conversion_velocity

Note: ip_blacklist, bot_detector, device_fingerprint are already wired in
      views_fraud_extended.py — not duplicated here.

Register in urls.py:
  router.register(r'fraud-reports', FraudReportViewSet, basename='fraud-report')

Endpoints:
  GET  /api/publisher-tools/fraud-reports/report/
  GET  /api/publisher-tools/fraud-reports/platform-report/   (admin only)
  POST /api/publisher-tools/fraud-reports/geo-validate/
  POST /api/publisher-tools/fraud-reports/impossible-travel/
  GET  /api/publisher-tools/fraud-reports/country-risk/
  POST /api/publisher-tools/fraud-reports/velocity-check/
  POST /api/publisher-tools/fraud-reports/click-velocity/
  POST /api/publisher-tools/fraud-reports/impression-velocity/
  POST /api/publisher-tools/fraud-reports/conversion-velocity/

DRY:
  - PublisherViewMixin: self.publisher, self.handle_errors(), self.ok()
  - AdminOnlyMixin only applied per-action via permission_classes override
  - No local _get_publisher()
"""

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from core.views import BaseViewSet
from .mixins import PublisherViewMixin, AdminOnlyMixin, ErrorHandlingMixin
from .permissions import IsPublisher


class FraudReportViewSet(PublisherViewMixin, BaseViewSet):
    """
    Fraud Reporting API — fraud_prevention/ floating functions exposed।

    Inherits from PublisherViewMixin:
      - self.publisher         → cached publisher
      - self.handle_errors()   → collapses try/except boilerplate
      - self.ok(data, message) → standardised success response
    """

    permission_classes = [IsAuthenticated, IsPublisher]

    # ─────────────────────────────────────────────────────────────────────────
    # FRAUD REPORTS
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], url_path='report')
    def fraud_report(self, request):
        """
        Comprehensive fraud report for the authenticated publisher।
        Wires: fraud_prevention.fraud_report.generate_fraud_report()

        GET ?days=30

        Response:
          {
            "publisher_id": "PUB-001",
            "period_days":  30,
            "summary": {
              "total_ivt_events": 42,
              "avg_fraud_score":  65.3,
              "ivt_rate_pct":     3.2,
              "revenue_at_risk_usd": 18.5,
              ...
            },
            "by_type":     [...],
            "by_severity": [...],
            "top_ips":     [...],
            "risk_level":  "low"
          }
        """
        pub = self.publisher
        try:
            days = int(request.query_params.get('days', 30))
        except (ValueError, TypeError):
            days = 30

        days = max(1, min(days, 365))

        with self.handle_errors() as guard:
            from .fraud_prevention.fraud_report import generate_fraud_report
            data = generate_fraud_report(pub, days=days)
            return self.ok(data)
        return guard.response

    @action(
        detail=False,
        methods=['get'],
        url_path='platform-report',
        permission_classes=[IsAuthenticated, IsAdminUser],
    )
    def platform_fraud_report(self, request):
        """
        Platform-wide fraud report — admin only।
        Wires: fraud_prevention.fraud_report.generate_platform_fraud_report()

        GET ?days=30
        """
        try:
            days = int(request.query_params.get('days', 30))
        except (ValueError, TypeError):
            days = 30

        days = max(1, min(days, 365))

        with self.handle_errors() as guard:
            from .fraud_prevention.fraud_report import generate_platform_fraud_report
            data = generate_platform_fraud_report(days=days)
            return self.ok(data)
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # GEO VALIDATION
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='geo-validate')
    def geo_validate(self, request):
        """
        Validate IP geo vs claimed geo, detect VPN/high-risk countries।
        Wires: fraud_prevention.geo_validation.validate_geo()

        POST body:
          {
            "ip_country":      "KP",
            "claimed_country": "US"   (optional)
          }

        Response:
          {
            "score":        90,
            "is_suspicious": true,
            "signals":      ["high_risk_country:KP", "geo_mismatch:ip=KP,claimed=US"],
            "ip_country":   "KP"
          }
        """
        data = request.data
        ip_country = (data.get('ip_country') or '').strip().upper()
        if not ip_country:
            return self.error_response('ip_country is required.', status_code=400)

        claimed_country = (data.get('claimed_country') or '').strip().upper() or None

        with self.handle_errors() as guard:
            from .fraud_prevention.geo_validation import validate_geo
            result = validate_geo(
                ip_country=ip_country,
                claimed_country=claimed_country,
            )
            return self.ok(result)
        return guard.response

    @action(detail=False, methods=['post'], url_path='impossible-travel')
    def impossible_travel(self, request):
        """
        Detect impossible travel (country changed too fast → likely VPN/fraud)।
        Wires: fraud_prevention.geo_validation.detect_geo_impossible_travel()

        POST body:
          {
            "user_id":        "user_xyz",
            "current_country": "US",
            "prev_country":    "BD",
            "time_diff_hours": 0.5
          }

        Response:
          {
            "user_id":             "user_xyz",
            "is_impossible_travel": true,
            "current_country":     "US",
            "prev_country":        "BD",
            "time_diff_hours":     0.5
          }
        """
        data = request.data
        user_id      = data.get('user_id', '')
        current      = (data.get('current_country') or '').strip().upper()
        prev         = (data.get('prev_country') or '').strip().upper()

        if not current:
            return self.error_response('current_country is required.', status_code=400)

        try:
            time_diff_hours = float(data.get('time_diff_hours', 0))
        except (ValueError, TypeError):
            return self.error_response(
                'time_diff_hours must be a number.', status_code=400
            )

        with self.handle_errors() as guard:
            from .fraud_prevention.geo_validation import detect_geo_impossible_travel
            is_impossible = detect_geo_impossible_travel(
                user_id=user_id,
                current_country=current,
                prev_country=prev,
                time_diff_hours=time_diff_hours,
            )
            return self.ok({
                'user_id':              user_id,
                'is_impossible_travel': is_impossible,
                'current_country':      current,
                'prev_country':         prev,
                'time_diff_hours':      time_diff_hours,
            })
        return guard.response

    @action(detail=False, methods=['get'], url_path='country-risk')
    def country_risk(self, request):
        """
        Get fraud risk score for a given country code।
        Wires: fraud_prevention.geo_validation.get_country_risk_score()

        GET ?country=KP
        """
        country = request.query_params.get('country', '').strip().upper()
        if not country:
            return self.error_response('country is required.', status_code=400)

        with self.handle_errors() as guard:
            from .fraud_prevention.geo_validation import (
                get_country_risk_score,
                HIGH_RISK_COUNTRIES,
                KNOWN_VPN_COUNTRIES,
            )
            score     = get_country_risk_score(country)
            is_high   = country in HIGH_RISK_COUNTRIES
            is_vpn    = country in KNOWN_VPN_COUNTRIES
            return self.ok({
                'country':         country,
                'risk_score':      score,
                'is_high_risk':    is_high,
                'is_vpn_country':  is_vpn,
                'risk_level': (
                    'critical' if score >= 80 else
                    'high'     if score >= 50 else
                    'medium'   if score >= 20 else
                    'low'
                ),
            })
        return guard.response

    # ─────────────────────────────────────────────────────────────────────────
    # VELOCITY CHECKS
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='velocity-check')
    def velocity_check(self, request):
        """
        Multi-window velocity check for any event type।
        Wires: fraud_prevention.velocity_checker.VelocityChecker.check_multi_window()

        POST body:
          {
            "identifier": "ip:192.168.1.1",
            "event_type": "click"
          }

        Response:
          {
            "identifier":  "ip:192.168.1.1",
            "event_type":  "click",
            "exceeded":    false,
            "windows": {
              "60s":    {"count": 3, "max": 10, "exceeded": false, ...},
              "300s":   {...},
              "3600s":  {...},
              "86400s": {...}
            }
          }
        """
        data       = request.data
        identifier = data.get('identifier', '').strip()
        event_type = data.get('event_type', '').strip()

        if not identifier:
            return self.error_response('identifier is required.', status_code=400)
        if not event_type:
            return self.error_response('event_type is required.', status_code=400)

        with self.handle_errors() as guard:
            from .fraud_prevention.velocity_checker import VelocityChecker
            result = VelocityChecker.check_multi_window(identifier, event_type)
            return self.ok(result)
        return guard.response

    @action(detail=False, methods=['post'], url_path='click-velocity')
    def click_velocity(self, request):
        """
        Click velocity check for an identifier+unit combination।
        Wires: fraud_prevention.velocity_checker.check_click_velocity()

        POST body:
          {
            "identifier": "ip:192.168.1.1",
            "unit_id":    "UNIT-001"
          }
        """
        data       = request.data
        identifier = data.get('identifier', '').strip()
        unit_id    = data.get('unit_id', '').strip()

        if not identifier:
            return self.error_response('identifier is required.', status_code=400)
        if not unit_id:
            return self.error_response('unit_id is required.', status_code=400)

        with self.handle_errors() as guard:
            from .fraud_prevention.velocity_checker import check_click_velocity
            result = check_click_velocity(identifier, unit_id)
            return self.ok(result)
        return guard.response

    @action(detail=False, methods=['post'], url_path='impression-velocity')
    def impression_velocity(self, request):
        """
        Impression velocity check (per IP per unit, 60s window, max 200)।
        Wires: fraud_prevention.velocity_checker.check_impression_velocity()

        POST body:
          {
            "ip":      "192.168.1.1",
            "unit_id": "UNIT-001"
          }
        """
        data    = request.data
        ip      = data.get('ip', '').strip()
        unit_id = data.get('unit_id', '').strip()

        if not ip:
            return self.error_response('ip is required.', status_code=400)
        if not unit_id:
            return self.error_response('unit_id is required.', status_code=400)

        with self.handle_errors() as guard:
            from .fraud_prevention.velocity_checker import check_impression_velocity
            result = check_impression_velocity(ip, unit_id)
            return self.ok(result)
        return guard.response

    @action(detail=False, methods=['post'], url_path='conversion-velocity')
    def conversion_velocity(self, request):
        """
        Conversion velocity check (multi-window)।
        Wires: fraud_prevention.velocity_checker.check_conversion_velocity()

        POST body:
          {
            "identifier": "user_xyz"
          }
        """
        identifier = request.data.get('identifier', '').strip()
        if not identifier:
            return self.error_response('identifier is required.', status_code=400)

        with self.handle_errors() as guard:
            from .fraud_prevention.velocity_checker import check_conversion_velocity
            result = check_conversion_velocity(identifier)
            return self.ok(result)
        return guard.response
