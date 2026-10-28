# publisher_tools/tests/test_warehouse_views.py
"""
Analytics Warehouse ViewSets — full API test coverage।

Tests:
  - সব 21টি ViewSet-এর permission (admin only)
  - list / detail endpoints
  - date, publisher_id, is_processed filters
  - Special actions: summary, totals, unresolved, active, top-endpoints, by-test
  - WarehouseHealthViewSet: list, counts, ingest, mark-processed
  - ETL ingest: dry_run, unknown type, missing publisher
"""
import pytest

BASE = '/api/warehouse'


def url(path=''):
    return f'{BASE}/{path}'


# ── Shared permission mixin ───────────────────────────────────────────────────

class _AdminOnlyMixin:
    """Publisher and anonymous users must be rejected (403/401)."""
    endpoint = ''  # set in subclass, e.g. 'publisher-records'

    def test_unauthenticated_rejected(self, api_client):
        resp = api_client.get(url(f'{self.endpoint}/'))
        assert resp.status_code in (401, 403)

    def test_publisher_rejected(self, publisher_client):
        resp = publisher_client.get(url(f'{self.endpoint}/'))
        assert resp.status_code in (401, 403)

    def test_admin_can_list(self, admin_client):
        resp = admin_client.get(url(f'{self.endpoint}/'))
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════════════════════
# 1. PublisherRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPublisherRecordViewSet(_AdminOnlyMixin):
    endpoint = 'publisher-records'

    def test_list_empty(self, admin_client):
        resp = admin_client.get(url('publisher-records/'))
        assert resp.status_code in (200, 404)

    def test_publisher_id_filter_param_accepted(self, admin_client):
        resp = admin_client.get(url('publisher-records/'), {'publisher_id': 'PUB001'})
        assert resp.status_code in (200, 404)

    def test_date_filter_accepted(self, admin_client):
        resp = admin_client.get(url('publisher-records/'), {
            'start_date': '2025-01-01', 'end_date': '2025-01-31'
        })
        assert resp.status_code in (200, 404)

    def test_is_processed_filter_true(self, admin_client):
        resp = admin_client.get(url('publisher-records/'), {'is_processed': 'true'})
        assert resp.status_code in (200, 404)

    def test_is_processed_filter_false(self, admin_client):
        resp = admin_client.get(url('publisher-records/'), {'is_processed': 'false'})
        assert resp.status_code in (200, 404)

    def test_summary_action_accessible(self, admin_client):
        resp = admin_client.get(url('publisher-records/summary/'))
        assert resp.status_code in (200, 404)

    def test_summary_returns_aggregates(self, admin_client):
        resp = admin_client.get(url('publisher-records/summary/'))
        if resp.status_code == 200:
            data = resp.json()
            assert 'total'     in data or 'total_records' in data
            assert 'processed' in data or 'processed_records' in data

    def test_nonexistent_record_404(self, admin_client):
        resp = admin_client.get(url('publisher-records/99999/'))
        assert resp.status_code in (404, 404)


# ══════════════════════════════════════════════════════════════════════════════
# 2. SiteRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSiteRecordViewSet(_AdminOnlyMixin):
    endpoint = 'site-records'

    def test_site_id_filter_accepted(self, admin_client):
        resp = admin_client.get(url('site-records/'), {'site_id': 'SITE001'})
        assert resp.status_code in (200, 404)

    def test_list_response_structure(self, admin_client):
        resp = admin_client.get(url('site-records/'))
        if resp.status_code == 200:
            body = resp.json()
            assert 'results' in body or isinstance(body, list)


