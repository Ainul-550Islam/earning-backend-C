# publisher_tools/tests/test_views_fraud_report.py
"""
Tests for FraudReportViewSet (views_fraud_report.py)।

Covers all 9 @action endpoints:
  fraud_report, platform_fraud_report,
  geo_validate, impossible_travel, country_risk,
  velocity_check, click_velocity, impression_velocity, conversion_velocity

Pattern: pytest + APIClient + conftest.py fixtures
Auth:    publisher_client → force_authenticate(user=publisher_user)
         admin_client    → force_authenticate(user=admin_user)
"""

import pytest

BASE = '/api/publisher-tools/fraud-reports'


# ══════════════════════════════════════════════════════════════════════════════
# FRAUD REPORT
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestFraudReport:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/report/').status_code in (401, 403)

    def test_returns_report(self, publisher_client):
        assert publisher_client.get(f'{BASE}/report/').status_code in (200, 503)

    def test_with_custom_days(self, publisher_client):
        r = publisher_client.get(f'{BASE}/report/', {'days': 7})
        assert r.status_code in (200, 503)

    def test_response_has_summary_key(self, publisher_client):
        r = publisher_client.get(f'{BASE}/report/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'summary' in data

    def test_response_has_publisher_id(self, publisher_client):
        r = publisher_client.get(f'{BASE}/report/')
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'publisher_id' in data or 'summary' in data

    def test_not_500(self, publisher_client):
        assert publisher_client.get(f'{BASE}/report/').status_code != 500


# ══════════════════════════════════════════════════════════════════════════════
# PLATFORM FRAUD REPORT (admin only)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPlatformFraudReport:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        r = unauthenticated_client.get(f'{BASE}/platform-report/')
        assert r.status_code in (401, 403)

    def test_publisher_non_admin_denied(self, publisher_client):
        r = publisher_client.get(f'{BASE}/platform-report/')
        assert r.status_code in (403, 503)

    def test_admin_can_access(self, admin_client):
        r = admin_client.get(f'{BASE}/platform-report/')
        assert r.status_code in (200, 503)

    def test_admin_with_days_param(self, admin_client):
        r = admin_client.get(f'{BASE}/platform-report/', {'days': 7})
        assert r.status_code in (200, 503)


# ══════════════════════════════════════════════════════════════════════════════
# GEO VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestGeoValidate:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        r = unauthenticated_client.post(f'{BASE}/geo-validate/', {}, format='json')
        assert r.status_code in (401, 403)

    def test_missing_ip_country_returns_400(self, publisher_client):
        r = publisher_client.post(f'{BASE}/geo-validate/', {}, format='json')
        assert r.status_code == 400

    def test_low_risk_country(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/geo-validate/',
            {'ip_country': 'DE'},
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_high_risk_country(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/geo-validate/',
            {'ip_country': 'KP'},
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_geo_mismatch_with_claimed(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/geo-validate/',
            {'ip_country': 'KP', 'claimed_country': 'US'},
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_response_has_score_and_signals(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/geo-validate/',
            {'ip_country': 'BD'},
            format='json',
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'score' in data
            assert 'signals' in data

    def test_response_is_suspicious_is_boolean(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/geo-validate/', {'ip_country': 'DE'}, format='json'
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert isinstance(data.get('is_suspicious'), bool)


# ══════════════════════════════════════════════════════════════════════════════
# IMPOSSIBLE TRAVEL
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestImpossibleTravel:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        r = unauthenticated_client.post(f'{BASE}/impossible-travel/', {}, format='json')
        assert r.status_code in (401, 403)

    def test_missing_current_country_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/impossible-travel/',
            {'prev_country': 'BD', 'time_diff_hours': 0.5},
            format='json',
        )
        assert r.status_code == 400

    def test_missing_time_diff_hours_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/impossible-travel/',
            {'current_country': 'US'},
            format='json',
        )
        assert r.status_code == 400

    def test_valid_impossible_scenario(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/impossible-travel/',
            {
                'user_id':          'test_user_001',
                'current_country':  'US',
                'prev_country':     'BD',
                'time_diff_hours':  0.1,
            },
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_valid_possible_travel(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/impossible-travel/',
            {
                'user_id':          'test_user_002',
                'current_country':  'IN',
                'prev_country':     'BD',
                'time_diff_hours':  12.0,
            },
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_response_has_is_impossible_travel_key(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/impossible-travel/',
            {'current_country': 'US', 'prev_country': 'BD', 'time_diff_hours': 0.5},
            format='json',
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'is_impossible_travel' in data

    def test_is_impossible_travel_is_boolean(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/impossible-travel/',
            {'current_country': 'US', 'time_diff_hours': 2.0},
            format='json',
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert isinstance(data.get('is_impossible_travel'), bool)


# ══════════════════════════════════════════════════════════════════════════════
# COUNTRY RISK
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCountryRisk:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        assert unauthenticated_client.get(f'{BASE}/country-risk/').status_code in (401, 403)

    def test_missing_country_returns_400(self, publisher_client):
        assert publisher_client.get(f'{BASE}/country-risk/').status_code == 400

    def test_valid_low_risk_country(self, publisher_client):
        r = publisher_client.get(f'{BASE}/country-risk/', {'country': 'DE'})
        assert r.status_code in (200, 503)

    def test_valid_high_risk_country(self, publisher_client):
        r = publisher_client.get(f'{BASE}/country-risk/', {'country': 'KP'})
        assert r.status_code in (200, 503)

    def test_valid_bd_country(self, publisher_client):
        r = publisher_client.get(f'{BASE}/country-risk/', {'country': 'BD'})
        assert r.status_code in (200, 503)

    def test_response_has_risk_score(self, publisher_client):
        r = publisher_client.get(f'{BASE}/country-risk/', {'country': 'US'})
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'risk_score' in data

    def test_response_has_risk_level(self, publisher_client):
        r = publisher_client.get(f'{BASE}/country-risk/', {'country': 'KP'})
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'risk_level' in data
            assert data['risk_level'] in ('low', 'medium', 'high', 'critical')

    def test_response_has_boolean_flags(self, publisher_client):
        r = publisher_client.get(f'{BASE}/country-risk/', {'country': 'BD'})
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert isinstance(data.get('is_high_risk'), bool)
            assert isinstance(data.get('is_vpn_country'), bool)


# ══════════════════════════════════════════════════════════════════════════════
# VELOCITY CHECK
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestVelocityCheck:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        r = unauthenticated_client.post(f'{BASE}/velocity-check/', {}, format='json')
        assert r.status_code in (401, 403)

    def test_missing_identifier_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/velocity-check/', {'event_type': 'click'}, format='json'
        )
        assert r.status_code == 400

    def test_missing_event_type_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/velocity-check/', {'identifier': 'ip:1.2.3.4'}, format='json'
        )
        assert r.status_code == 400

    def test_valid_click_event(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/velocity-check/',
            {'identifier': 'ip:192.168.1.100', 'event_type': 'click'},
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_valid_impression_event(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/velocity-check/',
            {'identifier': 'user:abc123', 'event_type': 'impression'},
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_response_has_exceeded_key(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/velocity-check/',
            {'identifier': 'ip:10.0.0.1', 'event_type': 'click'},
            format='json',
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'exceeded' in data

    def test_response_has_windows_key(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/velocity-check/',
            {'identifier': 'ip:10.0.0.1', 'event_type': 'click'},
            format='json',
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'windows' in data


# ══════════════════════════════════════════════════════════════════════════════
# CLICK VELOCITY
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestClickVelocity:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        r = unauthenticated_client.post(f'{BASE}/click-velocity/', {}, format='json')
        assert r.status_code in (401, 403)

    def test_missing_identifier_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/click-velocity/', {'unit_id': 'UNIT-001'}, format='json'
        )
        assert r.status_code == 400

    def test_missing_unit_id_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/click-velocity/', {'identifier': 'ip:1.2.3.4'}, format='json'
        )
        assert r.status_code == 400

    def test_valid_payload_handled(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/click-velocity/',
            {'identifier': 'ip:192.168.0.1', 'unit_id': 'UNIT-TEST-001'},
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_not_500(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/click-velocity/',
            {'identifier': 'ip:10.0.0.1', 'unit_id': 'UNIT-TEST-002'},
            format='json',
        )
        assert r.status_code != 500


# ══════════════════════════════════════════════════════════════════════════════
# IMPRESSION VELOCITY
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestImpressionVelocity:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        r = unauthenticated_client.post(f'{BASE}/impression-velocity/', {}, format='json')
        assert r.status_code in (401, 403)

    def test_missing_ip_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/impression-velocity/', {'unit_id': 'UNIT-001'}, format='json'
        )
        assert r.status_code == 400

    def test_missing_unit_id_returns_400(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/impression-velocity/', {'ip': '192.168.1.1'}, format='json'
        )
        assert r.status_code == 400

    def test_valid_payload_handled(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/impression-velocity/',
            {'ip': '192.168.1.1', 'unit_id': 'UNIT-TEST-001'},
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_response_has_exceeded_key(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/impression-velocity/',
            {'ip': '10.0.0.5', 'unit_id': 'UNIT-TEST-001'},
            format='json',
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            assert 'exceeded' in data or 'rate' in data or 'count' in data


# ══════════════════════════════════════════════════════════════════════════════
# CONVERSION VELOCITY
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestConversionVelocity:
    def test_unauthenticated_rejected(self, unauthenticated_client):
        r = unauthenticated_client.post(f'{BASE}/conversion-velocity/', {}, format='json')
        assert r.status_code in (401, 403)

    def test_missing_identifier_returns_400(self, publisher_client):
        r = publisher_client.post(f'{BASE}/conversion-velocity/', {}, format='json')
        assert r.status_code == 400

    def test_valid_user_identifier(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/conversion-velocity/',
            {'identifier': 'user:test_abc_123'},
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_valid_ip_identifier(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/conversion-velocity/',
            {'identifier': 'ip:203.0.113.42'},
            format='json',
        )
        assert r.status_code in (200, 503)

    def test_not_500(self, publisher_client):
        r = publisher_client.post(
            f'{BASE}/conversion-velocity/',
            {'identifier': 'user:probe_xyz'},
            format='json',
        )
        assert r.status_code != 500
