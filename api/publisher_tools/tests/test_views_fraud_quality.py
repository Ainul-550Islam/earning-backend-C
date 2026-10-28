# publisher_tools/tests/test_views_fraud_quality.py
"""
High-priority API tests — TrafficSafetyLogViewSet, SiteQualityMetricViewSet.

TrafficSafetyLogViewSet:
  list (with filters), retrieve,
  take_action (admin), mark_false_positive (admin),
  summary

SiteQualityMetricViewSet:
  list (with filters), retrieve, create (admin),
  alerts, trend

Run:
    pytest publisher_tools/tests/test_views_fraud_quality.py -v
"""
import pytest
from publisher_tools.tests.factories import (
    PublisherFactory, SiteFactory, AdUnitFactory,
    TrafficSafetyLogFactory, SiteQualityMetricFactory,
)

FRAUD_BASE   = '/api/publisher-tools/traffic-safety'
QUALITY_BASE = '/api/publisher-tools/site-quality'


def fraud_url(suffix=''):
    return f'{FRAUD_BASE}{suffix}/'

def quality_url(suffix=''):
    return f'{QUALITY_BASE}{suffix}/'


# ==============================================================================
# TrafficSafetyLog — LIST
# ==============================================================================

@pytest.mark.django_db
class TestTrafficSafetyLogList:

    def test_publisher_can_list_own_logs(
        self, publisher_client, publisher, site
    ):
        TrafficSafetyLogFactory(publisher=publisher, site=site)
        TrafficSafetyLogFactory(publisher=publisher, site=site)
        resp = publisher_client.get(fraud_url())
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        assert len(results) == 2

    def test_publisher_cannot_see_other_logs(
        self, publisher_client, publisher_user_2
    ):
        other_pub  = PublisherFactory(user=publisher_user_2)
        other_site = SiteFactory(publisher=other_pub)
        TrafficSafetyLogFactory(publisher=other_pub, site=other_site)
        resp = publisher_client.get(fraud_url())
        body = resp.json()
        results = body.get('results', body.get('data', []))
        assert len(results) == 0

    def test_admin_can_list_all_logs(self, admin_client, traffic_log):
        resp = admin_client.get(fraud_url())
        assert resp.status_code == 200

    def test_unauthenticated_cannot_list(self, api_client):
        resp = api_client.get(fraud_url())
        assert resp.status_code in (401, 403)

    def test_admin_filter_by_traffic_type(self, admin_client, publisher, site):
        TrafficSafetyLogFactory(publisher=publisher, site=site, traffic_type='bot_traffic')
        TrafficSafetyLogFactory(publisher=publisher, site=site, traffic_type='click_fraud')
        resp = admin_client.get(fraud_url(), {'traffic_type': 'bot_traffic'})
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        for item in results:
            assert item['traffic_type'] == 'bot_traffic'

    def test_admin_filter_by_severity(self, admin_client, publisher, site):
        TrafficSafetyLogFactory(publisher=publisher, site=site, severity='high')
        TrafficSafetyLogFactory(publisher=publisher, site=site, severity='low')
        resp = admin_client.get(fraud_url(), {'severity': 'high'})
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        for item in results:
            assert item['severity'] == 'high'

    def test_admin_filter_by_min_fraud_score(self, admin_client, publisher, site):
        TrafficSafetyLogFactory(publisher=publisher, site=site, fraud_score=90)
        TrafficSafetyLogFactory(publisher=publisher, site=site, fraud_score=30)
        resp = admin_client.get(fraud_url(), {'min_fraud_score': 80})
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        for item in results:
            assert item['fraud_score'] >= 80

    def test_admin_filter_by_date_range(self, admin_client, publisher, site):
        import datetime
        TrafficSafetyLogFactory(
            publisher=publisher, site=site,
            detected_at=datetime.datetime(2025, 1, 15, tzinfo=datetime.timezone.utc)
        )
        TrafficSafetyLogFactory(
            publisher=publisher, site=site,
            detected_at=datetime.datetime(2025, 3, 15, tzinfo=datetime.timezone.utc)
        )
        resp = admin_client.get(
            fraud_url(),
            {'start_date': '2025-01-01', 'end_date': '2025-01-31'},
        )
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        assert len(results) == 1


# ==============================================================================
# TrafficSafetyLog — TAKE ACTION (admin)
# ==============================================================================