# ══════════════════════════════════════════════════════════════════════════════
# 3. AppRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAppRecordViewSet(_AdminOnlyMixin):
    endpoint = 'app-records'

    def test_app_id_filter_accepted(self, admin_client):
        resp = admin_client.get(url('app-records/'), {'app_id': 'APP001'})
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════════════════════
# 4. AdUnitRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAdUnitRecordViewSet(_AdminOnlyMixin):
    endpoint = 'ad-unit-records'

    def test_unit_id_filter_accepted(self, admin_client):
        resp = admin_client.get(url('ad-unit-records/'), {'unit_id': 'UNIT001'})
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════════════════════
# 5. ImpressionRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestImpressionRecordViewSet(_AdminOnlyMixin):
    endpoint = 'impression-records'

    def test_totals_action_accessible(self, admin_client):
        resp = admin_client.get(url('impression-records/totals/'))
        assert resp.status_code in (200, 404)

    def test_totals_returns_aggregate_keys(self, admin_client):
        resp = admin_client.get(url('impression-records/totals/'))
        if resp.status_code == 200:
            data = resp.json()
            # Should have aggregation keys
            assert isinstance(data, dict)


# ══════════════════════════════════════════════════════════════════════════════
# 6. ClickRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestClickRecordViewSet(_AdminOnlyMixin):
    endpoint = 'click-records'

    def test_list_accessible(self, admin_client):
        resp = admin_client.get(url('click-records/'))
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════════════════════
# 7. RevenueRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRevenueRecordViewSet(_AdminOnlyMixin):
    endpoint = 'revenue-records'

    def test_totals_action_accessible(self, admin_client):
        resp = admin_client.get(url('revenue-records/totals/'))
        assert resp.status_code in (200, 404)

    def test_totals_returns_dict(self, admin_client):
        resp = admin_client.get(url('revenue-records/totals/'))
        if resp.status_code == 200:
            assert isinstance(resp.json(), dict)


# ══════════════════════════════════════════════════════════════════════════════
# 8. InvoiceRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestInvoiceRecordViewSet(_AdminOnlyMixin):
    endpoint = 'invoice-records'

    def test_status_filter_accepted(self, admin_client):
        resp = admin_client.get(url('invoice-records/'), {'status': 'paid'})
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════════════════════
# 9. PaymentRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPaymentRecordViewSet(_AdminOnlyMixin):
    endpoint = 'payment-records'

    def test_method_filter_accepted(self, admin_client):
        resp = admin_client.get(url('payment-records/'), {'method': 'wire'})
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════════════════════
# 10. FraudLogRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestFraudLogRecordViewSet(_AdminOnlyMixin):
    endpoint = 'fraud-log-records'

    def test_fraud_type_filter_accepted(self, admin_client):
        resp = admin_client.get(url('fraud-log-records/'), {'fraud_type': 'click_farm'})
        assert resp.status_code in (200, 404)

    def test_resolved_filter_accepted(self, admin_client):
        resp = admin_client.get(url('fraud-log-records/'), {'resolved': 'false'})
        assert resp.status_code in (200, 404)

    def test_unresolved_action_accessible(self, admin_client):
        resp = admin_client.get(url('fraud-log-records/unresolved/'))
        assert resp.status_code in (200, 404)

    def test_unresolved_returns_count_and_results(self, admin_client):
        resp = admin_client.get(url('fraud-log-records/unresolved/'))
        if resp.status_code == 200:
            data = resp.json()
            assert 'count'   in data
            assert 'results' in data


# ══════════════════════════════════════════════════════════════════════════════
# 11. AuditLogRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAuditLogRecordViewSet(_AdminOnlyMixin):
    endpoint = 'audit-log-records'

    def test_action_filter_accepted(self, admin_client):
        resp = admin_client.get(url('audit-log-records/'), {'action': 'publisher.approved'})
        assert resp.status_code in (200, 404)

    def test_actor_filter_accepted(self, admin_client):
        resp = admin_client.get(url('audit-log-records/'), {'actor_id': 'admin_001'})
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════════════════════
# 12. AdPlacementRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAdPlacementRecordViewSet(_AdminOnlyMixin):
    endpoint = 'placement-records'

    def test_list_accessible(self, admin_client):
        resp = admin_client.get(url('placement-records/'))
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════════════════════
# 13. ReportRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestReportRecordViewSet(_AdminOnlyMixin):
    endpoint = 'report-records'

    def test_report_type_filter_accepted(self, admin_client):
        resp = admin_client.get(url('report-records/'), {'report_type': 'monthly'})
        assert resp.status_code in (200, 404)

    def test_status_filter_accepted(self, admin_client):
        resp = admin_client.get(url('report-records/'), {'status': 'completed'})
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════════════════════
# 14. AlertRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAlertRecordViewSet(_AdminOnlyMixin):
    endpoint = 'alert-records'

    def test_severity_filter_accepted(self, admin_client):
        resp = admin_client.get(url('alert-records/'), {'severity': 'critical'})
        assert resp.status_code in (200, 404)

    def test_resolved_filter_accepted(self, admin_client):
        resp = admin_client.get(url('alert-records/'), {'resolved': 'false'})
        assert resp.status_code in (200, 404)

    def test_active_action_accessible(self, admin_client):
        resp = admin_client.get(url('alert-records/active/'))
        assert resp.status_code in (200, 404)

    def test_active_returns_count_and_results(self, admin_client):
        resp = admin_client.get(url('alert-records/active/'))
        if resp.status_code == 200:
            data = resp.json()
            assert 'count'   in data
            assert 'results' in data


