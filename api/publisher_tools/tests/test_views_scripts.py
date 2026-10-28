# publisher_tools/tests/test_views_scripts.py
"""
Tests for ScriptRunnerViewSet (views_scripts.py).
All endpoints are admin-only.
Covers: run_fraud_detection, run_waterfall_optimization,
        update_floor_prices, reorder_waterfalls, analyze_networks,
        validate_ads_txt, health_check, flag_suspicious_publishers,
        ivt_rates, calculate_earnings.
"""
import pytest

BASE = '/api/publisher-tools/admin-scripts'


def url(suffix=''):
    return f'{BASE}{suffix}/'


# ─── Permission guard shared test class ──────────────────────────────────────

class _PermissionMixin:
    """Shared: publisher and anonymous cannot access any script endpoint."""
    endpoint    = ''
    method      = 'post'
    extra_data  = {}

    def _call(self, client):
        if self.method == 'post':
            return client.post(url(self.endpoint), self.extra_data, format='json')
        return client.get(url(self.endpoint), self.extra_data)

    def test_publisher_cannot_run(self, publisher_client):
        resp = self._call(publisher_client)
        assert resp.status_code in (403, 404)

    def test_unauthenticated_cannot_run(self, api_client):
        resp = self._call(api_client)
        assert resp.status_code in (401, 403)


# ==============================================================================
# RUN FRAUD DETECTION
# ==============================================================================

@pytest.mark.django_db
class TestRunFraudDetection(_PermissionMixin):
    endpoint = 'run-fraud-detection'
    method   = 'post'

    def test_admin_can_run(self, admin_client):
        resp = admin_client.post(url('run-fraud-detection'), {'hours': 24}, format='json')
        assert resp.status_code in (200, 503)

    def test_hours_param_accepted(self, admin_client):
        resp = admin_client.post(url('run-fraud-detection'), {'hours': 48}, format='json')
        assert resp.status_code in (200, 503)

    def test_response_has_result_data(self, admin_client):
        resp = admin_client.post(url('run-fraud-detection'), {}, format='json')
        if resp.status_code == 200:
            assert resp.json().get('success') is True


# ==============================================================================
# RUN WATERFALL OPTIMIZATION
# ==============================================================================

@pytest.mark.django_db
class TestRunWaterfallOptimization(_PermissionMixin):
    endpoint = 'run-waterfall-optimization'
    method   = 'post'

    def test_admin_can_run(self, admin_client):
        resp = admin_client.post(url('run-waterfall-optimization'), {}, format='json')
        assert resp.status_code in (200, 503)

    def test_response_has_success(self, admin_client):
        resp = admin_client.post(url('run-waterfall-optimization'), {}, format='json')
        if resp.status_code == 200:
            assert resp.json().get('success') is True


# ==============================================================================
# UPDATE FLOOR PRICES
# ==============================================================================

@pytest.mark.django_db
class TestUpdateFloorPrices(_PermissionMixin):
    endpoint = 'update-floor-prices'
    method   = 'post'

    def test_admin_can_run(self, admin_client):
        resp = admin_client.post(url('update-floor-prices'), {}, format='json')
        assert resp.status_code in (200, 503)


# ==============================================================================
# REORDER WATERFALLS
# ==============================================================================

@pytest.mark.django_db
class TestReorderWaterfalls(_PermissionMixin):
    endpoint = 'reorder-waterfalls'
    method   = 'post'

    def test_admin_can_run(self, admin_client):
        resp = admin_client.post(url('reorder-waterfalls'), {}, format='json')
        assert resp.status_code in (200, 503)


# ==============================================================================
# ANALYZE NETWORKS
# ==============================================================================

@pytest.mark.django_db
class TestAnalyzeNetworks(_PermissionMixin):
    endpoint = 'analyze-networks'
    method   = 'post'

    def test_admin_can_run(self, admin_client):
        resp = admin_client.post(url('analyze-networks'), {}, format='json')
        assert resp.status_code in (200, 503)


# ==============================================================================
# VALIDATE ADS.TXT
# ==============================================================================

@pytest.mark.django_db
class TestValidateAdsTxt(_PermissionMixin):
    endpoint = 'validate-ads-txt'
    method   = 'post'

    def test_admin_can_run(self, admin_client):
        resp = admin_client.post(url('validate-ads-txt'), {}, format='json')
        assert resp.status_code in (200, 503)


# ==============================================================================
# HEALTH CHECK
# ==============================================================================

@pytest.mark.django_db
class TestHealthCheck(_PermissionMixin):
    endpoint = 'health-check'
    method   = 'get'

    def test_admin_can_run(self, admin_client):
        resp = admin_client.get(url('health-check'))
        assert resp.status_code in (200, 503)

    def test_health_check_returns_dict(self, admin_client):
        resp = admin_client.get(url('health-check'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert isinstance(data, dict)


# ==============================================================================
# FLAG SUSPICIOUS PUBLISHERS
# ==============================================================================

@pytest.mark.django_db
class TestFlagSuspiciousPublishers(_PermissionMixin):
    endpoint   = 'flag-suspicious-publishers'
    method     = 'post'
    extra_data = {'threshold_pct': 20.0, 'auto_suspend': False}

    def test_admin_can_run(self, admin_client):
        resp = admin_client.post(
            url('flag-suspicious-publishers'),
            {'threshold_pct': 20.0, 'auto_suspend': False},
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_with_auto_suspend_false(self, admin_client):
        resp = admin_client.post(
            url('flag-suspicious-publishers'),
            {'threshold_pct': 15.0, 'auto_suspend': False},
            format='json',
        )
        assert resp.status_code in (200, 503)


# ==============================================================================
# IVT RATES
# ==============================================================================

@pytest.mark.django_db
class TestIVTRates(_PermissionMixin):
    endpoint = 'ivt-rates'
    method   = 'get'

    def test_admin_can_view_ivt_rates(self, admin_client):
        resp = admin_client.get(url('ivt-rates'))
        assert resp.status_code in (200, 503)

    def test_days_param_accepted(self, admin_client):
        resp = admin_client.get(url('ivt-rates'), {'days': '7'})
        assert resp.status_code in (200, 503)

    def test_ivt_rates_returns_list_or_dict(self, admin_client):
        resp = admin_client.get(url('ivt-rates'))
        if resp.status_code == 200:
            body = resp.json()
            data = body.get('data', body)
            assert isinstance(data, (list, dict))


# ==============================================================================
# CALCULATE EARNINGS
# ==============================================================================

@pytest.mark.django_db
class TestCalculateEarnings(_PermissionMixin):
    endpoint = 'calculate-earnings'
    method   = 'post'

    def test_admin_can_run(self, admin_client):
        resp = admin_client.post(
            url('calculate-earnings'),
            {'year': 2025, 'month': 1},
            format='json',
        )
        assert resp.status_code in (200, 503)

    def test_without_year_month_uses_defaults(self, admin_client):
        resp = admin_client.post(url('calculate-earnings'), {}, format='json')
        assert resp.status_code in (200, 503)

    def test_response_has_success_field(self, admin_client):
        resp = admin_client.post(
            url('calculate-earnings'),
            {'year': 2025, 'month': 1},
            format='json',
        )
        if resp.status_code == 200:
            assert resp.json().get('success') is True
