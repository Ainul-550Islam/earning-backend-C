# publisher_tools/tests/test_views_fraud.py
"""
Tests for FraudViewSet (views_fraud.py).
Covers: my_summary, ip_check, alerts (publisher),
        platform_report, check_impression, check_click,
        check_conversion, block_ip, unblock_ip, blocked_ips (admin).
"""
import pytest
from publisher_tools.tests.factories import (
    PublisherFactory, SiteFactory, TrafficSafetyLogFactory,
)

BASE = '/api/publisher-tools/fraud'


def url(suffix=''):
    return f'{BASE}{suffix}/'


# ==============================================================================
# MY SUMMARY
# ==============================================================================

@pytest.mark.django_db
class TestFraudMySummary:

    def test_publisher_can_view_own_summary(self, publisher_client):
        resp = publisher_client.get(url('my-summary'))
        assert resp.status_code == 200

    def test_summary_has_expected_keys(self, publisher_client):
        resp = publisher_client.get(url('my-summary'))
        body = resp.json()
        data = body.get('data', body)
        assert 'total_events' in data
        assert 'revenue_at_risk' in data

    def test_summary_with_period_param(self, publisher_client):
        resp = publisher_client.get(url('my-summary'), {'days': '7'})
        assert resp.status_code == 200

    def test_summary_reflects_actual_logs(self, publisher_client, publisher, site):
        TrafficSafetyLogFactory(publisher=publisher, site=site, fraud_score=85)
        TrafficSafetyLogFactory(publisher=publisher, site=site, fraud_score=90)
        resp = publisher_client.get(url('my-summary'))
        body = resp.json()
        data = body.get('data', body)
        assert data.get('total_events', 0) >= 2

    def test_unauthenticated_cannot_view_summary(self, api_client):
        resp = api_client.get(url('my-summary'))
        assert resp.status_code in (401, 403)

    def test_publisher_cannot_see_other_publishers_fraud(
        self, publisher_client, publisher_user_2
    ):
        other_pub  = PublisherFactory(user=publisher_user_2)
        other_site = SiteFactory(publisher=other_pub)
        TrafficSafetyLogFactory(publisher=other_pub, site=other_site, fraud_score=99)
        resp = publisher_client.get(url('my-summary'))
        body = resp.json()
        data = body.get('data', body)
        # own count should still be 0
        assert data.get('total_events', 0) == 0


# ==============================================================================
# IP CHECK
# ==============================================================================

@pytest.mark.django_db
class TestIPCheck:

    def test_publisher_can_check_ip(self, publisher_client):
        resp = publisher_client.get(url('ip-check'), {'ip': '1.2.3.4'})
        assert resp.status_code == 200

    def test_response_has_is_blocked_field(self, publisher_client):
        resp = publisher_client.get(url('ip-check'), {'ip': '5.6.7.8'})
        body = resp.json()
        data = body.get('data', body)
        assert 'is_blocked' in data

    def test_missing_ip_returns_400(self, publisher_client):
        resp = publisher_client.get(url('ip-check'))
        assert resp.status_code == 400

    def test_blocked_ip_returns_true(self, publisher_client, publisher, admin_client):
        # Block the IP via admin endpoint first
        admin_client.post(url('block-ip'), {'ip': '9.9.9.9', 'reason': 'test'}, format='json')
        resp = publisher_client.get(url('ip-check'), {'ip': '9.9.9.9'})
        body = resp.json()
        data = body.get('data', body)
        assert data.get('is_blocked') is True

    def test_unauthenticated_cannot_check(self, api_client):
        resp = api_client.get(url('ip-check'), {'ip': '1.2.3.4'})
        assert resp.status_code in (401, 403)


# ==============================================================================
# ALERTS
# ==============================================================================

@pytest.mark.django_db
class TestFraudAlerts:

    def test_publisher_can_view_own_alerts(self, publisher_client, publisher, site):
        TrafficSafetyLogFactory(
            publisher=publisher, site=site, severity='high', action_taken='pending'
        )
        resp = publisher_client.get(url('alerts'))
        assert resp.status_code == 200

    def test_alerts_returns_list(self, publisher_client):
        resp = publisher_client.get(url('alerts'))
        body = resp.json()
        data = body.get('data', body)
        assert isinstance(data, list)

    def test_alerts_only_contains_own_publisher_data(
        self, publisher_client, publisher_user_2
    ):
        other_pub  = PublisherFactory(user=publisher_user_2)
        other_site = SiteFactory(publisher=other_pub)
        TrafficSafetyLogFactory(
            publisher=other_pub, site=other_site,
            severity='critical', action_taken='pending',
        )
        resp = publisher_client.get(url('alerts'))
        body = resp.json()
        data = body.get('data', body)
        assert len(data) == 0