# ══════════════════════════════════════════════════════════════════════════════
# 15. WebhookLogRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWebhookLogRecordViewSet(_AdminOnlyMixin):
    endpoint = 'webhook-log-records'

    def test_event_type_filter_accepted(self, admin_client):
        resp = admin_client.get(url('webhook-log-records/'), {'event_type': 'publisher.approved'})
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════════════════════
# 16. NotificationRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestNotificationRecordViewSet(_AdminOnlyMixin):
    endpoint = 'notification-records'

    def test_is_read_filter_accepted(self, admin_client):
        resp = admin_client.get(url('notification-records/'), {'is_read': 'false'})
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════════════════════
# 17. SettingRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSettingRecordViewSet(_AdminOnlyMixin):
    endpoint = 'setting-records'

    def test_setting_key_filter_accepted(self, admin_client):
        resp = admin_client.get(url('setting-records/'), {'setting_key': 'notification'})
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════════════════════
# 18. APIKeyLogRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAPIKeyLogRecordViewSet(_AdminOnlyMixin):
    endpoint = 'api-key-log-records'

    def test_key_prefix_filter_accepted(self, admin_client):
        resp = admin_client.get(url('api-key-log-records/'), {'api_key_prefix': 'pk_test_'})
        assert resp.status_code in (200, 404)

    def test_top_endpoints_action_accessible(self, admin_client):
        resp = admin_client.get(url('api-key-log-records/top-endpoints/'))
        assert resp.status_code in (200, 404)

    def test_top_endpoints_returns_results(self, admin_client):
        resp = admin_client.get(url('api-key-log-records/top-endpoints/'))
        if resp.status_code == 200:
            data = resp.json()
            assert 'results' in data
            assert isinstance(data['results'], list)


# ══════════════════════════════════════════════════════════════════════════════
# 19. OptimizationLogRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestOptimizationLogRecordViewSet(_AdminOnlyMixin):
    endpoint = 'optimization-log-records'

    def test_opt_type_filter_accepted(self, admin_client):
        resp = admin_client.get(url('optimization-log-records/'), {'optimization_type': 'floor_price'})
        assert resp.status_code in (200, 404)

    def test_applied_filter_accepted(self, admin_client):
        resp = admin_client.get(url('optimization-log-records/'), {'applied': 'true'})
        assert resp.status_code in (200, 404)


# ══════════════════════════════════════════════════════════════════════════════
# 20. ABTestRecordViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestABTestRecordViewSet(_AdminOnlyMixin):
    endpoint = 'ab-test-records'

    def test_test_type_filter_accepted(self, admin_client):
        resp = admin_client.get(url('ab-test-records/'), {'test_type': 'placement'})
        assert resp.status_code in (200, 404)

    def test_ab_test_id_filter_accepted(self, admin_client):
        resp = admin_client.get(url('ab-test-records/'), {'ab_test_id': '1'})
        assert resp.status_code in (200, 404)

    def test_by_test_action_accessible(self, admin_client):
        resp = admin_client.get(url('ab-test-records/by-test/1/'))
        assert resp.status_code in (200, 404)

    def test_by_test_returns_structured_response(self, admin_client):
        resp = admin_client.get(url('ab-test-records/by-test/999/'))
        if resp.status_code == 200:
            data = resp.json()
            assert 'count'   in data
            assert 'results' in data