@pytest.mark.django_db
class TestTakeAction:

    def test_admin_can_take_action_block_ip(self, admin_client, traffic_log):
        resp = admin_client.post(
            fraud_url(f'/{traffic_log.pk}/take_action'),
            {'action': 'block_ip', 'notes': 'Confirmed bot.'},
            format='json',
        )
        assert resp.status_code == 200

    def test_take_action_response_has_log_data(self, admin_client, traffic_log):
        resp = admin_client.post(
            fraud_url(f'/{traffic_log.pk}/take_action'),
            {'action': 'block_ip'},
            format='json',
        )
        body = resp.json()
        data = body.get('data', body)
        assert 'fraud_score' in data
        assert 'traffic_type' in data

    def test_invalid_action_returns_400(self, admin_client, traffic_log):
        resp = admin_client.post(
            fraud_url(f'/{traffic_log.pk}/take_action'),
            {'action': 'do_nothing_illegal'},
            format='json',
        )
        assert resp.status_code == 400

    def test_missing_action_returns_400(self, admin_client, traffic_log):
        resp = admin_client.post(
            fraud_url(f'/{traffic_log.pk}/take_action'),
            {},
            format='json',
        )
        assert resp.status_code == 400

    def test_publisher_cannot_take_action(self, publisher_client, traffic_log):
        resp = publisher_client.post(
            fraud_url(f'/{traffic_log.pk}/take_action'),
            {'action': 'block_ip'},
            format='json',
        )
        assert resp.status_code in (403, 404)

    def test_unauthenticated_cannot_take_action(self, api_client, traffic_log):
        resp = api_client.post(
            fraud_url(f'/{traffic_log.pk}/take_action'),
            {'action': 'block_ip'},
        )
        assert resp.status_code in (401, 403)


# ==============================================================================
# TrafficSafetyLog — MARK FALSE POSITIVE (admin)
# ==============================================================================

@pytest.mark.django_db
class TestMarkFalsePositive:

    def test_admin_can_mark_false_positive(self, admin_client, traffic_log):
        resp = admin_client.post(
            fraud_url(f'/{traffic_log.pk}/mark_false_positive'),
            {'is_false_positive': True, 'notes': 'Confirmed legitimate traffic.'},
            format='json',
        )
        assert resp.status_code == 200
        traffic_log.refresh_from_db()
        assert traffic_log.is_false_positive is True

    def test_admin_can_unmark_false_positive(self, admin_client, traffic_log):
        traffic_log.is_false_positive = True
        traffic_log.save()
        resp = admin_client.post(
            fraud_url(f'/{traffic_log.pk}/mark_false_positive'),
            {'is_false_positive': False},
            format='json',
        )
        assert resp.status_code == 200
        traffic_log.refresh_from_db()
        assert traffic_log.is_false_positive is False

    def test_missing_is_false_positive_returns_400(self, admin_client, traffic_log):
        resp = admin_client.post(
            fraud_url(f'/{traffic_log.pk}/mark_false_positive'),
            {},
            format='json',
        )
        assert resp.status_code == 400

    def test_publisher_cannot_mark_false_positive(self, publisher_client, traffic_log):
        resp = publisher_client.post(
            fraud_url(f'/{traffic_log.pk}/mark_false_positive'),
            {'is_false_positive': True},
            format='json',
        )
        assert resp.status_code in (403, 404)


# ==============================================================================
# TrafficSafetyLog — SUMMARY
# ==============================================================================