# ==============================================================================
# ADMIN: BLOCK / UNBLOCK IP
# ==============================================================================

@pytest.mark.django_db
class TestIPBlockUnblock:

    def test_admin_can_block_ip(self, admin_client):
        resp = admin_client.post(
            url('block-ip'),
            {'ip': '10.0.0.1', 'reason': 'Confirmed bot', 'hours': 24},
            format='json',
        )
        assert resp.status_code == 200

    def test_block_requires_ip(self, admin_client):
        resp = admin_client.post(url('block-ip'), {'reason': 'test'}, format='json')
        assert resp.status_code == 400

    def test_publisher_cannot_block_ip(self, publisher_client):
        resp = publisher_client.post(
            url('block-ip'),
            {'ip': '10.0.0.2', 'reason': 'test'},
            format='json',
        )
        assert resp.status_code in (403, 404)

    def test_admin_can_unblock_ip(self, admin_client):
        admin_client.post(url('block-ip'), {'ip': '10.0.0.3', 'reason': 'test'}, format='json')
        resp = admin_client.post(url('unblock-ip'), {'ip': '10.0.0.3'}, format='json')
        assert resp.status_code == 200

    def test_unblock_requires_ip(self, admin_client):
        resp = admin_client.post(url('unblock-ip'), {}, format='json')
        assert resp.status_code == 400

    def test_unblocking_unknown_ip_returns_200(self, admin_client):
        resp = admin_client.post(url('unblock-ip'), {'ip': '255.255.255.255'}, format='json')
        assert resp.status_code == 200

    def test_permanent_block(self, admin_client):
        resp = admin_client.post(
            url('block-ip'),
            {'ip': '192.168.1.100', 'reason': 'Spam', 'permanent': True},
            format='json',
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert data.get('permanent') is True

    def test_unauthenticated_cannot_block(self, api_client):
        resp = api_client.post(url('block-ip'), {'ip': '1.1.1.1', 'reason': 'test'})
        assert resp.status_code in (401, 403)


# ==============================================================================
# ADMIN: BLOCKED IPS LIST
# ==============================================================================

@pytest.mark.django_db
class TestBlockedIPList:

    def test_admin_can_list_blocked_ips(self, admin_client):
        admin_client.post(url('block-ip'), {'ip': '10.10.10.1', 'reason': 'test'}, format='json')
        resp = admin_client.get(url('blocked-ips'))
        assert resp.status_code == 200

    def test_blocked_ips_response_structure(self, admin_client):
        resp = admin_client.get(url('blocked-ips'))
        body = resp.json()
        data = body.get('data', body)
        assert 'blocked_ips' in data
        assert 'count' in data

    def test_active_only_filter(self, admin_client):
        resp = admin_client.get(url('blocked-ips'), {'active_only': 'true'})
        assert resp.status_code == 200

    def test_publisher_cannot_list_blocked_ips(self, publisher_client):
        resp = publisher_client.get(url('blocked-ips'))
        assert resp.status_code in (403, 404)


# ==============================================================================
# ADMIN: FRAUD CHECKS
# ==============================================================================

@pytest.mark.django_db
class TestFraudChecks:

    def test_admin_can_check_impression(self, admin_client):
        resp = admin_client.post(
            url('check-impression'),
            {'ip': '1.2.3.4', 'user_agent': 'Mozilla/5.0', 'ad_unit_id': 'unit_123'},
            format='json',
        )
        assert resp.status_code == 200

    def test_admin_can_check_click(self, admin_client):
        resp = admin_client.post(
            url('check-click'),
            {'identifier': '1.2.3.4', 'unit_id': 'unit_abc'},
            format='json',
        )
        assert resp.status_code == 200

    def test_check_click_requires_identifier(self, admin_client):
        resp = admin_client.post(url('check-click'), {'unit_id': 'unit_abc'}, format='json')
        assert resp.status_code == 400

    def test_admin_can_check_conversion(self, admin_client):
        resp = admin_client.post(
            url('check-conversion'),
            {'ip': '1.2.3.4', 'conversion_id': 'conv_001'},
            format='json',
        )
        assert resp.status_code == 200

    def test_publisher_cannot_check_impression(self, publisher_client):
        resp = publisher_client.post(
            url('check-impression'),
            {'ip': '1.2.3.4'},
            format='json',
        )
        assert resp.status_code in (403, 404)

    def test_admin_can_view_platform_report(self, admin_client):
        resp = admin_client.get(url('platform-report'), {'days': '7'})
        assert resp.status_code in (200, 503)  # 503 if fraud_prevention module not wired

    def test_publisher_cannot_view_platform_report(self, publisher_client):
        resp = publisher_client.get(url('platform-report'))
        assert resp.status_code in (403, 404)