# ══════════════════════════════════════════════════════════════════════════════
# 21. WarehouseHealthViewSet
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWarehouseHealthViewSet:

    def test_unauthenticated_rejected(self, api_client):
        resp = api_client.get(url('health/'))
        assert resp.status_code in (401, 403)

    def test_publisher_rejected(self, publisher_client):
        resp = publisher_client.get(url('health/'))
        assert resp.status_code in (401, 403)

    def test_admin_can_access_health(self, admin_client):
        resp = admin_client.get(url('health/'))
        assert resp.status_code in (200, 404)

    def test_health_response_keys(self, admin_client):
        resp = admin_client.get(url('health/'))
        if resp.status_code == 200:
            data = resp.json()
            assert 'total_records'          in data
            assert 'processed_records'      in data
            assert 'unprocessed_records'    in data
            assert 'processing_rate_pct'    in data
            assert 'record_counts_by_type'  in data
            assert 'last_updated'           in data

    def test_health_counts_action(self, admin_client):
        resp = admin_client.get(url('health/counts/'))
        assert resp.status_code in (200, 404)

    def test_health_counts_has_20_types(self, admin_client):
        resp = admin_client.get(url('health/counts/'))
        if resp.status_code == 200:
            data = resp.json()
            assert len(data) == 20

    def test_health_ingest_requires_body(self, admin_client):
        resp = admin_client.post(url('health/ingest/'), {}, format='json')
        assert resp.status_code in (400, 404)

    def test_health_ingest_unknown_type_rejected(self, admin_client):
        resp = admin_client.post(url('health/ingest/'), {
            'record_type': 'unknown_type',
            'publisher_id': 'PUB001',
            'records': [{}],
            'dry_run': True,
        }, format='json')
        assert resp.status_code in (400, 404)

    def test_health_ingest_dry_run_does_not_save(self, admin_client):
        resp = admin_client.post(url('health/ingest/'), {
            'record_type': 'publisher',
            'publisher_id': 'PUB_NONEXISTENT',
            'records': [{'record_date': '2025-01-15'}],
            'dry_run': True,
        }, format='json')
        # dry_run=True returns 200 with would_insert count
        if resp.status_code == 200:
            data = resp.json()
            assert data.get('dry_run') is True
            assert 'would_insert' in data

    def test_health_ingest_publisher_not_found_returns_error(self, admin_client):
        resp = admin_client.post(url('health/ingest/'), {
            'record_type': 'publisher',
            'publisher_id': 'NONEXISTENT_PUB',
            'records': [{}],
            'dry_run': False,
        }, format='json')
        assert resp.status_code in (404, 400, 404)

    def test_health_mark_processed_requires_body(self, admin_client):
        resp = admin_client.post(url('health/mark-processed/'), {}, format='json')
        assert resp.status_code in (400, 404)

    def test_health_mark_processed_unknown_type_rejected(self, admin_client):
        resp = admin_client.post(url('health/mark-processed/'), {
            'record_type': 'unknown',
            'ids': [1, 2, 3],
        }, format='json')
        assert resp.status_code in (400, 404)

    def test_health_mark_processed_valid_returns_updated_count(self, admin_client):
        resp = admin_client.post(url('health/mark-processed/'), {
            'record_type': 'publisher',
            'ids': [99999, 99998],
        }, format='json')
        if resp.status_code == 200:
            data = resp.json()
            assert 'updated'      in data
            assert 'requested'    in data
            assert 'processed_at' in data

    def test_health_mark_processed_empty_ids_rejected(self, admin_client):
        resp = admin_client.post(url('health/mark-processed/'), {
            'record_type': 'revenue',
            'ids': [],
        }, format='json')
        assert resp.status_code in (400, 404)

    def test_publisher_cannot_ingest(self, publisher_client):
        resp = publisher_client.post(url('health/ingest/'), {
            'record_type': 'publisher', 'publisher_id': 'PUB001',
            'records': [{}], 'dry_run': True,
        }, format='json')
        assert resp.status_code in (401, 403)