@pytest.mark.django_db
class TestTrafficSafetyLogSummary:

    def test_publisher_can_get_summary(self, publisher_client, publisher, site):
        TrafficSafetyLogFactory(publisher=publisher, site=site, traffic_type='bot_traffic')
        TrafficSafetyLogFactory(publisher=publisher, site=site, traffic_type='click_fraud')
        resp = publisher_client.get(fraud_url('summary'))
        assert resp.status_code == 200

    def test_summary_returns_list(self, publisher_client, publisher, site):
        resp = publisher_client.get(fraud_url('summary'))
        body = resp.json()
        data = body.get('data', body)
        assert isinstance(data, list)

    def test_admin_can_get_global_summary(self, admin_client, traffic_log):
        resp = admin_client.get(fraud_url('summary'))
        assert resp.status_code == 200

    def test_summary_with_period_param(self, publisher_client):
        resp = publisher_client.get(fraud_url('summary'), {'period': 'last_7_days'})
        assert resp.status_code == 200

    def test_unauthenticated_cannot_view_summary(self, api_client):
        resp = api_client.get(fraud_url('summary'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# SiteQualityMetric — LIST / RETRIEVE
# ==============================================================================

@pytest.mark.django_db
class TestSiteQualityMetricList:

    def test_publisher_can_list_own_quality_metrics(
        self, publisher_client, publisher, site
    ):
        SiteQualityMetricFactory(site=site)
        resp = publisher_client.get(quality_url())
        assert resp.status_code == 200

    def test_publisher_cannot_see_other_site_metrics(
        self, publisher_client_2, site
    ):
        SiteQualityMetricFactory(site=site)
        resp = publisher_client_2.get(quality_url())
        body = resp.json()
        results = body.get('results', body.get('data', []))
        assert len(results) == 0

    def test_admin_can_list_all_metrics(self, admin_client, quality_metric):
        resp = admin_client.get(quality_url())
        assert resp.status_code == 200

    def test_admin_filter_by_has_alerts(self, admin_client, site):
        SiteQualityMetricFactory(site=site, has_alerts=True)
        SiteQualityMetricFactory(site=site, has_alerts=False)
        resp = admin_client.get(quality_url(), {'has_alerts': 'true'})
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        for item in results:
            assert item['has_alerts'] is True

    def test_admin_filter_by_min_score(self, admin_client, site):
        SiteQualityMetricFactory(site=site, overall_quality_score=90)
        SiteQualityMetricFactory(site=site, overall_quality_score=50)
        resp = admin_client.get(quality_url(), {'min_score': 80})
        assert resp.status_code == 200
        body = resp.json()
        results = body.get('results', body.get('data', []))
        for item in results:
            assert item['overall_quality_score'] >= 80

    def test_unauthenticated_cannot_list(self, api_client):
        resp = api_client.get(quality_url())
        assert resp.status_code in (401, 403)


# ==============================================================================
# SiteQualityMetric — ALERTS action
# ==============================================================================

@pytest.mark.django_db
class TestSiteQualityAlerts:

    def test_publisher_can_get_alerts(self, publisher_client, site):
        SiteQualityMetricFactory(site=site, has_alerts=True)
        SiteQualityMetricFactory(site=site, has_alerts=False)
        resp = publisher_client.get(quality_url('alerts'))
        assert resp.status_code == 200
        body = resp.json()
        data = body.get('data', body)
        assert isinstance(data, list)

    def test_alerts_only_returns_has_alerts_true(
        self, publisher_client, site
    ):
        SiteQualityMetricFactory(site=site, has_alerts=True)
        SiteQualityMetricFactory(site=site, has_alerts=False)
        resp = publisher_client.get(quality_url('alerts'))
        body = resp.json()
        data = body.get('data', body)
        for item in data:
            assert item['has_alerts'] is True

    def test_admin_can_view_global_alerts(self, admin_client, quality_metric):
        quality_metric.has_alerts = True
        quality_metric.save()
        resp = admin_client.get(quality_url('alerts'))
        assert resp.status_code == 200

    def test_unauthenticated_cannot_view_alerts(self, api_client):
        resp = api_client.get(quality_url('alerts'))
        assert resp.status_code in (401, 403)


# ==============================================================================
# SiteQualityMetric — TREND action
# ==============================================================================

@pytest.mark.django_db
class TestSiteQualityTrend:

    def test_publisher_can_get_trend(self, publisher_client, site):
        resp = publisher_client.get(
            quality_url('trend'), {'site_id': str(site.site_id)}
        )
        assert resp.status_code == 200

    def test_missing_site_id_returns_400(self, publisher_client):
        resp = publisher_client.get(quality_url('trend'))
        assert resp.status_code == 400

    def test_invalid_site_id_returns_404(self, publisher_client):
        resp = publisher_client.get(
            quality_url('trend'), {'site_id': 'SITE999999'}
        )
        assert resp.status_code == 404

    def test_other_publisher_site_id_returns_404(
        self, publisher_client, publisher_user_2
    ):
        other_pub  = PublisherFactory(user=publisher_user_2)
        other_site = SiteFactory(publisher=other_pub)
        resp = publisher_client.get(
            quality_url('trend'), {'site_id': str(other_site.site_id)}
        )
        assert resp.status_code == 404

    def test_admin_can_view_any_site_trend(self, admin_client, site):
        resp = admin_client.get(
            quality_url('trend'), {'site_id': str(site.site_id)}
        )
        assert resp.status_code == 200

    def test_days_param_respected(self, publisher_client, site):
        resp = publisher_client.get(
            quality_url('trend'),
            {'site_id': str(site.site_id), 'days': '7'},
        )
        assert resp.status_code == 200

    def test_unauthenticated_cannot_view_trend(self, api_client, site):
        resp = api_client.get(quality_url('trend'), {'site_id': str(site.site_id)})
        assert resp.status_code in (401, 403)


# ==============================================================================
# SiteQualityMetric — CREATE (admin only)
# ==============================================================================

@pytest.mark.django_db
class TestSiteQualityMetricCreate:

    def _payload(self, site):
        import datetime
        return {
            'site': site.pk,
            'date': str(datetime.date.today()),
            'overall_quality_score': 85,
            'content_score': 80,
            'traffic_score': 90,
            'technical_score': 85,
            'ads_txt_score': 95,
            'viewability_score': '0.72',
            'ivt_rate': '0.0100',
            'bounce_rate': '0.4200',
            'has_alerts': False,
            'alert_reasons': [],
            'recommendations': ['Improve page speed.'],
        }

    def test_admin_can_create_quality_metric(self, admin_client, site):
        resp = admin_client.post(quality_url(), self._payload(site), format='json')
        assert resp.status_code == 201

    def test_publisher_cannot_create_quality_metric(self, publisher_client, site):
        resp = publisher_client.post(quality_url(), self._payload(site), format='json')
        assert resp.status_code in (403, 405)

    def test_unauthenticated_cannot_create(self, api_client, site):
        resp = api_client.post(quality_url(), self._payload(site), format='json')
        assert resp.status_code in (401, 403)
